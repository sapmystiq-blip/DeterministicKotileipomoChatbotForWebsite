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

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from difflib import SequenceMatcher
from datetime import datetime, timedelta
import httpx
from .time_rules import SHOP_HOURS as TR_SHOP_HOURS, validate_pickup_time as tr_validate_pickup_time, parse_pickup_iso as tr_parse_pickup_iso, is_blackout as tr_is_blackout
from . import intent_router as IR
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
GOOGLE_REVIEW_URL = os.getenv("GOOGLE_REVIEW_URL", "https://www.google.com/search?q=Raka%27s+kotileipomo&sca_esv=6c7f7ca6e8ee6a34&rlz=1C5CHFA_enFI1167FI1167&hl=fi-FI&biw=1164&bih=754&tbm=lcl&ei=gxvEaJ7VH_G0wPAPhfyKqAY&ved=0ahUKEwjeos7mpdOPAxVxGhAIHQW-AmUQ4dUDCAo&uact=5&oq=Raka%27s+kotileipomo&gs_lp=Eg1nd3Mtd2l6LWxvY2FsIhJSYWthJ3Mga290aWxlaXBvbW8yBRAAGIAEMgUQABiABDIGEAAYFhgeMgYQABgWGB4yBhAAGBYYHjICECYyCBAAGIAEGKIEMggQABiABBiiBDIIEAAYogQYiQVIvAhQxAZYxAZwAHgAkAEAmAF-oAGmAqoBAzIuMbgBA8gBAPgBAZgCA6ACwAKYAwCIBgGSBwMxLjKgB64PsgcDMS4yuAfAAsIHBTItMi4xyAcW&sclient=gws-wiz-local#lkt=LocalPoiReviews&rlfi=hd:;si:7666209392203396731,l,ChJSYWthJ3Mga290aWxlaXBvbW9I2M7x8PS1gIAIWiQQABABGAAYASIScmFrYSdzIGtvdGlsZWlwb21vKgYIAhAAEAGSAQZiYWtlcnmqAUoKDS9nLzExcHk3MXN0dnMQATIfEAEiG12RikuLePke45zt2cmJ_CcYGIZmNEHDLSGmJzIWEAIiEnJha2EncyBrb3RpbGVpcG9tbw,y,n4xN2WK8BF4;mv:[[60.197882977319026,24.947339021027446],[60.19752302268097,24.946614778972545]]&lrd=0x468df9bf012e8049:0x6a63d8d32c0bf67b,3,,,,")
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

# KB JSON files live under backend/knowledgebase. Legacy Q&A lists are under deprecated/.
KB_DIR = HERE / "knowledgebase"
LEGACY_KB_DIR = KB_DIR / "deprecated"
# Discover only legacy Q&A JSON files (list of {question, answer})
KB_FILES = [p.name for p in sorted(LEGACY_KB_DIR.glob("*.json"))]

# ============================================================
# Database (optional; e.g., Railway Postgres)
# ============================================================
DB_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
# SQLAlchemy requires the "postgresql://" scheme (not legacy "postgres://").
# Normalize if a Railway/Heroku style URL is provided.
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = "postgresql://" + DB_URL[len("postgres://"):]
DB_ENABLED = bool(DB_URL)
ENGINE = None
TABLE_READY = False
ADMIN_KEY = os.getenv("ADMIN_KEY") or os.getenv("BOT_ADMIN_KEY")

# In-memory admin session allowlist (per-process)
ADMIN_SESSIONS: set[str] = set()

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
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS kb_items (
                  id BIGSERIAL PRIMARY KEY,
                  lang TEXT,
                  question TEXT NOT NULL,
                  answer TEXT NOT NULL,
                  enabled BOOLEAN DEFAULT TRUE,
                  category TEXT,
                  created_by TEXT,
                  created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            ))
            # Ensure category column exists if table was created previously
            conn.execute(text("ALTER TABLE kb_items ADD COLUMN IF NOT EXISTS category TEXT"))
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS feedback_queue (
                  id BIGSERIAL PRIMARY KEY,
                  session_id TEXT,
                  name TEXT,
                  email TEXT,
                  message TEXT NOT NULL,
                  status TEXT DEFAULT 'pending',
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

def _db_insert_feedback(session_id: str | None, name: str | None, email: str | None, message: str):
    if not ENGINE or not TABLE_READY:
        return
    try:
        from sqlalchemy import text
        with ENGINE.begin() as conn:
            conn.execute(text(
                """
                INSERT INTO feedback_queue (session_id, name, email, message)
                VALUES (:sid, :name, :email, :msg)
                """
            ), {"sid": session_id, "name": name, "email": email, "msg": message})
    except Exception as e:
        logger.warning(f"DB feedback insert failed: {e}")

def _db_feedback_list(status: str = "pending", limit: int = 100) -> list[dict[str, Any]]:
    if not ENGINE or not TABLE_READY:
        return []
    try:
        from sqlalchemy import text
        with ENGINE.begin() as conn:
            rs = conn.execute(text(
                """
                SELECT id, session_id, name, email, message, status, created_at
                FROM feedback_queue
                WHERE status = :st
                ORDER BY id DESC
                LIMIT :lim
                """
            ), {"st": status, "lim": int(limit)})
            cols = rs.keys()
            return [dict(zip(cols, row)) for row in rs.fetchall()]
    except Exception as e:
        logger.warning(f"DB feedback list failed: {e}")
        return []

def _db_feedback_set_status(fid: int, status: str):
    if not ENGINE or not TABLE_READY:
        return
    try:
        from sqlalchemy import text
        with ENGINE.begin() as conn:
            conn.execute(text("UPDATE feedback_queue SET status=:st WHERE id=:id"), {"st": status, "id": int(fid)})
    except Exception as e:
        logger.warning(f"DB feedback status update failed: {e}")

def _db_kb_insert(lang: str | None, question: str, answer: str, created_by: str | None, enabled: bool = True, category: str | None = None) -> int | None:
    if not ENGINE or not TABLE_READY:
        return None
    try:
        from sqlalchemy import text
        with ENGINE.begin() as conn:
            rs = conn.execute(text(
                """
                INSERT INTO kb_items (lang, question, answer, enabled, category, created_by)
                VALUES (:lang, :q, :a, :en, :cat, :by)
                RETURNING id
                """
            ), {"lang": lang, "q": question, "a": answer, "en": bool(enabled), "cat": category, "by": created_by})
            row = rs.fetchone()
            return int(row[0]) if row else None
    except Exception as e:
        logger.warning(f"DB kb insert failed: {e}")
        return None

def _db_kb_list(limit: int = 500) -> list[dict[str, Any]]:
    if not ENGINE or not TABLE_READY:
        return []
    try:
        from sqlalchemy import text
        with ENGINE.begin() as conn:
            rs = conn.execute(text(
                """
                SELECT id, lang, question, answer, enabled, category, created_by, created_at
                FROM kb_items
                ORDER BY id DESC
                LIMIT :lim
                """
            ), {"lim": int(limit)})
            cols = rs.keys()
            return [dict(zip(cols, row)) for row in rs.fetchall()]
    except Exception as e:
        logger.warning(f"DB kb list failed: {e}")
        return []

def _db_kb_toggle(item_id: int, enabled: bool):
    if not ENGINE or not TABLE_READY:
        return
    try:
        from sqlalchemy import text
        with ENGINE.begin() as conn:
            conn.execute(text("UPDATE kb_items SET enabled=:en WHERE id=:id"), {"en": bool(enabled), "id": int(item_id)})
    except Exception as e:
        logger.warning(f"DB kb toggle failed: {e}")

def _db_kb_enabled_all(lang: str | None = None) -> list[dict[str, Any]]:
    if not ENGINE or not TABLE_READY:
        return []
    try:
        from sqlalchemy import text
        with ENGINE.begin() as conn:
            if lang:
                rs = conn.execute(text(
                    """
                    SELECT question, answer, lang, category
                    FROM kb_items
                    WHERE enabled = TRUE AND (lang = :lang OR lang IS NULL OR lang = '')
                    ORDER BY id DESC
                    """
                ), {"lang": lang})
            else:
                rs = conn.execute(text(
                    "SELECT question, answer, lang, category FROM kb_items WHERE enabled = TRUE ORDER BY id DESC"
                ))
            cols = rs.keys()
            return [dict(zip(cols, row)) for row in rs.fetchall()]
    except Exception as e:
        logger.warning(f"DB kb fetch failed: {e}")
        return []

def _refresh_kb_index():
    try:
        kb_rows = _db_kb_enabled_all()
        kb = []
        for r in kb_rows:
            q = (r.get("question") or "").strip()
            a = (r.get("answer") or "").strip()
            if not q or not a:
                continue
            kb.append({"question": q, "answer": a, "title": (r.get("category") or r.get("lang") or "db"), "file": "db"})
        build_index(kb)
        global KB
        KB = kb
        logger.info(f"DB KB loaded: {len(KB)} items")
    except Exception as e:
        logger.warning(f"KB index refresh failed: {e}")

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

# Helper: when chat ordering is disabled, strip the Start Order button from UI snippets
def _maybe_strip_chat_order_btn(html: str) -> str:
    try:
        if os.getenv("ENABLE_CHAT_ORDERING", "false").lower() in {"0","false","no","off"}:
            return re.sub(r'<button class="btn" data-action="start-order">.*?</button>', '', html)
        return html
    except Exception:
        return html

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


class FeedbackPayload(BaseModel):
    name: str | None = None
    email: str | None = None
    message: str

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
    logger.info(f"Looking for legacy KB files in: {LEGACY_KB_DIR.resolve()}")
    for fname in KB_FILES:
        fpath = LEGACY_KB_DIR / fname
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

    # Explicit pickup-on-weekday queries → delegate to FAQ weekday logic
    try:
        pk_kws = {"pickup","pick up","pick-up","nouto","noutaa","hämta","hamta","hämt"}
        if any(k in text for k in pk_kws):
            import re as _re
            toks = set(_re.findall(r"[a-zåäö]+", text))
            # Common weekday tokens and abbreviations across FI/SV/EN
            wd = {
                # EN
                "monday","tuesday","wednesday","thursday","friday","saturday","sunday",
                "mon","tue","wed","thu","fri","sat","sun",
                # FI
                "maanantai","tiistai","keskiviikko","torstai","perjantai","lauantai","sunnuntai",
                "ma","ti","ke","to","pe","la","su",
                # SV (with/without diacritics)
                "måndag","mandag","tisdag","onsdag","torsdag","fredag","lördag","lordag","söndag","sondag",
                "mån","man","må","ma","tis","ti","ons","on","tors","tor","to","fre","fr","lör","lor","lö","lo","sön","son","sö","so",
            }
            if toks & wd:
                lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
                ans = IR.resolve_faq(user_msg, lang)
                if ans:
                    return ans
    except Exception:
        pass

    # opening hours fast-path (avoid misfiring capability phrase on "what are your opening hours")
    HOURS_KWS = [
        "opening hours", "open today", "open now",  # EN
        "aukiolo", "aukioloajat",                    # FI
        "öppettider",                                 # SV
    ]
    if any(k in text for k in HOURS_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        try:
            return IR.resolve_hours(lang)
        except Exception:
            # let downstream handle if router not available
            return None

    # Admin teach UI (hidden command). Accept "/teach" or "teach" after normalization.
    raw = (user_msg or "").strip().lower()
    if raw.startswith("/teach") or text.startswith("teach"):
        # Lightweight HTML form for adding a KB item
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        title = {"fi":"Opeta bottia","sv":"Lär boten","en":"Teach the bot"}[lang]
        submit = {"fi":"Tallenna","sv":"Spara","en":"Save"}[lang]
        q_l = {"fi":"Kysymys","sv":"Fråga","en":"Question"}[lang]
        a_l = {"fi":"Vastaus","sv":"Svar","en":"Answer"}[lang]
        key_l = {"fi":"Ylläpitäjän avain","sv":"Adminnyckel","en":"Admin key"}[lang]
        html = f"""
<div class=\"teach-ui\">
  <div class=\"title\">{title}</div>
  <form class=\"teach-form\">
    <div class=\"row\">
      <select name=\"lang\" required>
        <option value=\"fi\">FI</option>
        <option value=\"sv\">SV</option>
        <option value=\"en\">EN</option>
      </select>
    </div>
    <div class=\"row\"><input type=\"text\" name=\"question\" placeholder=\"{q_l}\" required></div>
    <div class=\"row\"><textarea name=\"answer\" rows=\"3\" placeholder=\"{a_l}\" required></textarea></div>
    <div class=\"row\"><input type=\"password\" name=\"admin_key\" placeholder=\"{key_l}\" required></div>
    <div class=\"actions\"><button type=\"submit\" class=\"btn btn-primary\">{submit}</button></div>
  </form>
  <div class=\"subtle\">This action is restricted to one admin with a secret key.</div>
  </div>
"""
        return html

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
                "Hei, olen Piirakkabotti – Raka's kotileipomon avustaja.\n"
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

    # Diet queries: route directly to dynamic vegan/dairy-free listing
    try:
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        try:
            if IR.detect_intent(user_msg) == "diet":
                return IR.resolve_diet_options(user_msg, lang)
        except Exception:
            pass
    except Exception:
        pass

    # Defer FAQ handling to the intent router so product/diet intents are not overshadowed

    # Delivery vs pickup clarification
    DELIVERY_KWS = {"delivery","deliver","home delivery","toimitus","kotiinkuljetus","kuljetus","leverans"}
    if any(k in text for k in DELIVERY_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        url = ECWID_STORE_URL
        if lang == "sv":
            msg = (
                f"""
<div class=\"order-ui\">
  <div class=\"order-sub\">Vi erbjuder för närvarande ingen leverans. Avhämtning i butiken under öppettider.</div>
  <div class=\"order-title\">Beställ i webbutiken</div>
  <div class=\"order-sub\">Hämta i butiken, betalning på plats.</div>
  <div class=\"order-buttons\">
    <a class=\"btn\" href=\"{url}\" target=\"_blank\" rel=\"noopener\">Öppna webbutiken</a>
    <button class=\"btn\" data-action=\"start-order\">Beställ i chatten</button>
  </div>
</div>
"""
            )
            return _maybe_strip_chat_order_btn(msg)
        if lang == "fi":
            msg = (
                f"""
<div class=\"order-ui\">
  <div class=\"order-sub\">Emme tarjoa toimitusta. Nouto myymälästä aukioloaikoina.</div>
  <div class=\"order-title\">Tilaa verkkokaupasta</div>
  <div class=\"order-sub\">Nouto myymälästä, maksu paikan päällä.</div>
  <div class=\"order-buttons\">
    <a class=\"btn\" href=\"{url}\" target=\"_blank\" rel=\"noopener\">Avaa verkkokauppa</a>
    <button class=\"btn\" data-action=\"start-order\">Tilaa chatissa</button>
  </div>
</div>
"""
            )
            return _maybe_strip_chat_order_btn(msg)
        # en
        return _maybe_strip_chat_order_btn(
            f"""
<div class=\"order-ui\">
  <div class=\"order-sub\">We currently do not offer delivery. Pickup in-store during opening hours.</div>
  <div class=\"order-title\">Order Online</div>
  <div class=\"order-sub\">Pickup in store, pay at pickup.</div>
  <div class=\"order-buttons\">
    <a class=\"btn\" href=\"{url}\" target=\"_blank\" rel=\"noopener\">Open Online Shop</a>
    <button class=\"btn\" data-action=\"start-order\">Order in chat</button>
  </div>
</div>
"""
        )

    # Seating availability (avoid substring collisions like "deposit")
    SEATING_KWS = {"seating","seat","seats","dine","dine-in",
                   "asiakaspaikka","asiakaspaikat","asiakaspaikkoja",
                   "istumapaikka","istumapaikat","istumapaikkoja",
                   "sittplats","sittplatser","servering"}
    if any(k in text for k in SEATING_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return "Vi har inga kundplatser i butiken. Beställ gärna för avhämtning."
        if lang == "fi":
            return "Meillä ei ole asiakaspaikkoja myymälässä. Voit tilata noudettavaksi."
        return "We don’t have customer seating in-store. Please order for pickup."

    # Direct cakes/pies availability (negative policy) — catch generic cake queries first
    CAKE_KWS = {
        # FI
        "kakku", "kakut", "kakkuja", "täytekakku", "kuivakakku", "voileipäkakku", "lihapiirakka", "lihapiirakoita",
        # SV
        "tårta", "tårtor", "smörgåstårta", "köttpirog", "köttpiroger",
        # EN
        "cake", "cakes", "sandwich cake", "meat pie", "meat pies",
    }
    if any(k in text for k in CAKE_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return (
                "Vi bakar inte tårtor (gräddtårtor, sockerkakor), smörgåstårtor, köttpiroger eller konditorivaror. "
                "Vi är i första hand ett karelskt pirogbageri."
            )
        if lang == "fi":
            return (
                "Emme leivo kakkuja (täytekakkuja, kuivakakkuja), voileipäkakkuja, lihapiirakoita tai konditoriatuotteita. "
                "Olemme ensisijaisesti karjalanpiirakkaleipomo."
            )
        return (
            "We don’t bake cakes (layer cakes, loaf cakes), sandwich cakes, meat pies, or confectionery items. "
            "We are primarily a Karelian pie bakery."
        )

    # Custom cakes/pastries request → explain policy + show menu
    CUSTOM_KWS = {
        # EN
        "custom cake","custom cakes","custom pastry","custom pastries","made to order","special order","birthday cake","wedding cake",
        # FI
        "tilauskakku","tilauskakut","tilausleivonnainen","tilausleivonnaiset","mittatilaus","räätälöity","räätälöityjä","kakku tilauksesta",
        "tilaustyö","tilaustyönä","tilaustyöt",
        # SV
        "beställningstårta","tårta på beställning","specialtårta","beställningsbakverk",
    }
    if any(k in text for k in CUSTOM_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            msg = (
                "Vi bakar inte tårtor (gräddtårtor, sockerkakor), smörgåstårtor, köttpiroger eller konditorivaror. "
                "Vi är i första hand ett karelskt pirogbageri. Vi tar dock emot förbeställningar till större fester och evenemang – ur vårt ordinarie sortiment."
            )
            prompt = (
                "<div class=\"suggest\">"
                "<div class=\"title\">Vill du se menyn?</div>"
                "<div class=\"buttons\">"
                "<button type=\"button\" class=\"btn suggest-btn\" data-suggest=\"meny\">Ja</button>"
                "<button type=\"button\" class=\"btn suggest-btn\" data-suggest=\"nej tack\">Nej</button>"
                "</div></div>"
            )
            return f"<div class=\"info\">{msg}</div>" + prompt
        if lang == "fi":
            msg = (
                "Emme leivo kakkuja (täytekakkuja, kuivakakkuja), voileipäkakkuja, lihapiirakoita tai konditoriatuotteita. "
                "Olemme ensisijaisesti karjalanpiirakkaleipomo. Otamme kuitenkin ennakkotilauksia isompiin juhliin ja tilaisuuksiin – valikoimamme tuotteista."
            )
            prompt = (
                "<div class=\"suggest\">"
                "<div class=\"title\">Haluatko nähdä valikon?</div>"
                "<div class=\"buttons\">"
                "<button type=\"button\" class=\"btn suggest-btn\" data-suggest=\"ruokalista\">Kyllä</button>"
                "<button type=\"button\" class=\"btn suggest-btn\" data-suggest=\"ei kiitos\">Ei</button>"
                "</div></div>"
            )
            return f"<div class=\"info\">{msg}</div>" + prompt
        # en
        msg = (
            "We don’t bake cakes (layer cakes, loaf cakes), sandwich cakes, meat pies, or confectionery items. "
            "We are primarily a Karelian pie bakery. However, we do accept preorders for larger events using items from our menu."
        )
        prompt = (
            "<div class=\"suggest\">"
            "<div class=\"title\">Would you like to see our menu?</div>"
            "<div class=\"buttons\">"
            "<button type=\"button\" class=\"btn suggest-btn\" data-suggest=\"menu\">Yes</button>"
            "<button type=\"button\" class=\"btn suggest-btn\" data-suggest=\"no thanks\">No</button>"
            "</div></div>"
        )
        return f"<div class=\"info\">{msg}</div>" + prompt

    # Specific flavors/fillings/designs (no customizations)
    CUSTOMIZE_KWS = {
        # EN
        "specific flavor", "specific flavours", "specific flavors", "specific filling", "fillings", "flavors", "flavours", "design", "designs", "custom flavor", "custom filling", "custom design",
        # FI
        "maku", "maut", "täyte", "täytteet", "suunnittelu", "koristelu", "oma maku", "oma täyte",
        # SV
        "smak", "smaker", "fyllning", "fyllningar", "design", "egen smak", "egen fyllning",
    }
    if any(k in text for k in CUSTOMIZE_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return "Tyvärr tar vi inte emot önskemål om specifika smaker, fyllningar eller designer för tillfället."
        if lang == "fi":
            return "Valitettavasti emme tällä hetkellä ota vastaan pyyntöjä erityisistä mauista, täytteistä tai design‑koristeluista."
        return "Sorry, we do not accept requests for specific flavors, fillings, or designs at the moment."

    # Lead time (how far in advance)
    LEAD_KWS = {
        # EN
        "how far in advance", "how early", "order ahead", "how many days in advance", "lead time",
        # FI
        "kuinka aikaisin", "montako päivää etukäteen", "ennakkoon", "ennakkoon kuinka", "ennakkoon paljonko",
        # SV
        "hur långt i förväg", "hur tidigt", "beställa i förväg", "hur många dagar i förväg",
    }
    if any(k in text for k in LEAD_KWS) or ("kuinka ajoissa" in text) or ("minun tulee tehdä tilaus" in text):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        # Prefer curated FAQ answer if available
        try:
            faq_txt = IR.resolve_faq(user_msg, lang)
            if faq_txt:
                return faq_txt
        except Exception:
            pass
        url = ECWID_STORE_URL
        if lang == "sv":
            note = "Gör din beställning minst 1 dag i förväg och upp till en månad i förväg."
            ui = (
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
            return _maybe_strip_chat_order_btn(f"<div class=\"info\">{note}</div>" + ui)
        if lang == "fi":
            note = "Tee tilaus vähintään 1 päivä etukäteen ja enintään kuukauden päähän."
            ui = (
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
            return _maybe_strip_chat_order_btn(f"<div class=\"info\">{note}</div>" + ui)
        note = "Please place orders at least 1 day in advance and up to a month ahead."
        ui = (
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
        return _maybe_strip_chat_order_btn(f"<div class=\"info\">{note}</div>" + ui)

    # Deposit / prepayment policy
    DEPOSIT_KWS = {
        # EN
        "deposit", "prepayment", "pre-payment", "advance payment",
        # FI
        "ennakkomaksu", "etukäteismaksu", "ennakko", "varausmaksu",
        # SV
        "förskottsbetalning", "deposition", "handpenning",
    }
    if any(k in text for k in DEPOSIT_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        # Prefer curated FAQ answer if available
        try:
            faq_txt = IR.resolve_faq(user_msg, lang)
            if faq_txt:
                return faq_txt
        except Exception:
            pass
        if lang == "sv":
            return "För beställningar över 150 € kräver vi förskottsbetalning."
        if lang == "fi":
            return "Yli 150 €:n tilauksista edellytämme ennakkomaksun."
        return "We require prepayment for orders over €150."

    # Minimum order requirement
    MIN_ORDER_KWS = {
        # EN
        "minimum order", "minimum spend", "min order", "minimum purchase",
        # FI
        "minimitilaus", "minimiosto", "minimiostos",
        # SV
        "minsta beställning", "minsta köp", "minimumorder",
    }
    if any(k in text for k in MIN_ORDER_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        # Prefer curated FAQ answer if available
        try:
            faq_txt = IR.resolve_faq(user_msg, lang)
            if faq_txt:
                return faq_txt
        except Exception:
            pass
        if lang == "sv":
            return "Nej, vi har inget minsta orderbelopp."
        if lang == "fi":
            return "Ei, meillä ei ole minimitilausrajaa."
        return "No, we do not have a minimum order requirement."

    # Payment methods (cards/mobile/cash)
    PAYMENT_KWS = {
        # EN
        "credit card", "debit card", "cards accepted", "visa", "mastercard", "amex", "mobile pay", "mobilepay", "cash", "checks", "contactless",
        # FI
        "kortti", "kortilla", "luottokortti", "pankkikortti", "lähimaksu", "mobilepay", "käteinen", "sekki", "sekkejä",
        # SV
        "kort", "kreditkort", "bankkort", "kontaktlös", "kontaktlöst", "mobilepay", "kontanter", "checkar",
        "betalning", "pay", "payment",
    }
    if any(k in text for k in PAYMENT_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        # Prefer curated FAQ answer if available
        try:
            faq_txt = IR.resolve_faq(user_msg, lang)
            if faq_txt:
                return faq_txt
        except Exception:
            pass
        if lang == "sv":
            return (
                "Vi accepterar ledande debit- och kreditkort med kontaktlös betalning. "
                "Vi accepterar inte MobilePay, kontanter eller checkar."
            )
        if lang == "fi":
            return (
                "Hyväksymme yleisimmät pankki- ja luottokortit lähimaksulla. "
                "Emme hyväksy MobilePayta, käteistä tai shekkejä."
            )
        return (
            "We accept major debit and credit cards with contactless. "
            "We do not accept MobilePay, cash or checks."
        )

    # Loyalty program / newsletter
    LOYALTY_KWS = {
        # EN
        "loyalty", "rewards", "points", "membership", "members club", "newsletter", "mailing list",
        # FI
        "kanta-asiakas", "kantaasiakas", "pisteet", "jäsenyys", "jäsen", "uutiskirje",
        # SV
        "lojalitet", "bonus", "poäng", "medlemskap", "nyhetsbrev",
    }
    if any(k in text for k in LOYALTY_KWS):
        email = "rakaskotileipomo@gmail.com"
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return (
                f"Vi har inget lojalitetsprogram, men du kan mejla oss på {email} för att bli tillagd på vårt (sällan skickade) nyhetsbrev."
            )
        if lang == "fi":
            return (
                f"Meillä ei ole kanta-asiakasohjelmaa, mutta voit lähettää sähköpostia osoitteeseen {email} päästäksesi harvoin lähetettävään uutiskirjeeseemme."
            )
        return (
            f"We do not have a loyalty program, but you can email {email} to be added to our very rarely sent newsletter."
        )

    # Classes / community events
    CLASSES_KWS = {
        # EN
        "baking class", "baking classes", "class", "classes", "workshop", "community event", "events",
        # FI
        "kurssi", "kurssit", "leivontakurssi", "yhteisötilaisuus", "tapahtuma", "tapahtumat",
        # SV
        "kurs", "kurser", "bakningskurs", "evenemang",
    }
    if any(k in text for k in CLASSES_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return "För närvarande ordnar vi inte bakningskurser eller evenemang."
        if lang == "fi":
            return "Tällä hetkellä emme järjestä leivontakursseja tai yhteisötapahtumia."
        return "At the moment we do not host baking classes or community events."

    # Feedback / reviews
    FEEDBACK_KWS = {
        # EN
        "feedback", "review", "reviews", "google review", "leave feedback",
        # FI
        "palaute", "palautetta", "arvostelu", "arvostelut",
        # SV
        "feedback", "omdöme", "recension", "recensioner",
    }
    if any(k in text for k in FEEDBACK_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        link = GOOGLE_REVIEW_URL
        title = {
            "fi": "Anna palaute tai jätä arvostelu",
            "sv": "Lämna feedback eller skriv en recension",
            "en": "Leave feedback or post a review",
        }[lang]
        submit = {"fi": "Lähetä", "sv": "Skicka", "en": "Submit"}[lang]
        name_l = {"fi": "Nimi (valinnainen)", "sv": "Namn (valfritt)", "en": "Name (optional)"}[lang]
        email_l = {"fi": "Sähköposti (valinnainen)", "sv": "E‑post (valfritt)", "en": "Email (optional)"}[lang]
        msg_l = {"fi": "Palaute", "sv": "Feedback", "en": "Feedback"}[lang]
        review_l = {"fi": "Jätä Google‑arvostelu", "sv": "Lämna Google‑recension", "en": "Post Google review"}[lang]
        html = f"""
<div class=\"feedback-ui\">
  <div class=\"title\">{title}</div>
  <form class=\"feedback-form\">
    <div class=\"row\"><input type=\"text\" name=\"name\" placeholder=\"{name_l}\"></div>
    <div class=\"row\"><input type=\"email\" name=\"email\" placeholder=\"{email_l}\"></div>
    <div class=\"row\"><textarea name=\"message\" rows=\"3\" placeholder=\"{msg_l}\" required></textarea></div>
    <div class=\"actions\"><button type=\"submit\" class=\"btn btn-primary\">{submit}</button>
      <a class=\"btn btn-review\" href=\"{link}\" target=\"_blank\" rel=\"noopener\">{review_l}</a></div>
  </form>
</div>
"""
        return html

    # Bulk / wholesale discounts
    BULK_KWS = {
        # EN
        "bulk", "wholesale", "large order", "large orders", "volume discount", "discounts for bulk", "bulk pricing",
        # FI
        "tukku", "isot tilaukset", "suuri tilaus", "määriä", "alennus", "tukkualennus",
        # SV
        "partihandel", "storköp", "större beställning", "volymrabatt", "rabatt",
    }
    if any(k in text for k in BULK_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        email = "rakaskotileipomo@gmail.com"
        if lang == "sv":
            return (
                f"Detta bedöms från fall till fall. Skicka gärna ett e‑postmeddelande till {email} med din förfrågan."
            )
        if lang == "fi":
            return (
                f"Päätämme asiasta tapauskohtaisesti. Lähetä ystävällisesti sähköpostia osoitteeseen {email} ja kerro tarpeestasi."
            )
        return (
            f"This is decided on a case‑by‑case basis. Please email {email} with your query."
        )

    # Gift cards
    GIFT_KWS = {
        # EN
        "gift card", "gift cards", "giftcard", "voucher", "gift voucher",
        # FI
        "lahjakortti", "lahjakortteja", "lahjakorte", "lahja kortti",
        # SV
        "presentkort", "gåvokort", "gavokort",
    }
    if any(k in text for k in GIFT_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return "Vi säljer presentkort med ett minsta belopp på 10 € och de gäller i 6 månader."
        if lang == "fi":
            return "Myymme lahjakortteja; minimisumma on 10 € ja voimassaoloaika 6 kuukautta."
        return "We sell gift cards with a minimum value of €10 and they are valid for 6 months."

    # Price range (per‑piece)
    PRICE_RANGE_KWS = {
        # EN
        "price range", "prices range", "how much do", "how expensive", "what are your prices", "price list",
        # FI
        "hintahaarukka", "hinnat", "hinnasto", "mitä maksaa", "paljonko maksaa",
        # SV
        "prisspann", "prisnivå", "priser", "prislista", "hur mycket kostar",
    }
    if any(k in text for k in PRICE_RANGE_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return "Styckepriserna ligger ungefär mellan 1,20–4,50 € per styck."
        if lang == "fi":
            return "Yksikköhinnat ovat noin 1,20–4,50 € /kpl."
        return "Per‑piece prices range roughly from €1.20 to €4.50."

    # Unsold goods / food waste policy
    DONATION_KWS = {
        # EN
        "donate", "unsold", "leftover", "food waste", "waste", "left over",
        # FI
        "lahjoita", "lahjoitetaanko", "lahjoitukset", "myymättömät", "jääkö yli", "hävikki", "hävikkituotteet",
        # SV
        "donera", "donerar", "osålda", "svinn", "matsvinn",
    }
    if any(k in text for k in DONATION_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return (
                "Vi tror inte på matsvinn. Vi har en ‘svinnfrys’ för osålda produkter: "
                "i slutet av dagen packar vi och fryser in osålda bakverk, och säljer dem sedan till starkt rabatterat pris."
            )
        if lang == "fi":
            return (
                "Emme usko ruokahävikkiin. Meillä on ‘hävikki‑pakastin’ myymättömille tuotteille: "
                "päivän päätteeksi pussitamme ja pakastamme myymättä jääneet leivonnaiset, ja myymme ne sen jälkeen hyvin alennettuun hintaan."
            )
        return (
            "We do not believe in food waste. We keep a ‘food‑waste freezer’ for unsold items: "
            "at the end of the day we bag and freeze any unsold baked goods, then offer them at a very discounted price."
        )

    # Reusable containers policy
    REUSE_KWS = {
        # EN
        "reusable container", "reusable containers", "bring container", "own container", "bring your own container", "byo container",
        # FI
        "uudelleenkäytettävä", "uudelleenkäytettävät", "omat rasiat", "oma rasia", "oma astia", "omat astiat", "tuoda rasia",
        # SV
        "återanvändbar", "återanvändbara", "egen behållare", "egna behållare", "ta med behållare",
    }
    if any(k in text for k in REUSE_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return (
                "Kunder är välkomna att ta med egna återanvändbara behållare. Vi packar gärna våra bakverk i dem."
            )
        if lang == "fi":
            return (
                "Asiakkaat voivat tuoda omat uudelleenkäytettävät rasiat/astiat. Pakkaamme leivonnaiset niihin mielellämme."
            )
        return (
            "Customers are welcome to bring their reusable containers. We will be happy to pack our baked goods in them."
        )

    # Eco‑friendly / recyclable packaging
    PACKAGING_KWS = {
        # EN
        "eco friendly packaging", "eco-friendly packaging", "sustainable packaging", "recyclable packaging", "packaging", "paper bags", "hdpe",
        # FI
        "ekologinen", "ympäristöystävällinen", "kierrätettävä", "kierrätettäviä", "pakkaus", "pakkaukset", "paperipussi", "paperipussit", "leivosrasia", "leivosrasiat", "hdpe",
        # SV
        "miljövänlig", "miljovänlig", "hållbar", "återvinningsbar", "återvinningsbara", "förpackning", "förpackningar", "papperspåse", "papperspåsar", "hdpe",
    }
    if any(k in text for k in PACKAGING_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return (
                "Vi använder endast återvinningsbara papperspåsar och bakelseaskar för våra bakverk. "
                "Frysta produkter packas i återvinningsbara HDPE‑påsar. "
                "Vi erbjuder också bruna take‑away‑papperskassar med tvinnade handtag som är återanvändbara och återvinningsbara."
            )
        if lang == "fi":
            return (
                "Käytämme ainoastaan kierrätettäviä paperipusseja ja leivosrasioita leivonnaisten pakkaamiseen. "
                "Pakasteet pakataan kierrätettäviin HDPE‑pusseihin. "
                "Tarjoamme myös ruskeita kierretyillä kantokahvoilla varustettuja take‑away‑paperikasseja, jotka ovat uudelleenkäytettäviä ja kierrätettäviä."
            )
        return (
            "We use only recyclable paper bags and ‘leivosrasiat’ pastry boxes for our baked items. "
            "Frozen items are packed in recyclable HDPE bags. "
            "We also offer brown take‑away paper bags with twisted handles which are reusable and recyclable."
        )

    # Samples / tasting policy
    SAMPLE_KWS = {
        # EN
        "samples", "sample", "tasting", "taste", "free sample",
        # FI
        "maistiainen", "maistiaiset", "maistella", "maistatuksia", "maistatus",
        # SV
        "smakprov", "smakprover", "provsmakning", "smaka",
    }
    if any(k in text for k in SAMPLE_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return (
                "Vi erbjuder normalt inte smakprov. Men om Raka eller Anssi håller på att skapa en ny bakelse kan något gott erbjudas för provsmakning."
            )
        if lang == "fi":
            return (
                "Emme yleensä tarjoa maistiaisia. Mutta jos Raka tai Anssi on kehittämässä uutta leivonnaista, jotain herkullista voi olla tarjolla maisteltavaksi."
            )
        return (
            "We do not normally offer samples. But if Raka or Anssi is in the middle of creating a new bakery item, something yummy might be on offer for tasting."
        )

    # Phone vs online orders
    PHONE_ONLINE_KWS = {"phone order","phone orders","call order","call in",
                        "puhelin","puhelimitse","soittaa","verkossa",
                        "telefon","ringa",
                        "online order","online orders","webborder","onlinebeställning","onlinebeställningar"}
    if any(k in text for k in PHONE_ONLINE_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        url = ECWID_STORE_URL
        if lang == "sv":
            return (
                f"Vi tar emot webborder. Se webbutiken nedan.\n\n"
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
                f"Otamme vastaan verkkotilauksia. Katso verkkokauppa alta.\n\n"
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
            f"We take online orders. See the online shop below.\n\n"
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

    # Freshly baked daily
    FRESH_KWS = {
        "fresh daily","bake fresh","freshly baked","baked fresh","handmade",
        "paistatko", "tuoreena", "tuore", "paistetaan", "leivotteko", "leivotaan",
        "färskt", "nybakat", "nybakade", "bakas",
    }
    if any(k in text for k in FRESH_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return "Ja – allt vi erbjuder är nybakat och handgjort med kärlek av Anssi och Raka."
        if lang == "fi":
            return "Kyllä – kaikki tuotteemme ovat tuoreita ja käsin tehty rakkaudella Ansin ja Rakan toimesta."
        return "Yes — everything we offer is freshly baked and handmade with love by Anssi and Raka."

    # Made from scratch vs pre‑made mixes
    SCRATCH_KWS = {
        # EN
        "made from scratch", "from scratch", "pre-made", "premade", "pre made", "pre-made mixes", "mixes", "ready mix", "pre mix",
        # FI
        "alusta asti", "käsin tehty", "valmisseos", "valmisseoksia", "esiseos", "valmiseos",
        # SV
        "från grunden", "för hand", "färdiga mixer", "färdigmix", "bakmix", "mixer",
    }
    if any(k in text for k in SCRATCH_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return "Vi gör allting från grunden för hand. Vi använder inga färdiga mixer."
        if lang == "fi":
            return "Teemme kaiken alusta asti käsin. Emme käytä valmisseoksia."
        return "We make everything from scratch by hand. We do not use any pre‑made mixes."

    # Gluten‑free options policy
    GLUTENFREE_KWS = {
        # EN
        "gluten free", "gluten-free", "glutenfree",
        # FI
        "gluteeniton", "gluteenittomia", "gluteenittomat",
        # SV
        "glutenfri", "glutenfritt", "glutenfria",
    }
    if any(k in text for k in GLUTENFREE_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        # Prefer curated FAQ answer if available
        try:
            faq_txt = IR.resolve_faq(user_msg, lang)
            if faq_txt:
                return faq_txt
        except Exception:
            pass
        if lang == "sv":
            return "Tyvärr har vi inte glutenfria alternativ för tillfället."
        if lang == "fi":
            return "Valitettavasti meillä ei ole gluteenittomia vaihtoehtoja tällä hetkellä."
        return "Unfortunately we do not have gluten‑free options at the moment."

    # Nut allergy policy (no nuts in regular products; almonds only for Runebergin torttu)
    # Make matching broad so phrases like "how do you handle nut allergies" hit this path.
    NUT_KWS = {
        # EN
        "nut allergy", "nut allergies", "nut", "nuts", "peanut", "tree nut", "almond", "almonds",
        # FI
        "pähkinäallergia", "pähkinä", "pähkinät", "maapähkinä", "manteli", "manteleita",
        # SV
        "nötallergi", "nöt", "nötter", "jordnöt", "mandel",
    }
    if any(k in text for k in NUT_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        # Prefer FAQ if available for short queries like "pähkinä"
        try:
            faq_txt = IR.resolve_faq(user_msg, lang)
            if faq_txt:
                return faq_txt
        except Exception:
            pass
        if lang == "sv":
            return (
                "Vi använder inte nötter i våra ordinarie produkter. "
                "För Runebergstårta använder vi mandel; inget annat bakas samtidigt och allt rengörs noggrant efteråt."
            )
        if lang == "fi":
            return (
                "Emme käytä pähkinöitä vakiotuotteissamme. "
                "Runebergintortussa käytämme manteleita; sitä valmistettaessa ei tehdä muita tuotteita ja puhdistamme kaiken huolellisesti sen jälkeen."
            )
        return (
            "We do not use nuts in our regular products. "
            "For Runeberg torte we use almonds; nothing else is made alongside it and we clean thoroughly after making the tortes."
        )

    # Request for ingredient/allergen lists (general overview)
    ALLERGEN_LIST_KWS = {
        # EN
        "allergen list", "allergens list", "ingredient list", "ingredients list", "allergen information", "allergen info",
        # FI
        "allergialista", "allergeenilista", "ainesosaluettelo", "ainesosalista", "allergiatiedot", "allergeenitiedot",
        # SV
        "allergenlista", "allergen lista", "ingredienslista", "ingrediens lista", "allergiinformation",
    }
    if any(k in text for k in ALLERGEN_LIST_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return (
                "Vanliga allergener vi använder: mjölk, gluten (vete/råg/korn) och ägg. "
                "Vi hanterar spannmål och mejeriprodukter i bageriet; korskontaminering kan inte helt uteslutas."
            )
        if lang == "fi":
            return (
                "Yleisimmät allergeenit joita käytämme: maito, gluteeni (vehnä/ruis/ohra) ja kananmuna. "
                "Käsittelemme leipomossa viljaa ja maitotuotteita; ristikontaminaatiota ei voida täysin poissulkea."
            )
        return (
            "Common allergens we handle: milk, gluten (wheat/rye/barley) and egg. "
            "We handle cereals and dairy in the bakery; cross‑contamination cannot be fully excluded."
        )

    # Seasonal / special items
    SEASONAL_KWS = {
        # EN
        "seasonal", "season", "special items", "rotate", "rotating", "changing menu", "limited",
        # FI
        "kausi", "sesonki", "sesonkituote", "kausituote", "vaihtuva", "erikois",
        # SV
        "säsong", "säsongs", "byter", "special", "begränsad",
    }
    if any(k in text for k in SEASONAL_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        if lang == "sv":
            return (
                "Ja, vi erbjuder säsongs‑ och specialprodukter såsom Runebergstårta, fastlagsbulle, rabarberpaj, bärpaj och mer."
            )
        if lang == "fi":
            return (
                "Kyllä, meillä on kausituotteita ja erikoistuotteita kuten Runebergin torttu, laskiaispulla, raparperipiirakka, marjapiirakka ja paljon muuta."
            )
        return (
            "Yes, we rotate seasonal and special items such as Runeberg torte, Shrove bun (laskiaispulla), rhubarb pie, berry pie and more."
        )

    # Local / organic ingredients policy (and local farmers/suppliers)
    SOURCING_KWS = {
        # EN
        "local ingredients", "locally sourced", "organic", "organics", "use local", "from finland",
        "local farmers", "support local", "local supplier", "local suppliers", "wholesaler", "supplier", "suppliers",
        # FI
        "luomu", "lähiruoka", "lähituote", "suomalaiset raaka-aineet", "suomalaisia raaka-aineita",
        "lähituottaja", "lähituottajat", "paikallinen tuottaja", "paikalliset tuottajat", "tukku", "tukkukauppa", "toimittaja", "toimittajat",
        # SV
        "ekologisk", "ekologiska", "ekologiskt", "inhemska", "finska råvaror",
        "lokala bönder", "lokala leverantörer", "leverantör", "leverantörer", "grossist",
    }
    if any(k in text for k in SOURCING_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        # Prefer explicit FAQ content if configured for this topic
        try:
            faq_txt = IR.resolve_faq(user_msg, lang)
            if faq_txt:
                return faq_txt
        except Exception:
            pass
        # Fallback to curated default message
        if lang == "sv":
            return (
                "Vi använder främst finländska råvaror som mjölk, råg, smör, grädde och ägg i våra produkter. "
                "Vi köper huvudsakligen via en familjeägd finländsk grossist och vårt rågmjöl kommer från Helsingin Mylly. "
                "Vi använder inte certifierade ekologiska ingredienser."
            )
        if lang == "fi":
            return (
                "Käytämme tuotteissamme pääosin suomalaisia raaka‑aineita, kuten maitoa, ruista, voita, kermaa ja kananmunia. "
                "Ostamme raaka‑aineita pääasiassa suomalaiselta perheomisteiselta tukkutoimittajalta ja ruisjauhomme tulee Helsingin Myllyltä. "
                "Emme käytä sertifioituja luomuraaka‑aineita."
            )
        return (
            "We use mostly Finnish ingredients like milk, rye, butter, cream and eggs in our products. "
            "We mainly buy through a family‑owned Finnish wholesaler, and our rye flour comes from Helsingin Mylly. "
            "We do not use certified organic ingredients."
        )

    # Pre‑order to skip the line (explicit question)
    SKIPLINE_KWS = {
        # EN
        "skip the line", "skip line", "preorder to skip", "pre-order to skip",
        # FI (include inflections)
        "ohittaa jonon", "ohitan jonon", "jonon ohittamiseksi", "jonon ohitus",
        "ennakkotilaus jonon", "ennakkotilauksen", "ennakkotilaus", "ennakkoon tilata jono",
        # SV
        "gå förbi kön", "förbeställa för att", "förbeställ för att",
    }
    if any(k in text for k in SKIPLINE_KWS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        url = ECWID_STORE_URL
        if lang == "sv":
            note = "Du kan förbeställa för att gå förbi kön. Gå bara till kassan och visa din orderbekräftelse."
            ui = (
                f"""
<div class=\"order-ui\">\n  <div class=\"order-title\">Beställ i webbutiken</div>\n  <div class=\"order-sub\">Hämta i butiken, betalning på plats.</div>\n  <div class=\"order-buttons\">\n    <a class=\"btn\" href=\"{url}\" target=\"_blank\" rel=\"noopener\">Öppna webbutiken</a>\n    <button class=\"btn\" data-action=\"start-order\">Beställ i chatten</button>\n  </div>\n</div>\n"""
            )
            return _maybe_strip_chat_order_btn(f"<div class=\"info\">{note}</div>" + ui)
        if lang == "fi":
            note = "Voit tehdä ennakkotilauksen ja ohittaa jonon. Tule kassalle ja näytä tilausvahvistus sähköpostistasi."
            ui = (
                f"""
<div class=\"order-ui\">\n  <div class=\"order-title\">Tilaa verkkokaupasta</div>\n  <div class=\"order-sub\">Nouto myymälästä, maksu paikan päällä.</div>\n  <div class=\"order-buttons\">\n    <a class=\"btn\" href=\"{url}\" target=\"_blank\" rel=\"noopener\">Avaa verkkokauppa</a>\n    <button class=\"btn\" data-action=\"start-order\">Tilaa chatissa</button>\n  </div>\n</div>\n"""
            )
            return _maybe_strip_chat_order_btn(f"<div class=\"info\">{note}</div>" + ui)
        note = "You can preorder to skip the line. Just come to the cashier and show your confirmation email."
        ui = (
            f"""
<div class=\"order-ui\">\n  <div class=\"order-title\">Order Online</div>\n  <div class=\"order-sub\">Pickup in store, pay at pickup.</div>\n  <div class=\"order-buttons\">\n    <a class=\"btn\" href=\"{url}\" target=\"_blank\" rel=\"noopener\">Open Online Shop</a>\n    <button class=\"btn\" data-action=\"start-order\">Order in chat</button>\n  </div>\n</div>\n"""
        )
        return _maybe_strip_chat_order_btn(f"<div class=\"info\">{note}</div>" + ui)

    # Ordering intent → link to Ecwid store (pickup, pay in store)
    if any(k in text for k in ORDER_KEYWORDS):
        lang = respond_lang or (PRIMARY_LANG if LANGUAGE_POLICY == "always_primary" else detect_lang(user_msg))
        url = ECWID_STORE_URL
        if lang == "sv":
            return _maybe_strip_chat_order_btn(
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
            return _maybe_strip_chat_order_btn(
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
        return _maybe_strip_chat_order_btn(
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

# --- Intent router Ecwid adapter wiring ---
try:
    IR.ecwid.get_products = _ecwid_get_products
    IR.ecwid.get_categories = _ecwid_get_categories
    IR.ecwid.get_order_constraints = (lambda debug=False: api_order_constraints(debug=debug))
    IR.ecwid.is_blackout = _is_blackout
except Exception:
    pass

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
    # Lightweight small‑talk handler so fun questions get a friendly answer
    def _small_talk(q: str, lang: str) -> str | None:
        t = _normalize(q)
        if lang not in {"fi","sv","en"}:
            lang = "en"
        who_kws = {
            "fi": ["kuka sinä olet", "kuka olet", "mikä sinä olet", "mika sina olet"],
            "sv": ["vem är du", "vem ar du"],
            "en": ["who are you", "what are you"]
        }
        hello_kws = {
            "fi": ["hei", "moikka", "moi", "terve"],
            "sv": ["hej", "hejsan"],
            "en": ["hi", "hello", "hey"]
        }
        thanks_kws = {
            "fi": ["kiitos", "kiitti"],
            "sv": ["tack"],
            "en": ["thanks", "thank you"]
        }
        def _any(keys):
            return any(k in t for k in keys)
        if _any(who_kws.get(lang, [])):
            if lang == "fi":
                return "Olen Piirakkabotti – Raka's kotileipomon avustaja. Voin auttaa tuotteista, aukioloajoista, menusta, tilauksista ja allergioista."
            if lang == "sv":
                return "Jag är Piirakkabotti – assistent för Raka's kotileipomo. Jag hjälper med produkter, öppettider, meny, beställningar och allergier."
            return "I'm Piirakkabotti – the assistant for Raka's kotileipomo. I can help with products, hours, menu, orders and allergies."
        if _any(hello_kws.get(lang, [])):
            if lang == "fi":
                return "Hei! Miten voin auttaa?"
            if lang == "sv":
                return "Hej! Hur kan jag hjälpa till?"
            return "Hi! How can I help today?"
        if _any(thanks_kws.get(lang, [])):
            if lang == "fi":
                return "Ole hyvä! Tarvitsetko muuta?"
            if lang == "sv":
                return "Varsågod! Behöver du något mer?"
            return "You’re welcome! Anything else I can help with?"
        return None

    toks = list(_tokens(query))
    has_overlap = any(t in DF for t in toks)
    if not kb_items or not has_overlap:
        lang = (respond_lang or PRIMARY_LANG)
        small = _small_talk(query, lang)
        if small:
            return small
        if lang == "fi":
            return (
                f"En löytänyt tietoja aiheesta “{query}”. "
                "Voin auttaa leipomoon liittyvissä asioissa, kuten tuotteet, aukioloajat, menu, tilaukset ja allergiat. "
                "Kokeile kysyä: “Mitkä ovat aukioloajat?”, “Voinko tilata etukäteen?”, tai “Karjalanpiirakan ainesosat?”."
            )
        if lang == "sv":
            return (
                f"Jag kunde inte hitta information om “{query}”. "
                "Jag kan hjälpa till med bagerifrågor som produkter, öppettider, meny, beställningar och allergier. "
                "Prova att fråga: ”Vilka är öppettiderna?”, ”Kan jag förbeställa?” eller ”Ingredienser för Karjalanpiirakka?”."
            )
        else:
            return (
                f"I couldn’t find details about “{query}”. "
                "I can help with bakery topics like products, opening hours, menu, orders, and allergies. "
                "Try asking: “What are your opening hours?”, “Can I preorder?”, or “What are the ingredients?”."
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
        "You are Piirakkabotti, a helpful assistant for Raka's kotileipomo bakery in Helsinki. "
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

    # 0) Priority: exact KB match (taught items) should override rules
    try:
        matches0 = find_best_kb_match(user_msg, top_k=5)
    except Exception:
        matches0 = []
    if matches0:
        nq = _normalize(user_msg)
        for blend, bm25, fuzzy, jacc, it in matches0:
            if _normalize(it.get("question") or "") == nq:
                ans = (it.get("answer") or "").strip()
                if ans:
                    try:
                        _db_insert_message(session_id, "assistant", ans, "KB", float(blend))
                    except Exception:
                        pass
                    return ChatResponse(reply=ans, source="KB", match=float(blend), session_id=session_id)
        # No exact match; continue to rules intent, then later general KB retrieval

    # 1) Rules first
    rb = rule_based_answer(user_msg, respond_lang)
    if rb:
        try:
            _db_insert_message(session_id, "assistant", rb, "Rules", 1.0)
        except Exception:
            pass
        return ChatResponse(reply=rb, source="Rules", match=1.0)

    # 1.5) Deterministic intent router for menu/hours/allergens/FAQ/blackouts
    try:
        routed = IR.answer(user_msg, respond_lang)
    except Exception:
        routed = None
    if routed:
        try:
            _db_insert_message(session_id, "assistant", routed, "Intent", 1.0)
        except Exception:
            pass
        return ChatResponse(reply=routed, source="Intent", match=1.0, session_id=session_id)

    # 2) Retrieval from taught KB (DB), then friendly fallback
    # Try to find best matches from current KB index
    matches = find_best_kb_match(user_msg, top_k=5)
    reply = None
    src = "Fallback"
    best_score = 0.0
    if matches:
        blend, bm25, fuzzy, jacc, best_item = matches[0]
        # Acceptance gates
        if (blend >= MIN_ACCEPT_SCORE) and (bm25 >= MIN_BM25_SIGNAL or jacc >= MIN_JACCARD or fuzzy >= MIN_FUZZY):
            # Compose answer from top items if LLM enabled; else return best answer
            kb_items = [m[4] for m in matches]
            if LLM_ENABLED and OPENAI_CLIENT:
                reply = generate_llm_answer(user_msg, kb_items, respond_lang=respond_lang or PRIMARY_LANG)
                src = "KB • LLM"
            else:
                reply = (best_item.get("answer") or "").strip() or None
                src = "KB"
            best_score = float(blend)
    if not reply:
        # Deterministic out-of-scope friendly fallback
        kb_items: List[Dict[str, Any]] = []
        intent = infer_intent(user_msg)
        kb_items = filter_items_for_intent(intent, kb_items)
        if LLM_ENABLED and OPENAI_CLIENT:
            reply = generate_llm_answer(user_msg, kb_items, respond_lang=respond_lang or PRIMARY_LANG)
            src = "LLM • Fallback"
        else:
            reply = llm_like_answer(user_msg, kb_items, respond_lang or PRIMARY_LANG)
            src = "Fallback"
    try:
        _db_insert_message(session_id, "assistant", reply, src, best_score)
    except Exception:
        pass
    return ChatResponse(reply=reply, source=src, match=best_score, session_id=session_id)

# Simple feedback endpoint (logs to DB if available)
@app.post("/api/feedback")
def api_feedback(payload: FeedbackPayload, request: Request):
    try:
        session_id = request.cookies.get("chat_session")
    except Exception:
        session_id = None
    msg = payload.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Feedback message cannot be empty.")
    try:
        _db_insert_message(session_id, "feedback", f"name={payload.name or ''}; email={payload.email or ''}; msg={msg}", "feedback", None)
        _db_insert_feedback(session_id, payload.name, payload.email, msg)
    except Exception:
        pass
    return {"ok": True}

# ---------------------------
# Admin helpers / endpoints
# ---------------------------
def _is_admin(request: Request, body_key: str | None = None) -> bool:
    if not ADMIN_KEY:
        return False
    try:
        hdr = request.headers.get("x-admin-key")
    except Exception:
        hdr = None
    if hdr and hdr == ADMIN_KEY:
        return True
    if body_key and body_key == ADMIN_KEY:
        return True
    try:
        sid = request.cookies.get("chat_session") or ""
    except Exception:
        sid = ""
    return (sid in ADMIN_SESSIONS)

class TeachPayload(BaseModel):
    lang: str | None = None
    question: str
    answer: str
    admin_key: str | None = None
    category: str | None = None

@app.post("/api/kb/add")
def api_kb_add(payload: TeachPayload, request: Request):
    if not _is_admin(request, payload.admin_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    q = (payload.question or "").strip()
    a = (payload.answer or "").strip()
    if not q or not a:
        raise HTTPException(status_code=400, detail="question and answer are required")
    lang = (payload.lang or PRIMARY_LANG).strip().lower()
    sid = None
    try:
        sid = request.cookies.get("chat_session")
    except Exception:
        pass
    new_id = _db_kb_insert(lang, q, a, created_by=sid or "api", category=(payload.category or None))
    if not new_id:
        raise HTTPException(status_code=500, detail="Failed to insert KB item")
    _refresh_kb_index()
    return {"ok": True, "id": new_id}

@app.get("/api/kb/list")
def api_kb_list(request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"items": _db_kb_list(limit=500)}

class TogglePayload(BaseModel):
    id: int
    enabled: bool

@app.post("/api/kb/toggle")
def api_kb_toggle(payload: TogglePayload, request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    _db_kb_toggle(int(payload.id), bool(payload.enabled))
    _refresh_kb_index()
    return {"ok": True}

@app.get("/api/feedback_queue")
def api_feedback_queue(request: Request, status: str = "pending", limit: int = 100):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"items": _db_feedback_list(status=status, limit=limit)}

class PromotePayload(BaseModel):
    id: int
    lang: str
    question: str
    answer: str
    category: str | None = None

@app.post("/api/feedback/promote")
def api_feedback_promote(payload: PromotePayload, request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    q = (payload.question or "").strip()
    a = (payload.answer or "").strip()
    if not q or not a:
        raise HTTPException(status_code=400, detail="question and answer are required")
    new_id = _db_kb_insert(payload.lang.strip().lower(), q, a, created_by="promotion", category=(payload.category or None))
    if not new_id:
        raise HTTPException(status_code=500, detail="Failed to insert KB item")
    _db_feedback_set_status(int(payload.id), "promoted")
    _refresh_kb_index()
    return {"ok": True, "kb_id": new_id}

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
    # Feature flag to disable in‑chat ordering
    if (os.getenv("ENABLE_CHAT_ORDERING", "false").lower() in {"0","false","no","off"}):
        raise HTTPException(status_code=403, detail="Ordering is disabled")
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
        # If the day is closed, it might be due to a blackout; prefer explicit blackout wording
        try:
            cons = api_order_constraints(debug=False)
            dt = _parse_pickup_iso(req.pickup_time)
            if dt and _is_blackout(dt, cons.get("blackout_dates") or []):
                raise HTTPException(status_code=400, detail="Pickup date is not available (blackout).")
        except HTTPException:
            raise
        except Exception:
            pass
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
        _refresh_kb_index()
    else:
        # Legacy KB disabled: keep deterministic intent router only
        KB = []

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
