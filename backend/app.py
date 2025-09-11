# backend/app.py
from __future__ import annotations

import os
import re
import json
import math
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any
from collections import Counter

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from difflib import SequenceMatcher
from datetime import datetime, timedelta
import httpx
from .time_rules import SHOP_HOURS as TR_SHOP_HOURS, validate_pickup_time as tr_validate_pickup_time, parse_pickup_iso as tr_parse_pickup_iso, is_blackout as tr_is_blackout
try:
    from .routers.orders import router as orders_router
except Exception:
    orders_router = None

# Load .env before reading any environment variables
try:
    from dotenv import load_dotenv  # python-dotenv
    load_dotenv()
except Exception:
    pass

# Optional LLM (OpenAI) client
OPENAI_CLIENT = None
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_ENABLED = False
LLM_TIMEOUT_SECS = int(os.getenv("LLM_TIMEOUT_SECS", "20"))
PRIMARY_LANG = os.getenv("PRIMARY_LANG", "fi")
LANGUAGE_POLICY = os.getenv("LANGUAGE_POLICY", "always_primary")  # always_primary | match_user
SUPPORTED_LANG_HINT = "fi, en, sv, no, de, fr, es, it"
ECWID_STORE_URL = os.getenv("ECWID_STORE_URL", "https://rakaskotileipomo.fi/verkkokauppa")
ECWID_STORE_ID = os.getenv("ECWID_STORE_ID")
ECWID_API_TOKEN = os.getenv("ECWID_API_TOKEN")
LOCAL_TZ = os.getenv("LOCAL_TZ", "Europe/Helsinki")
# Ordering time constraints (fallbacks if not discoverable from Ecwid)
ECWID_MAX_ORDER_DAYS = int(os.getenv("ECWID_MAX_ORDER_DAYS", "60"))
ECWID_MIN_LEAD_MINUTES = int(os.getenv("ECWID_MIN_LEAD_MINUTES", "720"))

# Weekly pickup hours (imported from shared time rules)
SHOP_HOURS: Dict[int, List[Tuple[str, str]]] = TR_SHOP_HOURS

# Initialize OpenAI client if key present (optional)
try:
    from openai import OpenAI  # type: ignore
    if os.getenv("OPENAI_API_KEY"):
        OPENAI_CLIENT = OpenAI()
        LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() in {"1","true","yes","on"}
    else:
        LLM_ENABLED = False
except Exception:
    OPENAI_CLIENT = None
    LLM_ENABLED = False

# ============================================================
# Language detection (optional)
# ============================================================
try:
    from langdetect import detect as _ld_detect  # type: ignore
    def detect_lang(text: str) -> str:
        try:
            return _ld_detect(text) or "en"
        except Exception:
            return "en"
except Exception:
    def detect_lang(text: str) -> str:
        return "en"

LANG_NAMES = {
    "en": "English", "fi": "Finnish", "sv": "Swedish", "no": "Norwegian",
    "de": "German", "fr": "French", "es": "Spanish", "it": "Italian",
    "pt": "Portuguese", "nl": "Dutch", "da": "Danish"
}

logger = logging.getLogger("uvicorn")

# ============================================================
# Paths
# ============================================================
HERE = Path(__file__).resolve().parent           # repo/backend/
REPO_ROOT = HERE.parent                          # repo/
FRONTEND_DIR = REPO_ROOT / "frontend"            # index.html, styles.css, chat.js
INDEX_FILE = FRONTEND_DIR / "index.html"

# KB JSON files live under backend/knowledgebase
KB_DIR = HERE / "knowledgebase"
# Discover all JSON KB files using glob (no hardcoding)
KB_FILES = [p.name for p in sorted(KB_DIR.glob("*.json"))]

# ============================================================
# Database (optional; e.g., Railway Postgres)
# ============================================================
DB_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
DB_ENABLED = bool(DB_URL)
ENGINE = None
TABLE_READY = False

def _db_connect_and_prepare():
    """Initialize DB connection and ensure schema exists.
    Uses SQLAlchemy Core to be lightweight.
    """
    global ENGINE, TABLE_READY
    if not DB_ENABLED or ENGINE is not None:
        return
    try:
        from sqlalchemy import create_engine, text
        # Default pool size is fine for single worker; Railway uses one dyno
        ENGINE = create_engine(DB_URL, pool_pre_ping=True)
        with ENGINE.begin() as conn:
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                  id BIGSERIAL PRIMARY KEY,
                  session_id TEXT,
                  role TEXT NOT NULL,
                  message TEXT NOT NULL,
                  source TEXT,
                  match_score DOUBLE PRECISION,
                  created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            ))
        TABLE_READY = True
        logger.info("DB initialized: chat_messages table ready")
    except Exception as e:
        logger.exception(f"DB init failed: {e}")
        ENGINE = None
        TABLE_READY = False

def _db_insert_message(session_id: str | None, role: str, message: str, source: str | None, match_score: float | None):
    if not ENGINE or not TABLE_READY:
        return
    try:
        from sqlalchemy import text
        with ENGINE.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO chat_messages (session_id, role, message, source, match_score)
                    VALUES (:sid, :role, :msg, :src, :ms)
                """),
                {"sid": session_id, "role": role, "msg": message, "src": source, "ms": match_score}
            )
    except Exception as e:
        logger.warning(f"DB insert failed: {e}")

# ============================================================
# Retrieval acceptance gates
# ============================================================
MIN_ACCEPT_SCORE = 1.20   # overall blend threshold (tune 1.0–2.0)
MIN_BM25_SIGNAL  = 0.10   # require some keyword signal
MIN_JACCARD      = 0.05   # or some token overlap
MIN_FUZZY        = 0.40   # or moderate fuzzy similarity

# ============================================================
# FastAPI
# ============================================================
app = FastAPI(title="Piirakkabotti")

# ============================================================
# Models
# ============================================================
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    lang: str | None = None  # 'fi' | 'sv' | 'en'

class ChatResponse(BaseModel):
    reply: str
    source: str | None = None
    match: float | None = None
    session_id: str | None = None

# ============================================================
# Text normalization / tokenization
# ============================================================
STOPWORDS = {
    # EN
    "the","a","an","and","or","to","of","for","on","in","is","it","are","do","you","we","i",
    "can","with","at","my","our","your","me","us","be","have","has","will","from","about",
    # common question words
    "what","which","where","when","who","whom","whose","how",
    # FI (tiny set; expand as needed)
    "ja","tai","se","ne","että","kuin","minun","meidän","teidän","sinun","oma","olen","ovat",
}

SYNONYMS = {
    # English variations
    "wifi":"wi-fi", "wi-fi":"wifi", "internet":"wifi",
    "parking":"car park", "carpark":"car park",
    "pool":"swimming pool", "swimming":"pool",
    "gym":"fitness", "fitness":"fitness",
    "checkout":"check-out", "checkin":"check-in",
    "late checkout":"late check-out", "late-checkout":"late check-out",

    # Sightseeing / attractions phrasing
    "sightsee":"attractions", "sightseeing":"attractions", "sights":"attractions",
    "attraction":"attractions", "landmarks":"attractions", "places":"attractions",
    "visit":"attractions", "doing":"attractions", "do":"attractions",

    # Finnish → English mapping (compact)
    "aamiainen":"breakfast",
    "pysäköinti":"parking",
    "sauna":"sauna",
    "uima-allas":"pool",
    "kuntosali":"gym",
    "myöhäinen":"late",
    "myöhäinen uloskirjautuminen":"late check-out",
    "sisäänkirjautuminen":"check-in",
    "uloskirjautuminen":"check-out",
}

def _normalize(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"[^\w\s\-]", " ", t)  # drop punctuation
    t = re.sub(r"\s+", " ", t)
    return t

def _tokens(text: str):
    for tok in _normalize(text).split():
        if tok in STOPWORDS:
            continue
        tok = SYNONYMS.get(tok, tok)  # map synonyms
        yield tok

def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()

def _token_overlap(a: str, b: str) -> float:
    sa = set(_tokens(a)); sb = set(_tokens(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)

# ============================================================
# KB + Index (mutable; rebuilt on startup)
# ============================================================
KB: List[Dict[str, Any]] = []
DOCS: List[Dict[str, Any]] = []
DF: Counter = Counter()
N: int = 0
AVG_LEN: float = 0.0

def load_kb_clean() -> List[Dict[str, Any]]:
    kb: List[Dict[str, Any]] = []
    seen = set()
    logger.info(f"Looking for KB files in: {KB_DIR.resolve()}")
    for fname in KB_FILES:
        fpath = KB_DIR / fname
        if not fpath.exists():
            logger.warning(f"KB file not found, skipping: {fname}")
            continue
        try:
            logger.info(f"Loading KB file: {fname}")
            data = json.loads(fpath.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                logger.warning(f"KB file is not a list, skipping: {fname}")
                continue
            for row in data:
                if not isinstance(row, dict):
                    continue
                q = (row.get("question") or "").strip()
                a = (row.get("answer") or "").strip()
                if not q or not a:
                    continue
                key = (_normalize(q), _normalize(a))
                if key in seen:
                    continue
                seen.add(key)
                kb.append({
                    "question": q,
                    "answer": a,
                    "title": row.get("title") or "",
                    "file": fname
                })
        except Exception as e:
            logger.exception(f"Error reading KB file {fname}: {e}")
            continue
    logger.info(f"Loaded {len(kb)} KB entries from {len(KB_FILES)} files")
    return kb

def build_index(kb: List[Dict[str, Any]]):
    global DOCS, DF, N, AVG_LEN
    DOCS = []
    DF = Counter()
    for i, item in enumerate(kb):
        text = f"{item.get('question','')} {item.get('answer','')}"
        toks = list(_tokens(text))
        DOCS.append({"id": i, "toks": toks, "len": len(toks)})
        for t in set(toks):
            DF[t] += 1
    N = len(kb)
    AVG_LEN = (sum(d["len"] for d in DOCS) / max(1, len(DOCS))) if DOCS else 0.0
    logger.info(f"Indexed {N} KB docs. AVG_LEN={AVG_LEN:.2f}, vocab={len(DF)}")

def _bm25_score(query_tokens: List[str], doc) -> float:
    # BM25 parameters
    k1, b = 1.4, 0.75
    score = 0.0
    if not doc["toks"]:
        return 0.0
    tf = Counter(doc["toks"])
    for qt in query_tokens:
        df = DF.get(qt, 0)
        if df == 0:
            continue
        idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
        f = tf.get(qt, 0)
        denom = f + k1 * (1 - b + b * (doc["len"] / (AVG_LEN or 1)))
        score += idf * ((f * (k1 + 1)) / (denom or 1))
    return score

def expand_query(q: str) -> List[str]:
    base = list(_tokens(q))
    expanded: List[str] = []
    for t in base:
        expanded.append(t)
        if t in SYNONYMS:
            expanded.append(SYNONYMS[t])  # one-hop

    # Heuristic: if the query sounds like the verb "to park",
    # expand with parking-specific tokens to bridge morphology.
    nq = _normalize(q)
    if re.search(r"\b(where|can|may|could|i|we|my|our|hotel)\b.*\bpark\b", nq):
        expanded.extend(["parking", "car", "car park", "garage", "pysäköinti"])

    return list(dict.fromkeys(expanded))  # de-dupe, order-preserving

# ============================================================
# Light intent detection and KB filtering
# ============================================================
def infer_intent(text: str) -> str | None:
    t = _normalize(text)
    toks = set(_tokens(text))
    # Parking (vehicle) intent heuristics
    if (
        "parking" in toks
        or "garage" in t
        or "pysäköinti" in t
        or "car park" in t
        or re.search(r"\b(where|can|may|could|i|we|my|our|hotel)\b.*\bpark\b", t)
        or re.search(r"\bpark (my|the) car\b", t)
    ):
        return "parking"
    return None

def filter_items_for_intent(intent: str | None, items: List[Dict[str, Any]]):
    if not intent:
        return items
    if intent == "parking":
        keep_kw = {"parking", "garage", "car park", "pysäköinti", "charging", "ev", "electric"}
        filtered: List[Dict[str, Any]] = []
        for it in items:
            text = _normalize(f"{it.get('question','')} {it.get('answer','')}")
            if any(kw in text for kw in keep_kw):
                filtered.append(it)
        return filtered or items
    return items

def score_item(query: str, item: Dict[str, Any], doc):
    qtokens = expand_query(query)
    bm25 = _bm25_score(qtokens, doc)
    fuzzy = _ratio(query, item["question"])
    jacc  = _token_overlap(query, item["question"])
    blend = (0.62 * bm25) + (0.28 * fuzzy) + (0.10 * jacc)
    return blend, bm25, fuzzy, jacc

def find_best_kb_match(query: str, top_k: int = 3):
    if not KB:
        return []

    nq = _normalize(query)

    # Exact question match → return very strong score so it passes gates
    for it in KB:
        if _normalize(it["question"]) == nq:
            return [(10.0, 10.0, 1.0, 1.0, it)]  # blend, bm25, fuzzy, jacc, item

    scored = []
    for d in DOCS:
        it = KB[d["id"]]
        blend, bm25, fuzzy, jacc = score_item(query, it, d)
        if blend > 0:
            scored.append((blend, bm25, fuzzy, jacc, it))

    scored.sort(key=lambda x: x[0], reverse=True)

    # de-dup by identical answers to avoid spam ties
    seen_ans, deduped = set(), []
    for blend, bm25, fuzzy, jacc, it in scored:
        k = _normalize(it["answer"])
        if k in seen_ans:
            continue
        seen_ans.add(k)
        deduped.append((blend, bm25, fuzzy, jacc, it))
        if len(deduped) >= top_k:
            break
    return deduped

# ============================================================
# Rule-based fast paths (greetings, intents)
# ============================================================
BOOKING_KEYWORDS = {"book","reservation","reserve","varaa","booking"}
CALLBACK_KEYWORDS = {"callback","call back","phone call","ring me","soita"}
HELP_KEYWORDS = {"help","apua","support","human","agent"}
# Bakery order intent keywords
ORDER_KEYWORDS = {
    "order","preorder","tilaa","tilaus","ennakkotilaus","ennakkotilata","catering",
    "pickup","nouto","verkkokauppa","shop","store",
    "tilata","tilaisin","tilaan","haluan tilata","haluaisin tilata","ostaa","teen tilauksen"
}
# Capability / identity intent (e.g., "what can you do", "who are you")
CAPABILITY_PHRASES = {
    "what can you do", "what do you do", "how can you help",
    "what can you help", "what can i ask", "what do you know",
    "who are you", "who are u", "what are you", "who r u",
}
GREETINGS = {"hei","moi","terve","hi","hello","hey","hola","ciao"}

def rule_based_answer(user_msg: str, respond_lang: str | None = None) -> str | None:
    text = _normalize(user_msg)

    # greetings (exact or startswith greeting)
    if text in GREETINGS or any(text.startswith(g + " ") for g in GREETINGS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return "Hej! 👋 Hur kan jag hjälpa till?"
        if lang == "fi":
            return "Hei! 👋 Kuinka voin auttaa?"
        return "Hi! 👋 How can I help?"

    # thanks
    if any(p in text for p in {"thanks","thank you","kiitos","tack"}):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return "Varsågod!"
        if lang == "fi":
            return "Ole hyvä!"
        return "You're welcome!"

    # capabilities / identity
    if any(p in text for p in CAPABILITY_PHRASES):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return (
                "Hej, jag är Piirakkabotti – bageriets assistent.\n"
                "Jag kan hjälpa till med:\n"
                "• Produkter och priser\n"
                "• Öppettider och kontakt\n"
                "• Meny och fyllningar\n"
                "• Beställningar och förbeställningar\n"
                "• Allergier och ingredienser\n"
                "• Avhämtning och leverans"
            )
        if lang == "fi":
            return (
                "Hei, olen Piirakkabotti – Rakan kotileipomon avustaja.\n"
                "Voin auttaa seuraavissa asioissa:\n"
                "• Tuotteet ja hinnat\n"
                "• Aukioloajat ja yhteystiedot\n"
                "• Menu ja täytteet\n"
                "• Tilaukset ja ennakkotilaukset\n"
                "• Allergiat ja ainesosat\n"
                "• Nouto ja toimitus"
            )
        return (
            "Hi, I’m Piirakkabotti, your bakery assistant.\n"
            "I can help with:\n"
            "• Products and prices\n"
            "• Opening hours and contact\n"
            "• Menu and fillings\n"
            "• Orders and preorders\n"
            "• Allergies and ingredients\n"
            "• Pickup and delivery"
        )

    # Ordering intent → link to Ecwid store (pickup, pay in store)
    if any(k in text for k in ORDER_KEYWORDS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        url = ECWID_STORE_URL
        if lang == "sv":
            return (
                f"""
<div class=\"order-ui\">
  <div class=\"order-title\">Beställ i webbutiken</div>
  <div class=\"order-sub\">Hämta i butiken, betalning på plats.</div>
  <div class=\"order-buttons\">
    <a class=\"btn\" href=\"{url}\" target=\"_blank\" rel=\"noopener\">Öppna webbutiken</a>
    <button class=\"btn\" data-action=\"start-order\">Beställ i chatten</button>
  </div>
</div>
"""
            )
        if lang == "fi":
            return (
                f"""
<div class=\"order-ui\">
  <div class=\"order-title\">Tilaa verkkokaupasta</div>
  <div class=\"order-sub\">Nouto myymälästä, maksu paikan päällä.</div>
  <div class=\"order-buttons\">
    <a class=\"btn\" href=\"{url}\" target=\"_blank\" rel=\"noopener\">Avaa verkkokauppa</a>
    <button class=\"btn\" data-action=\"start-order\">Tilaa chatissa</button>
  </div>
</div>
"""
            )
        return (
            f"""
<div class=\"order-ui\">
  <div class=\"order-title\">Order Online</div>
  <div class=\"order-sub\">Pickup in store, pay at pickup.</div>
  <div class=\"order-buttons\">
    <a class=\"btn\" href=\"{url}\" target=\"_blank\" rel=\"noopener\">Open Online Shop</a>
    <button class=\"btn\" data-action=\"start-order\">Order in chat</button>
  </div>
</div>
"""
        )

# ============================================================
# Ecwid helpers (server-side only)
# ============================================================
def _ecwid_base() -> str:
    if not ECWID_STORE_ID:
        raise RuntimeError("ECWID_STORE_ID is not set")
    return f"https://app.ecwid.com/api/v3/{ECWID_STORE_ID}"

def _ecwid_headers() -> Dict[str, str]:
    if not ECWID_API_TOKEN:
        raise RuntimeError("ECWID_API_TOKEN is not set")
    return {"Authorization": f"Bearer {ECWID_API_TOKEN}", "Content-Type": "application/json"}

def _ecwid_get_products(limit: int = 100, category: int | None = None) -> List[Dict[str, Any]]:
    base = _ecwid_base()
    headers = _ecwid_headers()
    url = f"{base}/products"
    params: Dict[str, Any] = {"limit": limit}
    if category is not None:
        params["category"] = int(category)
    with httpx.Client(timeout=10.0) as client:
        r = client.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
    return data.get("items", [])

def _ecwid_get_categories(limit: int = 200) -> List[Dict[str, Any]]:
    base = _ecwid_base()
    headers = _ecwid_headers()
    url = f"{base}/categories"
    params: Dict[str, Any] = {"limit": limit}
    with httpx.Client(timeout=10.0) as client:
        r = client.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
    return data.get("items", [])

def _ecwid_get_profile() -> Dict[str, Any]:
    base = _ecwid_base()
    headers = _ecwid_headers()
    url = f"{base}/profile"
    with httpx.Client(timeout=10.0) as client:
        r = client.get(url, headers=headers)
        r.raise_for_status()
        return r.json()

def _ecwid_get_shipping_options() -> List[Dict[str, Any]]:
    base = _ecwid_base()
    headers = _ecwid_headers()
    url = f"{base}/profile/shippingOptions"
    with httpx.Client(timeout=10.0) as client:
        r = client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
    # Ecwid returns either list or {'items': [...]}
    if isinstance(data, dict):
        return data.get("items", [])
    if isinstance(data, list):
        return data
    return []

def _curate_products(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    keep = []
    KEYWORDS = [
        "karjalan", "karelian", "piirakka", "pie", "samosa", "curry", "twist",
        "mustikkakukko", "blueberry", "marjapiirakka", "berry", "pulla", "bun"
    ]
    for it in items:
        name = (it.get("name") or "").lower()
        # Only offer enabled products to avoid API errors
        if not it.get("enabled", True):
            continue
        if any(k in name for k in KEYWORDS):
            keep.append({
                "id": it.get("id"),
                "sku": it.get("sku"),
                "name": it.get("name"),
                "price": it.get("price"),
                "enabled": True,
                # Best-effort image URL
                "imageUrl": (
                    it.get("thumbnailUrl")
                    or it.get("imageUrl")
                    or ((it.get("image") or {}).get("url"))
                ),
                # Stock information if available
                "inStock": it.get("inStock"),
                "quantity": it.get("quantity") or it.get("quantityAvailable"),
            })
    # de-dup by id/sku
    seen, out = set(), []
    for it in keep:
        key = it.get("id") or it.get("sku")
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out[:25]

class OrderItem(BaseModel):
    productId: int | None = None
    sku: str | None = None
    quantity: int

class OrderRequest(BaseModel):
    items: List[OrderItem]
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    pickup_time: str | None = None
    note: str | None = None

# ============================================================
# Fallback composer (out-of-scope aware)
# ============================================================
def llm_like_answer(query: str, kb_items: List[Dict[str, Any]], respond_lang: str | None = None) -> str:
    toks = list(_tokens(query))
    has_overlap = any(t in DF for t in toks)
    if not kb_items or not has_overlap:
        lang = (respond_lang or PRIMARY_LANG)
        if lang == "fi":
            return (
                f"En löytänyt tietoja aiheesta “{query}”. "
                "Voin auttaa leipomoon liittyvissä asioissa, kuten tuotteet, aukioloajat, menu, tilaukset ja allergiat. "
                "Kokeile kysyä: “Mitkä ovat aukioloajat?”, “Voinko tilata etukäteen?”, tai “Sisältääkö piirakka pähkinää?”."
            )
        if lang == "sv":
            return (
                f"Jag kunde inte hitta information om “{query}”. "
                "Jag kan hjälpa till med bagerifrågor som produkter, öppettider, meny, beställningar och allergier. "
                "Prova att fråga: ”Vilka är öppettiderna?”, ”Kan jag förbeställa?” eller ”Innehåller pajen nötter?”."
            )
        else:
            return (
                f"I couldn’t find details about “{query}”. "
                "I can help with bakery topics like products, opening hours, menu, orders, and allergies. "
                "Try asking: “What are your opening hours?”, “Can I preorder?”, or “Does the pie contain nuts?”."
            )
    best = kb_items[0]
    ans = (best.get("answer") or "").strip()
    return ans or "I found a related item, but it had no answer text."

def generate_llm_answer(query: str, kb_items: List[Dict[str, Any]], respond_lang: str) -> str:
    """Use OpenAI to compose a KB-grounded answer in the requested language.
    Safe fallback if unavailable.
    """
    if not OPENAI_CLIENT or not LLM_ENABLED:
        return llm_like_answer(query, kb_items, respond_lang)

    # Intent filter to avoid mixing unrelated topics (e.g., park vs parking)
    intent = infer_intent(query)
    kb_items = filter_items_for_intent(intent, kb_items)

    # Build compact context from top items
    context_blocks = []
    for it in kb_items[:5]:
        q = (it.get("question") or "").strip()
        a = (it.get("answer") or "").strip()
        if not a:
            continue
        src = it.get("file") or "knowledgebase"
        context_blocks.append(f"Q: {q}\nA: {a}\n(Source: {src})")

    if not context_blocks:
        return llm_like_answer(query, kb_items, respond_lang)

    lang_name = LANG_NAMES.get(respond_lang, respond_lang)
    system = (
        "You are Piirakkabotti, a helpful assistant for Raka's Kotileipomo bakery in Helsinki. "
        "Answer strictly using the provided knowledge base. "
        "Only answer the user's explicit intent and do not add unrelated recommendations unless asked. "
        "If the information is missing, say you don't know and recommend contacting the bakery staff. "
        f"Be concise, friendly, and do not invent details. Respond in {lang_name}."
    )
    context = "\n\n".join(context_blocks)
    user = (
        f"User question: {query}\n\n"
        f"Knowledge base excerpts:\n{context}\n\n"
        "Compose the best possible answer using only the excerpts above."
    )

    try:
        resp = OPENAI_CLIENT.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=300,
            timeout=LLM_TIMEOUT_SECS,
        )
        txt = (resp.choices[0].message.content or "").strip()
        return txt or llm_like_answer(query, kb_items, respond_lang)
    except Exception:
        return llm_like_answer(query, kb_items, respond_lang)

# ============================================================
# API routes
# ============================================================
@app.get("/api/health")
def health():
    return {
        "ok": True,
        "kb_items": len(KB),
        "kb_dir": str(KB_DIR.resolve()),
        "vocab": len(DF),
        "avg_len": round(AVG_LEN, 2),
        "llm_enabled": bool(LLM_ENABLED),
        "llm_model": LLM_MODEL if LLM_ENABLED else None,
        "langdetect": True,
        "lang_hint": SUPPORTED_LANG_HINT,
        "ecwid_ready": bool(ECWID_STORE_ID and ECWID_API_TOKEN),
    }

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request, response: Response):
    user_msg = (req.message or "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Session handling: prefer payload session_id; else cookie; else create
    session_id = (req.session_id or request.cookies.get("chat_session") or "").strip()
    if not session_id:
        import uuid
        session_id = uuid.uuid4().hex
        # 30 days cookie
        response.set_cookie("chat_session", session_id, max_age=60*60*24*30, httponly=False, samesite="Lax")

    # Language handling
    # Language preference: explicit from client, cookie, else policy/detection
    chosen_lang = (req.lang or request.cookies.get("chat_lang") or "").strip().lower()
    if chosen_lang not in {"fi","sv","en"}:
        chosen_lang = None
    user_lang = detect_lang(user_msg)
    respond_lang = chosen_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else user_lang)
    if req.lang and chosen_lang:
        # persist choice for session via cookie
        response.set_cookie("chat_lang", chosen_lang, max_age=60*60*24*30, httponly=False, samesite="Lax")

    # Log user message
    try:
        _db_insert_message(session_id, "user", user_msg, None, None)
    except Exception:
        pass

    # 1) Rules first
    rb = rule_based_answer(user_msg, respond_lang)
    if rb:
        return ChatResponse(reply=rb, source="Rules", match=1.0)

    # 2) Retrieve
    top = find_best_kb_match(user_msg, top_k=3)

    if top:
        best_blend, bm25, fuzzy, jacc, best_item = top[0]

        # Require some lexical evidence (BM25 or Jaccard).
        # However, for very short queries (1–2 tokens or short strings), allow fuzzy‑only
        # matches with a higher threshold so typos like "karjalanpiirakk" still hit.
        q_tok_count = len(list(_tokens(user_msg)))
        q_char_len = len((user_msg or '').strip())
        strong_enough = (
            best_blend >= MIN_ACCEPT_SCORE or
            (bm25 >= MIN_BM25_SIGNAL) or
            (jacc >= MIN_JACCARD) or
            (fuzzy >= max(MIN_FUZZY, 0.55) and (bm25 > 0 or jacc > 0)) or
            # Fuzzy‑only allowance for short queries
            (q_tok_count <= 2 and fuzzy >= 0.72) or
            (q_char_len <= 14 and fuzzy >= 0.74)
        )

        if strong_enough:
            kb_items = [t[4] for t in top]
            # Apply intent filtering for both LLM and non-LLM paths
            intent = infer_intent(user_msg)
            kb_items = filter_items_for_intent(intent, kb_items)
            if LLM_ENABLED and OPENAI_CLIENT:
                reply = generate_llm_answer(user_msg, kb_items, respond_lang=respond_lang)
                src = f"LLM • KB-grounded ({best_item.get('file','')})"
            else:
                # Prefer the first filtered item if available
                chosen = kb_items[0] if kb_items else best_item
                reply = (chosen.get("answer") or "").strip() or llm_like_answer(user_msg, kb_items, respond_lang)
                src = f"KB • {best_item.get('file','')}"
            # Log assistant message
            try:
                _db_insert_message(session_id, "assistant", reply, src, float(round(best_blend, 3)))
            except Exception:
                pass
            return ChatResponse(reply=reply, source=src, match=float(round(best_blend, 3)), session_id=session_id)

    # 3) Out-of-scope / soft fallback
    kb_items = [t[4] for t in top] if top else []
    intent = infer_intent(user_msg)
    kb_items = filter_items_for_intent(intent, kb_items)
    if LLM_ENABLED and OPENAI_CLIENT:
        reply = generate_llm_answer(user_msg, kb_items, respond_lang=respond_lang)
        src = "LLM • Fallback KB-grounded"
    else:
        reply = llm_like_answer(user_msg, kb_items, respond_lang)
        src = "Fallback • KB-grounded"
    best_score = float(round(top[0][0], 3)) if top else 0.0
    try:
        _db_insert_message(session_id, "assistant", reply, src, best_score)
    except Exception:
        pass
    return ChatResponse(reply=reply, source=src, match=best_score, session_id=session_id)

# ============================================================
# Ecwid endpoints
# ============================================================
@app.get("/api/products")
def api_products(category: int | None = None):
    if not (ECWID_STORE_ID and ECWID_API_TOKEN):
        raise HTTPException(status_code=503, detail="In-chat ordering is not configured.")
    try:
        items = _ecwid_get_products(limit=100, category=category)
        curated = _curate_products(items)
        return {"items": curated}
    except Exception as e:
        logger.exception(f"Ecwid products error: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch products.")

@app.get("/api/categories")
def api_categories():
    if not (ECWID_STORE_ID and ECWID_API_TOKEN):
        raise HTTPException(status_code=503, detail="In-chat ordering is not configured.")
    try:
        cats = _ecwid_get_categories(limit=200)
        # Return minimal fields
        out = [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "parentId": c.get("parentId"),
                "imageUrl": c.get("thumbnailUrl") or c.get("imageUrl"),
            }
            for c in cats if c.get("id") and c.get("name")
        ]
        return {"items": out}
    except Exception as e:
        logger.exception(f"Ecwid categories error: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch categories.")

@app.post("/api/order")
def api_order(req: OrderRequest):
    if not (ECWID_STORE_ID and ECWID_API_TOKEN):
        raise HTTPException(status_code=503, detail="In-chat ordering is not configured.")
    if not req.items:
        raise HTTPException(status_code=400, detail="No items provided.")
    # Require pickup time for all orders so server can enforce lead/max/blackouts
    if not (req.pickup_time and req.pickup_time.strip()):
        raise HTTPException(status_code=400, detail="pickup_time is required in format YYYY-MM-DDTHH:MM.")
    items = []
    for it in req.items:
        if (not it.productId) and (not it.sku):
            raise HTTPException(status_code=400, detail="Each item must have productId or sku.")
        if it.quantity <= 0:
            continue
        entry = {"quantity": it.quantity}
        if it.productId:
            entry["productId"] = it.productId
        if it.sku:
            entry["sku"] = it.sku
        items.append(entry)
    if not items:
        raise HTTPException(status_code=400, detail="All quantities are zero.")

    # Validate pickup time (format, hours, min lead, max window, blackout)
    ok, reason = _validate_pickup_time(req.pickup_time)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Pickup time not available: {reason}")
    try:
        cons = api_order_constraints(debug=False)  # reuse same logic
        min_lead = int(cons.get("min_lead_minutes", 0))
        max_days = int(cons.get("max_days", 0))
        blackouts = cons.get("blackout_dates") or []
        now = datetime.now()
        dt = _parse_pickup_iso(req.pickup_time)
        if not dt:
            raise HTTPException(status_code=400, detail="Invalid time format. Use YYYY-MM-DDTHH:MM.")
        # Lead time
        if min_lead > 0:
            min_dt = now + timedelta(minutes=min_lead)
            if dt < min_dt:
                raise HTTPException(status_code=400, detail=f"Pickup must be at least {int(round(min_lead/60))} hours from now.")
        # Max days window
        if max_days > 0:
            limit = now + timedelta(days=max_days)
            if dt.date() > limit.date():
                raise HTTPException(status_code=400, detail=f"Pickup cannot be more than {max_days} days ahead.")
        # Blackout
        if _is_blackout(dt, blackouts):
            raise HTTPException(status_code=400, detail="Pickup date is not available (blackout).")
    except HTTPException:
        raise
    except Exception:
        # If constraint check fails unexpectedly, proceed (Ecwid will still validate)
        pass

    body = {
        "name": req.name or "Chat Customer",
        "email": req.email or "",
        "phone": req.phone or "",
        "paymentMethod": "Pay at pickup",
        "paymentStatus": "AWAITING_PAYMENT",
        "shippingOption": {"shippingMethodName": "Pickup", "fulfillmentType": "PICKUP"},
        "items": items,
    }
    comment_parts = []
    if req.pickup_time:
        comment_parts.append(f"Pickup: {req.pickup_time}")
    if req.note:
        comment_parts.append(req.note)
    if comment_parts:
        body["customerComment"] = " | ".join(comment_parts)

    try:
        base = _ecwid_base()
        headers = _ecwid_headers()
        url = f"{base}/orders"
        with httpx.Client(timeout=10.0) as client:
            r = client.post(url, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
        return {"ok": True, "id": data.get("id"), "orderNumber": data.get("orderNumber")}
    except httpx.HTTPStatusError as he:
        # Try to surface a meaningful error message from Ecwid
        resp = he.response
        status = resp.status_code
        detail = ""
        try:
            payload = resp.json()
            # Ecwid commonly returns fields like 'errorMessage' or 'message'
            detail = (
                payload.get("errorMessage")
                or payload.get("message")
                or payload.get("error")
                or ""
            )
            # Include additional context if available
            if not detail and isinstance(payload, dict):
                # Sometimes errors are nested under a list like 'errors'
                errs = payload.get("errors")
                if isinstance(errs, list) and errs:
                    detail = str(errs[0])
        except Exception:
            # Fall back to raw text if JSON parsing fails
            detail = (resp.text or "").strip()

        if not detail:
            # Final fallback to a generic message
            detail = f"Ecwid API error {status}"

        logger.exception(f"Ecwid order HTTP error: {status} {detail}")
        raise HTTPException(status_code=status, detail=detail)
    except Exception as e:
        logger.exception(f"Ecwid order error: {e}")
        raise HTTPException(status_code=502, detail="Failed to create order.")

@app.get("/api/pickup_hours")
def api_pickup_hours():
    return {"timezone": LOCAL_TZ, "hours": SHOP_HOURS}

from fastapi import Query


@app.get("/api/order_constraints")
def api_order_constraints(debug: bool = Query(False, description="Include debug details")):
    """Return min lead time and max advance days for orders.
    Attempts to discover from Ecwid shipping/pickup settings; falls back to env defaults.
    """
    if not (ECWID_STORE_ID and ECWID_API_TOKEN):
        # Without Ecwid, still provide useful defaults for the UI
        out = {
            "source": "defaults",
            "min_lead_minutes": ECWID_MIN_LEAD_MINUTES,
            "max_days": ECWID_MAX_ORDER_DAYS,
        }
        if debug:
            out["details"] = {
                "reason": "missing_credentials",
            }
        return out
    # Start with None; only fall back to env defaults if not discovered from Ecwid
    min_lead: int | None = None
    max_days: int | None = None
    found_min = False
    found_max = False
    debug_notes: Dict[str, Any] = {"sources": []}
    blackout_ranges: list[Dict[str, Any]] = []
    try:
        def _availability_to_days(val: Any) -> int | None:
            if not isinstance(val, str):
                return None
            s = val.upper().strip()
            mapping = {
                "ONE_WEEK": 7,
                "TWO_WEEKS": 14,
                "ONE_MONTH": 30,
                "TWO_MONTHS": 60,
                "THREE_MONTHS": 90,
            }
            return mapping.get(s)

        # Try to infer from /profile/shippingOptions endpoint
        opts = _ecwid_get_shipping_options()
        for opt in opts:
            name = (opt.get("title") or opt.get("name") or "").lower()
            fulfill = (
                opt.get("fulfillmentType")
                or opt.get("fulfilmentType")
                or opt.get("type")
                or ""
            ).upper()
            settings = opt.get("settings") or {}

            # Lead time (minutes)
            prep_mins = (
                settings.get("pickupPreparationTimeMinutes")
                or settings.get("preparationTimeMinutes")
                or settings.get("leadTimeMinutes")
                or opt.get("pickupPreparationTimeMinutes")
                or opt.get("fulfillmentTimeInMinutes")
            )
            # Some stores expose hours
            if not prep_mins:
                val_h = opt.get("pickupPreparationTimeHours")
                if isinstance(val_h, (int, float)):
                    prep_mins = int(val_h) * 60
            if isinstance(prep_mins, (int, float)):
                val = int(prep_mins)
                min_lead = val if (min_lead is None or val > min_lead) else min_lead
                found_min = True

            # Max days in advance
            md = (
                settings.get("daysInAdvance")
                or settings.get("maxAdvanceDays")
                or settings.get("orderAheadDays")
                or _availability_to_days(opt.get("availabilityPeriod"))
            )
            if isinstance(md, int) and md > 0:
                val = int(md)
                max_days = val if (max_days is None or val < max_days) else max_days
                found_max = True

            if debug:
                debug_notes.setdefault("sources", []).append({
                    "option": name,
                    "fulfillmentType": fulfill,
                    "preparation_minutes": prep_mins,
                    "availabilityPeriod": opt.get("availabilityPeriod"),
                    "max_days_candidate": md,
                })

            # Collect blackout date ranges if present
            bl = opt.get("blackoutDates")
            if isinstance(bl, list):
                for it in bl:
                    fd = it.get("fromDate") or it.get("from")
                    td = it.get("toDate") or it.get("to")
                    ra = bool(it.get("repeatedAnnually"))
                    if fd and td:
                        blackout_ranges.append({"from": fd, "to": td, "repeatedAnnually": ra})

        # Also inspect /profile shipping settings directly (often richer)
        try:
            profile = _ecwid_get_profile()
            pset = profile.get("settings") or {}
            ship = pset.get("shipping") or {}
            md_profile = ship.get("maxOrderAheadDays")
            if isinstance(md_profile, int) and md_profile > 0:
                val = int(md_profile)
                max_days = val if (max_days is None or val < max_days) else max_days
                found_max = True

            prof_opts = ship.get("shippingOptions") or []
            for opt in prof_opts:
                name = (opt.get("title") or opt.get("name") or "").lower()
                fulfill = (
                    opt.get("fulfillmentType")
                    or opt.get("fulfilmentType")
                    or opt.get("type")
                    or ""
                ).upper()
                # Lead time
                prep_mins = (
                    opt.get("pickupPreparationTimeMinutes")
                    or opt.get("fulfillmentTimeInMinutes")
                )
                if not prep_mins:
                    val_h = opt.get("pickupPreparationTimeHours")
                    if isinstance(val_h, (int, float)):
                        prep_mins = int(val_h) * 60
                if isinstance(prep_mins, (int, float)):
                    val = int(prep_mins)
                    min_lead = val if (min_lead is None or val > min_lead) else min_lead
                    found_min = True

                # Max days via availabilityPeriod
                md = _availability_to_days(opt.get("availabilityPeriod"))
                if isinstance(md, int) and md > 0:
                    val = int(md)
                    max_days = val if (max_days is None or val < max_days) else max_days
                    found_max = True

                if debug:
                    debug_notes.setdefault("profile_sources", []).append({
                        "option": name,
                        "fulfillmentType": fulfill,
                        "preparation_minutes": prep_mins,
                        "availabilityPeriod": opt.get("availabilityPeriod"),
                    })
                # Collect blackout dates from profile shippingOptions as well
                bl = opt.get("blackoutDates")
                if isinstance(bl, list):
                    for it in bl:
                        fd = it.get("fromDate") or it.get("from")
                        td = it.get("toDate") or it.get("to")
                        ra = bool(it.get("repeatedAnnually"))
                        if fd and td:
                            blackout_ranges.append({"from": fd, "to": td, "repeatedAnnually": ra})
            if debug:
                debug_notes["profile_checked"] = True
                debug_notes["profile_shipping_maxOrderAheadDays"] = md_profile
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"Failed to fetch Ecwid order constraints, using defaults: {e}")
    # Apply fallbacks if nothing was discovered
    if min_lead is None:
        min_lead = ECWID_MIN_LEAD_MINUTES
    if max_days is None:
        max_days = ECWID_MAX_ORDER_DAYS
    src = "ecwid" if (found_min or found_max) else "defaults"
    out = {
        "source": src,
        "min_lead_minutes": int(min_lead),
        "max_days": int(max_days),
        "blackout_dates": blackout_ranges,
    }
    if debug:
        out["details"] = {
            "found_min": found_min,
            "found_max": found_max,
            **debug_notes,
        }
    return out

@app.get("/api/check_pickup")
def api_check_pickup(iso: str):
    ok, reason = _validate_pickup_time(iso)
    return {"ok": ok, "reason": reason}

def _parse_pickup_iso(s: str) -> datetime | None:
    return tr_parse_pickup_iso(s)

def _validate_pickup_time(pickup_iso: str) -> Tuple[bool, str | None]:
    return tr_validate_pickup_time(pickup_iso, SHOP_HOURS)

def _is_blackout(dt: datetime, blackouts: List[Dict[str, Any]]) -> bool:
    return tr_is_blackout(dt, blackouts)

# ============================================================
# Startup: load KB and build index (with logs)
# ============================================================
@app.on_event("startup")
def startup_event():
    global KB
    logger.info("=== App startup: loading KB and building index ===")
    if DB_ENABLED:
        _db_connect_and_prepare()
    KB = load_kb_clean()
    build_index(KB)

# ============================================================
# Frontend routes (serve index.html + static assets from /frontend)
# ============================================================
if not FRONTEND_DIR.exists():
    raise RuntimeError(f"Frontend folder not found at: {FRONTEND_DIR}")
if not INDEX_FILE.exists():
    raise RuntimeError(f"index.html not found at: {INDEX_FILE}")

@app.get("/")
def root():
    return FileResponse(INDEX_FILE)

# Include API routers before mounting static files
if orders_router is not None:
    app.include_router(orders_router)
# Mount ALL static assets at site root (keep AFTER API routes)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

# ============================================================
# Local dev entrypoint
# ============================================================
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    import uvicorn
    uvicorn.run("backend.app:app", host=host, port=port, reload=True)
