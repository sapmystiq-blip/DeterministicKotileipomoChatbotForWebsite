from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from pydantic import ValidationError
from difflib import SequenceMatcher

from .kb_models import WeeklyHours, FaqItem, AllergenMap, ProductAliases, Settings


HERE = Path(__file__).resolve().parent
KB_DIR = HERE / "knowledgebase"

# Simple in-memory cache for Ecwid calls
_CACHE: Dict[str, Tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 120.0

def _cache_get(key: str) -> Optional[Any]:
    import time
    ent = _CACHE.get(key)
    if not ent:
        return None
    ts, val = ent
    if (time.time() - ts) > _CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return val

def _cache_set(key: str, val: Any) -> None:
    import time
    _CACHE[key] = (time.time(), val)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_weekly_hours() -> WeeklyHours:
    f = KB_DIR / "hours.json"
    data = _read_json(f) or {"hours": {}, "exceptions": {}, "notes": {}}
    try:
        return WeeklyHours.parse_obj(data)
    except ValidationError:
        # fallback to empty
        return WeeklyHours(hours={}, exceptions={}, notes={})


def load_faq() -> List[FaqItem]:
    f = KB_DIR / "faq.json"
    data = _read_json(f) or []
    out: List[FaqItem] = []
    if isinstance(data, list):
        for row in data:
            try:
                out.append(FaqItem.parse_obj(row))
            except ValidationError:
                continue
    return out


def load_settings() -> Settings:
    f = KB_DIR / "settings.json"
    data = _read_json(f) or {}
    try:
        return Settings.parse_obj(data)
    except Exception:
        return Settings()


def load_allergens() -> AllergenMap:
    f = KB_DIR / "allergens.json"
    data = _read_json(f) or {"items": []}
    try:
        return AllergenMap.parse_obj(data)
    except ValidationError:
        return AllergenMap(items=[])


def load_product_aliases() -> ProductAliases:
    f = KB_DIR / "product_aliases.json"
    data = _read_json(f) or {"items": []}
    try:
        return ProductAliases.parse_obj(data)
    except ValidationError:
        return ProductAliases(items=[])


def _load_instore_prices() -> Dict[str, float]:
    f = KB_DIR / "instore_prices.json"
    data = _read_json(f) or {}
    out: Dict[str, float] = {}
    try:
        for it in data.get("prices", []):
            k = ((it.get("key") or "").strip().lower())
            v = it.get("per_piece_eur")
            if k and isinstance(v, (int, float)):
                out[k] = float(v)
    except Exception:
        pass
    return out


def _dow_name(lang: str, dow: int) -> str:
    names = {
        "fi": ["maanantai","tiistai","keskiviikko","torstai","perjantai","lauantai","sunnuntai"],
        "sv": ["måndag","tisdag","onsdag","torsdag","fredag","lördag","söndag"],
        "en": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
    }
    return (names.get(lang) or names["en"])[dow]


def format_hours_response(hours: WeeklyHours, lang: str) -> str:
    # Render compact weekly schedule (Thu, Fri, Sat)
    spans_by_dow: Dict[int, List[str]] = {}
    for dow in [3, 4, 5]:  # Thu, Fri, Sat common for this bakery
        blocks = hours.hours.get(str(dow)) or []
        if not blocks:
            continue
        spans_by_dow[dow] = [f"{b.start}-{b.end}" for b in blocks]

    # If no hours found, return a generic message
    if not spans_by_dow:
        if lang == "fi":
            return "Aukioloaikoja ei ole asetettu. Ota yhteyttä liikkeeseen."
        if lang == "sv":
            return "Öppettider har inte angetts. Kontakta butiken."
        return "Opening hours are not set. Please contact the shop."

    # Finnish: Prefer a single sentence like the requested phrasing
    if lang == "fi":
        def _short(span: str) -> str:
            # Convert 11:00-17:00 -> 11-17, but keep minutes if needed
            try:
                a, b = span.split("-")
                def s(x: str) -> str:
                    return x.replace(":00", "")
                return f"{s(a)}-{s(b)}"
            except Exception:
                return span
        thu = ", ".join(spans_by_dow.get(3, [])) if 3 in spans_by_dow else None
        fri = ", ".join(spans_by_dow.get(4, [])) if 4 in spans_by_dow else None
        sat = ", ".join(spans_by_dow.get(5, [])) if 5 in spans_by_dow else None
        if thu and fri and sat:
            thu_s = _short(thu)
            fri_s = _short(fri)
            sat_s = _short(sat)
            if thu_s == fri_s:
                return f"Olemme avoinna torstaisin ja perjantaisin klo {thu_s} ja lauantaisin klo {sat_s}."
            else:
                return f"Olemme avoinna torstaisin klo {thu_s}, perjantaisin klo {fri_s} ja lauantaisin klo {sat_s}."
        # Fallback to list formatting when incomplete
        lines = [f"{_dow_name(lang, d)}: {', '.join(spans_by_dow[d])}" for d in sorted(spans_by_dow.keys())]
        return "Aukioloajat:\n" + "\n".join(lines)

    # Swedish: natural sentence if Thu/Fri/Sat are present
    def _sv_span(span: str) -> str:
        # 11:00-17:00 -> 11–17 (en dash), keep minutes if needed
        try:
            a, b = span.split("-")
            def s(x: str) -> str:
                return x.replace(":00", "")
            return f"{s(a)}–{s(b)}"
        except Exception:
            return span
    if lang == "sv":
        thu = ", ".join(spans_by_dow.get(3, [])) if 3 in spans_by_dow else None
        fri = ", ".join(spans_by_dow.get(4, [])) if 4 in spans_by_dow else None
        sat = ", ".join(spans_by_dow.get(5, [])) if 5 in spans_by_dow else None
        if thu and fri and sat:
            thu_s = _sv_span(thu)
            fri_s = _sv_span(fri)
            sat_s = _sv_span(sat)
            if thu_s == fri_s:
                # Requested phrasing
                return f"Vi har öppet på torsdagar och fredagar kl. {thu_s} samt på lördagar kl. {sat_s}."
            else:
                return f"Vi har öppet på torsdagar kl. {thu_s}, fredagar kl. {fri_s} samt på lördagar kl. {sat_s}."
        # Fallback to compact list
        lines = [f"{_dow_name(lang, d)}: {', '.join(spans_by_dow[d])}" for d in sorted(spans_by_dow.keys())]
        return "Öppettider:\n" + "\n".join(lines)

    # English: natural sentence if Thu/Fri/Sat are present
    def _en_ampm(span: str) -> str:
        # 11:00-17:00 -> 11 am to 5 pm
        try:
            a, b = span.split("-")
            def ampm(x: str) -> str:
                hh, mm = x.split(":") if ":" in x else (x, "00")
                h = int(hh)
                m = int(mm)
                suf = "am" if h < 12 else "pm"
                h12 = h % 12
                if h12 == 0:
                    h12 = 12
                if m == 0:
                    return f"{h12} {suf}"
                return f"{h12}:{mm} {suf}"
            return f"{ampm(a)} to {ampm(b)}"
        except Exception:
            return span.replace("-", " to ")
    if lang == "en":
        thu = ", ".join(spans_by_dow.get(3, [])) if 3 in spans_by_dow else None
        fri = ", ".join(spans_by_dow.get(4, [])) if 4 in spans_by_dow else None
        sat = ", ".join(spans_by_dow.get(5, [])) if 5 in spans_by_dow else None
        if thu and fri and sat:
            thu_s = _en_ampm(thu)
            fri_s = _en_ampm(fri)
            sat_s = _en_ampm(sat)
            if thu_s == fri_s:
                # Requested phrasing
                return f"We are open on Thursdays and Fridays from {thu_s}, and on Saturdays from {sat_s}."
            else:
                return f"We are open on Thursdays from {thu_s}, Fridays from {fri_s}, and on Saturdays from {sat_s}."
        # Fallback to compact list
        lines = [f"{_dow_name(lang, d)}: {', '.join(spans_by_dow[d])}" for d in sorted(spans_by_dow.keys())]
        return "Opening hours:\n" + "\n".join(lines)

    # Default: compact list for other languages
    lines = [f"{_dow_name(lang, d)}: {', '.join(spans_by_dow[d])}" for d in sorted(spans_by_dow.keys())]
    return "Opening hours:\n" + "\n".join(lines)


def detect_intent(text: str) -> Optional[str]:
    t = text.lower().strip()
    # Opening hours
    if any(k in t for k in ["opening", "hours", "auki", "öppet", "open today", "open now", "aukiolo"]):
        return "hours"
    # Blackout / closed on date (holiday)
    if any(k in t for k in ["closed", "holiday", "pyhä", "kiinni", "blackout"]):
        return "blackout"
    # Menu / products (also catch "pakaste/frozen/fryst" to toggle frozen view)
    if any(k in t for k in [
        "menu", "meny", "ruokalista",
        # English
        "product", "products", "bread", "breads", "pastry", "pastries", "cake", "cakes", "bakes", "frozen",
        # Swedish
        "produkt", "produkter", "bröd", "bakverk", "kakor", "fryst",
        # Finnish
        "tuote", "tuotteet", "valikoima", "pakaste", "pakasteet",
        "leipä", "leivät", "leipiä",
        "leivonnainen", "leivonnaiset", "leivonnaisia",
        "kakku", "kakut", "kakkuja",
        # Generic phrases
        "what do you sell", "hinnat", "prices", "priser"
    ]):
        return "menu"
    # Allergens / ingredients (product detail if product is mentioned)
    if any(k in t for k in [
        # EN
        "allergen", "allergy", "contains", "ingredient", "ingredients",
        # FI
        "aines", "ainekset", "ainnekset", "ainesosat", "koostumus", "sisältö",
        "maito", "pähkin", "gluteeni",
        # SV
        "ingrediens", "ingredienser", "innehåll", "innehaller", "innehåller",
        "sammansättning", "sammansattning", "mjölk", "mjolk", "nöt", "nötter",
        # Generic stems
        "aller", "gluten", "nuts", "milk"
    ]):
        # product-specific if any alias present (compact, space-insensitive)
        def _compact(s: str) -> str:
            return re.sub(r"[^a-z0-9]+", "", s.lower())
        cq = _compact(t)
        aliases = load_product_aliases()
        for term in aliases.all_terms():
            if _compact(term) and _compact(term) in cq:
                return "product_detail"
        return "allergens"
    # Dietary filters (vegan / lactose-free / dairy-free)
    if any(k in t for k in [
        # EN
        "vegan", "dairy free", "dairy-free", "lactose free", "lactose-free",
        # FI
        "vegaani", "vegaaninen", "laktoositon", "maidoton",
        # SV
        "vegansk", "laktosfri", "mjölkfri", "mjolkfri",
    ]):
        return "diet"
    # FAQ (orders, pickup, contact, address/location)
    if any(k in t for k in [
        # Orders / pickup / contact
        "order", "preorder", "pickup", "nouto", "tilaa", "contact", "payment", "maksu", "store",
        # Address / location (EN/FI/SV)
        "address", "adress", "location", "sijainti", "sijaitse",
        "where are you located", "where is your shop", "where is the shop", "shop address", "store address",
        "missä sijaitsette", "missä olette", "var ligger", "var finns", "butikens adress",
        # Seasonal products / offers (route to FAQ)
        "kausituote", "kausituotteet", "kausi tuote", "kausi tuotteet", "kausi tuotteita", "sesonki", "sesonkituote", "erikoistarjou"
    ]):
        return "faq"
    # Product mention only → suggest follow‑ups
    cq = re.sub(r"[^a-z0-9]+", "", t)
    if len(cq) >= 3:
        aliases = load_product_aliases()
        for term in aliases.all_terms():
            tt = re.sub(r"[^a-z0-9]+", "", term.lower())
            if tt and tt in cq:
                return "product_suggest"
    return None


class EcwidAdapter:
    """Thin adapter to call functions provided in app.py without circular import.
    The app will inject callables at startup.
    """

    get_products: Optional[Any] = None
    get_categories: Optional[Any] = None
    get_order_constraints: Optional[Any] = None
    is_blackout: Optional[Any] = None


ecwid = EcwidAdapter()


def _price_str(price: Any) -> Optional[str]:
    try:
        if price is None:
            return None
        val = float(price)
        return f"{val:.2f} €"
    except Exception:
        return None


def resolve_menu(lang: str, query: Optional[str] = None) -> str:
    if not ecwid.get_products:
        if lang == "fi":
            return "Voin auttaa tuotteissa ja hinnoissa. Tutustu tuotteisiin verkkokaupassa."
        if lang == "sv":
            return "Jag kan hjälpa till med produkter och priser. Se produkter i webbutiken."
        return "I can help with products and prices. See products in the online store."
    # Try to order by categories: Uunituoreet first, then Pakasteet, then others
    cats: List[Dict[str, Any]] = []
    try:
        cats = _get_categories_cached(limit=200)
    except Exception:
        cats = []
    def _norms(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip().lower())
    uuni_ids: List[int] = []
    pakaste_ids: List[int] = []
    other_ids: List[int] = []
    for c in cats:
        nm = _norms(c.get("name") or "")
        cid = c.get("id")
        if not isinstance(cid, int):
            continue
        if re.search(r"uunituoreet", nm):
            uuni_ids.append(cid)
        elif re.search(r"pakaste", nm):
            pakaste_ids.append(cid)
        else:
            other_ids.append(cid)

    # Include descendant categories (products are often placed in subcategories)
    if cats:
        by_parent: Dict[int, List[int]] = {}
        for c in cats:
            pid = c.get("parentId")
            cid = c.get("id")
            if isinstance(cid, int) and isinstance(pid, int):
                by_parent.setdefault(pid, []).append(cid)

        def _with_descendants(root_ids: List[int]) -> List[int]:
            out: List[int] = []
            seen: set[int] = set()
            stack = list(root_ids)
            while stack:
                nid = stack.pop()
                if not isinstance(nid, int) or nid in seen:
                    continue
                seen.add(nid)
                out.append(nid)
                for ch in by_parent.get(nid, []):
                    if isinstance(ch, int) and ch not in seen:
                        stack.append(ch)
            return out

        uuni_ids = _with_descendants(uuni_ids) if uuni_ids else []
        pakaste_ids = _with_descendants(pakaste_ids) if pakaste_ids else []

    def _render_group(cat_id: int) -> List[str]:
        try:
            grp_items = _get_products_cached(limit=200, category=cat_id)
        except Exception:
            grp_items = []
        lines: List[str] = []
        for it in grp_items:
            if not it.get("enabled", True):
                continue
            name = it.get("name") or ""
            price = _price_str(it.get("price"))
            lines.append(f"• {name}" + (f" — {price}" if price else ""))
        return lines

    # If we have Uunituoreet/Pakasteet categories, render columns
    if uuni_ids or pakaste_ids:
        instore = _load_instore_prices()
        def _collect(cat_ids: List[int], max_items: int | None = None) -> List[str]:
            out: List[str] = []
            for cid in cat_ids:
                lines = _render_group(cid)
                for ln in lines:
                    out.append(ln)
                    if max_items is not None and len(out) >= max_items:
                        return out
            return out

        id_to_name = {c.get("id"): (c.get("name") or "") for c in cats}
        # Derive display names (use first matching category name)
        uuni_name_fi = next((id_to_name.get(cid, "Uunituoreet") for cid in uuni_ids), "Uunituoreet")
        paka_name_fi = next((id_to_name.get(cid, "Pakasteet") for cid in pakaste_ids), "Pakasteet")
        uuni_name = {"fi": uuni_name_fi, "sv": "Ugnsfärskt", "en": "Oven-fresh"}[lang]
        paka_name = {"fi": paka_name_fi, "sv": "Fryst", "en": "Frozen"}[lang]

        # Helpers to clean labels and add simple translations
        def _clean_label(s: str):
            import re as _re
            raw = s or ""
            # Extract and remove piece count like ", 10 kpl" or "10 kpl"
            count = None
            m = _re.search(r"(,\s*)?(\d+)\s*kpl\b", raw, flags=_re.IGNORECASE)
            if m:
                count = m.group(2)
                raw = (raw[:m.start()] + raw[m.end():]).strip()
            # Remove descriptors like ", paistettu" and lactose markers in parentheses
            raw = _re.sub(r",\s*paistettu\b", "", raw, flags=_re.IGNORECASE)
            # Keep vegan markers; only strip lactose/laktos parentheticals
            raw = _re.sub(r"\(([^)]*?(lakto[^)]*|laktos[^)]*)[^)]*?)\)", "", raw, flags=_re.IGNORECASE)
            raw = _re.sub(r"\s{2,}", " ", raw).strip().strip(", ")
            return raw, count

        def _name_translation(fi_name: str) -> str | None:
            nm = (fi_name or "").lower()
            mapping_en = {
                "karjalanpiirakka": "Karelian pie",
                "perunapiirakka": "Potato pie",
                "ohrapiirakka": "Barley pie",
                "vegaanipiirakka": "Vegan pie",
                "marjapiirakka": "Berry pie",
                "raparperipiirakka": "Rhubarb pie",
                "riisipiirakka": "Rice pie",
                "gobi-samosa": "Gobi (cauliflower) samosa",
                "kanasamosa": "Chicken samosa",
                "mungcurry-twist": "Mung curry twist",
                "lihacurry-pasteija": "Meat curry pastry",
                "mustikkakukko": "Blueberry pie",
                "kanelisolmupulla": "Cinnamon bun",
                "voisilmäpulla": "Butter bun",
            }
            for k, v in mapping_en.items():
                if k in nm:
                    return v
            return None

        def _name_translation_sv(fi_name: str) -> str | None:
            nm = (fi_name or "").lower()
            mapping_sv = {
                "karjalanpiirakka": "Karelsk pirog",
                "perunapiirakka": "Potatispirog",
                "ohrapiirakka": "Kornpirog",
                "vegaanipiirakka": "Vegansk pirog",
                "marjapiirakka": "Bärpaj",
                "raparperipiirakka": "Rabarberpaj",
                "riisipiirakka": "Rispirog",
                "gobi-samosa": "Gobi (blomkål)-samosa",
                "kanasamosa": "Kycklingsamosa",
                "mungcurry-twist": "Mungcurry-twist",
                "lihacurry-pasteija": "Köttcurrypaj",
                "mustikkakukko": "Blåbärspaj",
                "kanelisolmupulla": "Kanelbulle",
                "voisilmäpulla": "Smörbulle",
            }
            for k, v in mapping_sv.items():
                if k in nm:
                    return v
            return None

        def _name_translation_fi(fi_name: str) -> str | None:
            nm = (fi_name or "").lower()
            mapping_fi = {
                "gobi-samosa": "Gobi (kukkakaali)-samosa",
            }
            for k, v in mapping_fi.items():
                if k in nm:
                    return v
            return None

        def _fmt_item(name: str, price: str | None, include_instore: bool, *, is_frozen: bool = False, is_sweet: bool | None = None, suppress_frozen_suffix: bool = False) -> str:
            import re as _re
            base, count = _clean_label(name)
            # Build label per language without bracketed translations, preserving raakapakaste
            en_name = _name_translation(base)
            sv_name = _name_translation_sv(base)
            has_vegan = bool(_re.search(r"\(\s*vega", base, flags=_re.IGNORECASE))
            # Keep raakapakaste tag if present, translate per language
            has_raakapakaste = "raakapakaste" in (base or "").lower()
            # Build base localized label without forced frozen marker
            fi_local = _name_translation_fi(base)
            if lang == "en" and en_name:
                label = en_name + (" (vegan)" if has_vegan else "")
            elif lang == "sv" and sv_name:
                label = sv_name + (" (vegansk)" if has_vegan else "")
            elif lang == "fi" and fi_local:
                label = fi_local + (" (vegaani)" if has_vegan else "")
            else:
                label = base

            # Normalize any existing marker tokens in the source label
            marker_map = {"fi": "raakapakaste", "sv": "råfryst", "en": "raw-frozen"}
            # For specific frozen Indian snacks, add a chilli next to the item name (before the marker)
            nm_l_pre = (base or "").lower()
            if is_frozen and ("gobi-samosa" in nm_l_pre or "kanasamosa" in nm_l_pre):
                label = f"{label} 🌶️"
            # For frozen view: ensure marker present unless explicitly suppressed
            if is_frozen and not suppress_frozen_suffix:
                # Remove any existing variants to avoid duplication
                label = _re.sub(r"\b(raakapakaste|råfryst|raw[\- ]?frozen)\b", "", label, flags=_re.IGNORECASE)
                label = _re.sub(r"\s{2,}", " ", label).strip().strip(", ")
                label = f"{label} {marker_map[lang]}".strip()
            # For suppressed cases (grouped frozen pies), remove marker if present
            if is_frozen and suppress_frozen_suffix:
                label = _re.sub(r"\b(raakapakaste|råfryst|raw[\- ]?frozen)\b", "", label, flags=_re.IGNORECASE)
                label = _re.sub(r"\s{2,}", " ", label).strip().strip(", ")

            # For frozen (pakasteet) view, remove commas from product names entirely
            if not include_instore:
                label = label.replace(",", " ")
                label = _re.sub(r"\s{2,}", " ", label).strip()
            # In-store per-piece price
            nm_l = (base or "").lower()
            p_each = None
            for k, val in _load_instore_prices().items():
                if k in nm_l:
                    p_each = val
                    break
            def _fmt_eur(v: float, lc: str) -> str:
                # Consistent euro formatting across locales: trailing €, no space; trim .00
                is_int = abs(v - round(v)) < 1e-9
                if lc in ("fi", "sv"):
                    s = (f"{v:.2f}" if not is_int else f"{int(round(v))}").replace('.', ',')
                    return f"{s}€"
                # English: also trailing € for consistency
                s = f"{v:.2f}" if not is_int else f"{int(round(v))}"
                return f"{s}€"

            def _normalize_price_str(p: str) -> str:
                if not p:
                    return p
                raw = p.replace('€', '').strip()
                raw = raw.replace(',', '.')
                try:
                    val = float(raw)
                    return _fmt_eur(val, lang)
                except Exception:
                    # Fallback: remove space before euro sign if present
                    return p.replace(' €', '€').strip()
            unit_each = {"fi": "/kpl", "sv": "/st", "en": "/each"}[lang]
            unit_pack = {"fi": "/kpl", "sv": "/st", "en": "/pcs"}[lang]
            lines: list[str] = []
            # Exception: Mustikkakukko shows only per-piece price for oven-fresh (include_instore=True)
            if include_instore and "mustikkakukko" in nm_l:
                if p_each is not None:
                    lines.append(f"{_fmt_eur(p_each, lang)} {unit_each}")
            else:
                if include_instore and p_each is not None:
                    lines.append(f"{_fmt_eur(p_each, lang)} {unit_each}")
                if price and count:
                    lines.append(f"{_normalize_price_str(price)} /{count} {unit_pack.split('/')[-1]}")
            price_html = "".join(f"<div class=\"pl\">{ln}</div>" for ln in lines) if lines else (f"<div class=\"pl\">{price}</div>" if price else "")
            return f"<div class=\"item\"><div class=\"nm\">{label}</div>{price_html}</div>"

        # Classify FI product names into savory vs sweet
        def _is_sweet(fi_nm: str) -> bool:
            nm = (fi_nm or "").lower()
            sweet_kw = ["mustikka", "pulla", "kaneli", "voisilmä", "kakku", "kukko", "sokeri"]
            return any(k in nm for k in sweet_kw)

        def _collect_fmt_split(cat_ids: List[int], include_instore: bool) -> tuple[list[str], list[str]]:
            savory: list[str] = []
            sweet: list[str] = []
            for cid in cat_ids:
                try:
                    grp_items = _get_products_cached(limit=200, category=cid)
                except Exception:
                    grp_items = []
                for it in grp_items:
                    if not it.get("enabled", True):
                        continue
                    nm = it.get("name") or ""
                    pr = _price_str(it.get("price"))
                    is_sw = _is_sweet(nm)
                    formatted = _fmt_item(nm, pr, include_instore=include_instore, is_frozen=(not include_instore), is_sweet=is_sw, suppress_frozen_suffix=False)
                    (sweet if is_sw else savory).append(formatted)
            return savory, sweet

        uuni_savory, uuni_sweet = _collect_fmt_split(uuni_ids, include_instore=True)
        paka_savory, paka_sweet = _collect_fmt_split(pakaste_ids, include_instore=False)
        title = {"fi": "Tuotteet ja hinnat", "sv": "Produkter och priser", "en": "Products and prices"}[lang]
        lf_note = {
            "fi": "Kaikki tuotteemme ovat laktoosittomia.",
            "sv": "Alla våra produkter är laktosfria.",
            "en": "All our products are lactose‑free.",
        }[lang]
        # Bold the lactose‑free keyword in each language
        if lang == "fi":
            lf_note = lf_note.replace("laktoosittomia", "<strong>laktoosittomia</strong>")
        elif lang == "sv":
            lf_note = lf_note.replace("laktosfria", "<strong>laktosfria</strong>")
        else:
            # Match both ASCII hyphen and non‑breaking hyphen in the source text
            import re as _re
            lf_note = _re.sub(r"lactose[\-\u2011]free", r"<strong>lactose-free</strong>", lf_note, flags=_re.IGNORECASE)
        # Determine which view to render by query keywords
        qn = (query or "").lower()
        want_pakaste = any(k in qn for k in [
            "pakaste", "pakasteet", "pakaste tuotteet",
            "frozen", "frozen goodies",
            "fryst", "frysta", "frysta delikatesser", "frysta godsaker"
        ])

        # Build a two-column layout for a single group (Savory left, Sweet right)
        def _two_col_only(cat_label: str, savory_items: List[str], sweet_items: List[str], savory_html: Optional[str] = None) -> str:
            s_header = {"fi": "Suolaiset", "sv": "Salta", "en": "Savory"}[lang]
            m_header = {"fi": "Makeat",   "sv": "Söta",  "en": "Sweet"}[lang]
            s_html = savory_html if savory_html is not None else ("".join([f"<li>{ln}</li>" for ln in savory_items]) or "<li>—</li>")
            m_html = "".join([f"<li>{ln}</li>" for ln in sweet_items]) or "<li>—</li>"
            return (
                f"<div class=\"menu-two-col\" style=\"display:grid;grid-template-columns:1fr;gap:6px;align-items:start;width:100%;\">"
                f"<div class=\"title\" style=\"grid-column:1/-1;font-weight:700;margin:0;\">{title}</div>"
                f"<div class=\"note\" style=\"grid-column:1/-1;color:#6b5e57;font-size:12px;margin:0 0 1px 0;\">{lf_note}</div>"
                f"<div class=\"cat center\" style=\"grid-column:1/-1;text-align:center;margin:0 0 1px 0;font-size:19px;font-weight:700\">{cat_label}</div>"
                f"<div class=\"cols\" style=\"grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:start;\">"
                  f"<div class=\"col\"><div class=\"subcat\"><strong>{s_header}</strong></div></div>"
                  f"<div class=\"col\"><div class=\"subcat\"><strong>{m_header}</strong></div></div>"
                  f"<div class=\"cols-body\" style=\"grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:start;\">"
                    f"<div class=\"col\"><ul class=\"items\">{s_html}</ul></div>"
                    f"<div class=\"col\"><ul class=\"items\">{m_html}</ul></div>"
                  f"</div>"
                f"</div>"
                f"</div>"
            )

        # Build grouped savory content for Uunituoreet: Piirakat and Intialaiset with shared prices
        def _mk_group_li(title: str, items: List[str], price_lines: List[str]) -> str:
            # Localize subsubcategory labels; show one chilli next to the Indian snacks label
            base = (title or "").strip().lower()
            if base == "piirakat":
                label = {"fi": "Piirakat", "sv": "Karelska piroger", "en": "Karelian pies"}[lang]
            elif base == "intialaiset":
                base_label = {"fi": "Intialaiset herkut", "sv": "Indiska delikatesser", "en": "Indian snacks"}[lang]
                label = f"{base_label} 🌶️"
            else:
                label = title
            inner = "".join(f"<li>{x}</li>" for x in items)
            prices = "".join(f"<div class=\"pl\">{pl}</div>" for pl in price_lines)
            # Place prices before the items list
            return f"<li><div class=\"subsubcat\"><strong>{label}</strong></div>{prices}<ul class=\"items\">{inner}</ul></li>"

        savory_uuni_group_html: Optional[str] = None
        if not want_pakaste and (uuni_savory or uuni_sweet):
            # Re-collect savory uuni items without per-item prices for grouped sets
            pies_keys = ["karjalanpiirakka","perunapiirakka","ohrapiirakka","vegaanipiirakka"]
            indian_keys = ["gobi-samosa","kanasamosa","mungcurry-twist","lihacurry-pasteija"]
            grp_pies: list[str] = []
            grp_ind: list[str] = []
            other_savory: list[str] = []
            # Local helpers to format group prices consistently and per-language
            def _fmt_eur_group(v: float) -> str:
                # Trailing € for all locales; fi/sv use comma decimal
                is_int = abs(v - round(v)) < 1e-9
                if lang in ("fi", "sv"):
                    s = (f"{v:.2f}" if not is_int else f"{int(round(v))}").replace('.', ',')
                    return f"{s}€"
                s = f"{v:.2f}" if not is_int else f"{int(round(v))}"
                return f"{s}€"
            unit_each_map = {"fi": "/kpl", "sv": "/st", "en": "/each"}
            unit_pack_map = {"fi": "/kpl", "sv": "/st", "en": "/pcs"}
            for cid in uuni_ids:
                try:
                    grp_items = _get_products_cached(limit=200, category=cid)
                except Exception:
                    grp_items = []
                for it in grp_items:
                    if not it.get("enabled", True):
                        continue
                    nm = (it.get("name") or "").lower()
                    pr = _price_str(it.get("price"))
                    # Only collect savory items here; skip sweets entirely from savory column
                    if _is_sweet(nm):
                        continue
                    # Build no-price version for grouped items; normal for others
                    if any(k in nm for k in pies_keys):
                        grp_pies.append(_fmt_item(it.get("name") or "", None, include_instore=False, is_frozen=False, is_sweet=False))
                    elif any(k in nm for k in indian_keys):
                        grp_ind.append(_fmt_item(it.get("name") or "", None, include_instore=False, is_frozen=False, is_sweet=False))
                    else:
                        other_savory.append(_fmt_item(it.get("name") or "", pr, include_instore=True, is_frozen=False, is_sweet=False))
            parts: list[str] = []
            if grp_pies:
                pies_lines = [
                    f"{_fmt_eur_group(1.40)} {unit_each_map[lang]}",
                    f"{_fmt_eur_group(12)} /10 {unit_pack_map[lang].split('/')[-1]}"
                ]
                parts.append(_mk_group_li("Piirakat", grp_pies, pies_lines))
            if grp_ind:
                ind_lines = [
                    f"{_fmt_eur_group(2.90)} {unit_each_map[lang]}",
                    f"{_fmt_eur_group(10)} /4 {unit_pack_map[lang].split('/')[-1]}"
                ]
                parts.append(_mk_group_li("Intialaiset", grp_ind, ind_lines))
            # Append any remaining savory items flat
            parts.extend([f"<li>{x}</li>" for x in other_savory])
            savory_uuni_group_html = "".join(parts) if parts else None

        # Build grouped savory content for Pakasteet: 10-pack pies under a single subsubcategory
        savory_paka_group_html: Optional[str] = None
        if want_pakaste and (paka_savory or paka_sweet):
            pies_keys = ["karjalanpiirakka","perunapiirakka","ohrapiirakka","vegaanipiirakka"]
            grp_pies: list[str] = []
            other_savory_paka: list[str] = []
            paka_top_items: list[str] = []  # e.g., Karjalanpiirakka 20 kpl priced item above the group
            def _fmt_eur_local(v: float) -> str:
                is_int = abs(v - round(v)) < 1e-9
                if lang in ("fi", "sv"):
                    s = (f"{v:.2f}" if not is_int else f"{int(round(v))}").replace('.', ',')
                    return f"{s}€"
                s = f"{v:.2f}" if not is_int else f"{int(round(v))}"
                return f"{s}€"
            unit_pack = {"fi": "/kpl", "sv": "/st", "en": "/pcs"}[lang]
            for cid in pakaste_ids:
                try:
                    grp_items = _get_products_cached(limit=200, category=cid)
                except Exception:
                    grp_items = []
                for it in grp_items:
                    if not it.get("enabled", True):
                        continue
                    nm = (it.get("name") or "").lower()
                    # skip sweets from savory grouping
                    if _is_sweet(nm):
                        continue
                    if any(k in nm for k in pies_keys):
                        # Karjalanpiirakka 20 kpl stays as a separate item above the group
                        if re.search(r"\b20\s*kpl\b", nm) and "karjalanpiirakka" in nm:
                            pr = _price_str(it.get("price"))
                            paka_top_items.append(_fmt_item(it.get("name") or "", pr, include_instore=False, is_frozen=True, is_sweet=False, suppress_frozen_suffix=False))
                        elif re.search(r"\b20\s*kpl\b", nm):
                            pr = _price_str(it.get("price"))
                            other_savory_paka.append(_fmt_item(it.get("name") or "", pr, include_instore=False, is_frozen=True, is_sweet=False, suppress_frozen_suffix=False))
                        else:
                            grp_pies.append(_fmt_item(it.get("name") or "", None, include_instore=False, is_frozen=True, is_sweet=False, suppress_frozen_suffix=True))
                    else:
                        pr = _price_str(it.get("price"))
                        other_savory_paka.append(_fmt_item(it.get("name") or "", pr, include_instore=False, is_frozen=True, is_sweet=False, suppress_frozen_suffix=False))
            parts: list[str] = []
            # Put the Karjalanpiirakka 20 kpl (and any other top items) first
            parts.extend([f"<li>{x}</li>" for x in paka_top_items])
            if grp_pies:
                price_line = f"{_fmt_eur_local(10.90)} /10 {unit_pack.split('/')[-1]}"
                group_title = {
                    "fi": "Raakapakaste 10 kpl piirakkaa",
                    "sv": "Råfryst 10 st piroger",
                    "en": "Raw-frozen 10 pies",
                }[lang]
                parts.append(_mk_group_li(group_title, grp_pies, [price_line]))
            parts.extend([f"<li>{x}</li>" for x in other_savory_paka])
            savory_paka_group_html = "".join(parts) if parts else None

        # Render either Uunituoreet (default) or Pakasteet based on query
        html = (
            _two_col_only(paka_name, paka_savory, paka_sweet, savory_html=savory_paka_group_html)
            if want_pakaste
            else _two_col_only(uuni_name, uuni_savory, uuni_sweet, savory_html=savory_uuni_group_html)
        )

        # Add minimal styles and optional action to show frozen items
        html += (
            "<style>"
            ".menu-two-col, .menu-two-col *{box-sizing:border-box}"
            ".menu-two-col .cols-body{position:relative}"
            ".menu-two-col .cols-body::before{content:'';position:absolute;top:0;bottom:0;left:calc(50% + 6px);border-left:1px solid #e7ddd4}"
            ".menu-two-col .items{margin:1px 0 0;padding-left:0;list-style:none;font-size:12px;line-height:1.2}"
            ".menu-two-col .items li{margin:2px 0 4px 10px;}"
            ".menu-two-col .cat{margin-top:0;margin-bottom:1px;font-size:19px;font-weight:700}"
            ".menu-two-col .subcat{margin-top:1px;margin-bottom:0;font-size:15px;font-weight:600}"
            ".menu-two-col .subsubcat{margin:4px 0 2px;font-size:14px;font-weight:700}"
            ".menu-two-col .col{min-width:0}"
            ".menu-two-col .item .nm{font-size:14px;font-weight:600;margin-bottom:1px;word-break:break-word;overflow-wrap:anywhere}"
            ".menu-two-col .item .pl{font-size:12px;color:#6b5e57;word-break:break-word;overflow-wrap:anywhere}"
            ".menu-two-col .col + .col{padding-left:0}"
            "@media (max-width: 420px){.menu-two-col{grid-template-columns:1fr}.menu-two-col .cols-body::before{display:none}.menu-two-col .col + .col{border-left:0;padding-left:0;border-top:1px solid #e7ddd4;padding-top:8px}}"
            "</style>"
        )

        # When rendering the default Uunituoreet view, append a suggestion button to show frozen items
        if not want_pakaste and (paka_savory or paka_sweet):
            frozen_btn = {"fi": "Pakaste tuotteet", "sv": "Frysta delikatesser", "en": "Frozen goodies"}[lang]
            html += (
                "<div class=\"suggest\" style=\"margin-top:8px\">"
                "<div class=\"buttons\">"
                f"<button type=\"button\" class=\"btn suggest-btn\" data-suggest=\"{frozen_btn}\">{frozen_btn}</button>"
                "</div>"
                "</div>"
            )
        return html

    # Fallback to flat list if no categories/groups were rendered
    sections: List[str] = []
    title = {"fi": "Tuotteet ja hinnat:", "sv": "Produkter och priser:", "en": "Products and prices:"}[lang]
    sections.append(title)
    if True:
        try:
            items = _get_products_cached(limit=50)
        except Exception:
            items = []
        if not items:
            if lang == "fi":
                return "Voin auttaa tuotteissa ja hinnoissa. Tuotelista ei ole saatavilla juuri nyt. Katso verkkokauppa."
            if lang == "sv":
                return "Jag kan hjälpa till med produkter och priser. Produktlistan är inte tillgänglig just nu. Se webbutiken."
            return "I can help with products and prices. Product list is not available right now. See the online store."
        keep: List[str] = []
        for it in items:
            if not it.get("enabled", True):
                continue
            name = it.get("name") or ""
            price = _price_str(it.get("price"))
            keep.append(f"• {name}" + (f" — {price}" if price else ""))
            if len(keep) >= 8:
                break
        sections.extend(keep)
    return "\n".join(sections)


def _get_products_cached(limit: int = 100, category: Optional[int] = None) -> List[Dict[str, Any]]:
    if not ecwid.get_products:
        return []
    key = f"products:{limit}:{category}"
    hit = _cache_get(key)
    if hit is not None:
        return hit
    try:
        items = ecwid.get_products(limit=limit, category=category)
    except Exception:
        items = []
    _cache_set(key, items)
    return items


def _get_categories_cached(limit: int = 200) -> List[Dict[str, Any]]:
    if not ecwid.get_categories:
        return []
    key = f"categories:{limit}"
    hit = _cache_get(key)
    if hit is not None:
        return hit
    try:
        cats = ecwid.get_categories(limit=limit)
    except Exception:
        cats = []
    _cache_set(key, cats)
    return cats


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _find_product_by_name_or_alias(query: str, items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not items:
        return None
    q = _norm(query)
    def _compact(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", s.lower())
    cq = _compact(query)
    # Build alias → canonical map
    pa = load_product_aliases().items
    canonical_from_hit: Optional[str] = None
    for entry in pa:
        terms = [entry.name] + list(entry.aliases)
        for term in terms:
            if (_norm(term) and _norm(term) in q) or (_compact(term) and _compact(term) in cq):
                canonical_from_hit = _norm(entry.name)
                break
        if canonical_from_hit:
            break
    # If we matched an alias/canonical, choose best product by similarity to the user's query,
    # with a lightweight boost when the product name contains the canonical label. This avoids
    # hardcoded variant tokens and relies on actual Ecwid product names.
    if canonical_from_hit:
        best: Tuple[float, Dict[str, Any]] | None = None
        for it in items:
            name = _norm(it.get("name") or "")
            base = 1.0 if canonical_from_hit in name else 0.0
            sim = SequenceMatcher(None, name, q).ratio()
            score = base * 2.0 + sim
            if best is None or score > best[0]:
                best = (score, it)
        return best[1] if best else None
    # Otherwise, try to use query similarity to product names
    best: Tuple[float, Dict[str, Any]] | None = None
    for it in items:
        name = _norm(it.get("name") or "")
        sim = SequenceMatcher(None, name, q).ratio()
        if best is None or sim > best[0]:
            best = (sim, it)
    return best[1] if best else None


def _extract_attr_text(it: Dict[str, Any], keys: List[str]) -> Optional[str]:
    # Ecwid returns custom attributes typically under 'attributes'
    attrs = it.get("attributes") or []
    for a in attrs:
        name = (a.get("name") or a.get("title") or "").lower()
        val = (a.get("value") or a.get("text") or "").strip()
        if any(k in name for k in keys) and val:
            return val
    return None


def _strip_html(text: str) -> str:
    if not text:
        return ""
    # remove tags
    return re.sub(r"<[^>]+>", " ", text)


def _extract_bold_segments(html: str) -> List[str]:
    out: List[str] = []
    for m in re.finditer(r"<(b|strong)[^>]*>(.*?)</\1>", html, flags=re.IGNORECASE | re.DOTALL):
        seg = re.sub(r"\s+", " ", m.group(2)).strip()
        if seg:
            out.append(seg)
    return out


def _extract_ingredients_from_description(desc_html: str) -> Optional[str]:
    if not desc_html:
        return None
    text = _strip_html(desc_html)
    # Support both Finnish and English labels
    labels = ["ainesosat", "ingredients", "ingredienser"]
    for label in labels:
        m = re.search(rf"(?i){re.escape(label)}\s*[:\-]?\s*(.+)", text)
        if not m:
            continue
        tail = m.group(1).strip()
        # Cut off at known boundaries
        boundaries = [
            "ravintosisältö",  # Finnish Nutrition
            "nutrition", "nutritional values",
            "ingredients", "ainesosat",  # another label occurrence
            "storage", "säilytys",
            "allergens", "aller",
            "\n\n", "\n", "\r"
        ]
        low = tail.lower()
        cut_idx = None
        for b in boundaries:
            i = low.find(b)
            if i != -1:
                cut_idx = i if cut_idx is None else min(cut_idx, i)
        if cut_idx is not None:
            tail = tail[:cut_idx].strip()
        # Trim trailing punctuation artifacts
        tail = tail.strip(" .;:,\n\r")
        if tail:
            return tail
    return None


def _detect_allergens_fi(text: str) -> List[str]:
    """Heuristic detection for Finnish allergen tokens.
    Returns canonical keys: milk, gluten, egg.
    Avoids 'kookoskerma' false positive for milk.
    """
    if not text:
        return []
    t = _strip_html(text).lower()
    toks = re.findall(r"[a-zåäöA-ZÅÄÖ]+", t)
    toks_set = set(toks)
    out: List[str] = []
    # Milk
    milk_terms = {"maito", "voi", "kerma", "piima", "piimä", "täysmaitojuoma"}
    # Exclude coconut-cream false positive
    if "kookoskerma" in t:
        milk_terms = milk_terms - {"kerma"}
    if toks_set & milk_terms:
        out.append("milk")
    # Gluten (cereals containing gluten)
    if toks_set & {"vehnä", "vehnäjauho", "ruis", "ohra"}:
        out.append("gluten")
    # Egg
    if toks_set & {"muna", "kananmuna", "kananmunia"}:
        out.append("egg")
    # Bold-marked segments: check them specifically
    for seg in _extract_bold_segments(text):
        s = seg.lower()
        if any(w in s for w in ["maito", "voi", "kerma"]) and "milk" not in out:
            if "kookoskerma" not in s:
                out.append("milk")
        if any(w in s for w in ["vehn", "ruis", "ohra"]) and "gluten" not in out:
            out.append("gluten")
        if any(w in s for w in ["muna", "kananmuna"]) and "egg" not in out:
            out.append("egg")
    return out

def _detect_allergens_sv(text: str) -> List[str]:
    if not text:
        return []
    t = _strip_html(text).lower()
    toks = re.findall(r"[a-zåäöA-ZÅÄÖ]+", t)
    toks_set = set(toks)
    out: List[str] = []
    # Milk/dairy
    milk_terms = {"mjölk", "mjolk", "grädde", "gradde", "smör", "smor", "yoghurt", "yogurt"}
    if toks_set & milk_terms:
        out.append("milk")
    # Gluten cereals
    if toks_set & {"vete", "vetemjöl", "vetemjol", "råg", "rag", "korn"}:
        out.append("gluten")
    # Egg
    if "ägg" in toks_set or "agg" in toks_set:
        out.append("egg")
    # Bold-marked segments
    for seg in _extract_bold_segments(text):
        s = seg.lower()
        if any(w in s for w in ["mjölk", "mjolk", "grädde", "gradde", "smör", "smor"]) and "milk" not in out:
            out.append("milk")
        if any(w in s for w in ["vete", "vetemjöl", "vetemjol", "råg", "rag", "korn"]) and "gluten" not in out:
            out.append("gluten")
        if any(w in s for w in ["ägg", "agg"]) and "egg" not in out:
            out.append("egg")
    return out


def resolve_product_detail(query: str, lang: str) -> Optional[str]:
    items = _get_products_cached(limit=100)
    if not items:
        return None
    it = _find_product_by_name_or_alias(query, items)
    if not it:
        return None
    name = it.get("name") or "Product"
    ing_keys = ["ingredients", "aines", "ainesosat"]
    all_keys = ["allergens", "aller", "allerg"]
    ingredients = _extract_attr_text(it, ing_keys) or _extract_ingredients_from_description(it.get("description") or "")
    allergens = _extract_attr_text(it, all_keys)
    def _clean_product_name(n: str) -> str:
        # Drop trailing price dashes and piece counts like "— 19.90 €" or ", 20 kpl"
        n = re.split(r"\s+[–—]-?\s+", n)[0]
        n = re.sub(r",?\s*\b\d+\s*(kpl|pcs)\b", "", n, flags=re.IGNORECASE)
        n = re.sub(r"\s{2,}", " ", n).strip().strip(", ")
        return n

    name = _clean_product_name(name)

    lines: List[str] = []
    header = name  # do not append price
    lines.append(header)
    def _normalize_ingredient_terms_fi(s: str) -> str:
        t = re.sub(r"\s+", " ", s).strip()
        # Join common compounds that sometimes break due to HTML/formatting
        t = re.sub(r"\btäys\s*maito\s*juoma\b", "täysmaitojuoma", t, flags=re.IGNORECASE)
        t = re.sub(r"\bruis\s*jauho\b", "ruisjauho", t, flags=re.IGNORECASE)
        t = re.sub(r"\bvehnä\s*jauho\b", "vehnäjauho", t, flags=re.IGNORECASE)
        t = re.sub(r"\brypsi\s*öljy\b", "rypsiöljy", t, flags=re.IGNORECASE)
        return t

    def _translate_ingredients_list(s: str, lang_code: str) -> str:
        if not s:
            return s
        base = _normalize_ingredient_terms_fi(s)
        if lang_code == "fi":
            return base
        # Simple dictionary-based translation for common terms
        fi_en = {
            "vesi": "Water",
            "laktoositon": "Lactose-free",
            "täysmaitojuoma": "whole milk",
            "vehnäjauho": "Wheat flour",
            "ruisjauho": "Rye flour",
            "puuroriisi": "Porridge-rice",
            "riisi": "Rice",
            "suola": "Salt",
            "sokeri": "Sugar",
            "voi": "Butter",
            "maito": "Milk",
            "kerma": "Cream",
            "kasvimargariini": "Vegetable margarine",
            "rapsi": "Rapeseed",
            "palmu": "Palm",
            "kookos": "Coconut",
            "rypsiöljy": "Rapeseed oil",
            "inkivääri": "Ginger",
            "mausteet": "Spices",
            "kukkakaali": "Cauliflower",
            "lisäaineeton": "Additive-free",
            "perunahiutale": "Potato flakes",
            "kana": "Chicken",
            "jogurtti": "Yogurt",
            "sipuli": "Onion",
            "valkosipuli": "Garlic",
        }
        fi_sv = {
            "vesi": "Vatten",
            "laktoositon": "Laktosfri",
            "täysmaitojuoma": "helmjölksdryck",
            "vehnäjauho": "Vetemjöl",
            "ruisjauho": "Rågmjöl",
            "puuroriisi": "Grötris",
            "riisi": "Ris",
            "suola": "Salt",
            "sokeri": "Socker",
            "voi": "Smör",
            "maito": "Mjölk",
            "kerma": "Grädde",
            "kasvimargariini": "Vegetabiliskt margarin",
            "rapsi": "Raps",
            "palmu": "Palm",
            "kookos": "Kokos",
            "rypsiöljy": "Rapsolja",
            "inkivääri": "Ingefära",
            "mausteet": "Kryddor",
            "kukkakaali": "Blomkål",
            "lisäaineeton": "Tillsatsfri",
            "perunahiutale": "Potatisflingor",
            "kana": "Kyckling",
            "jogurtti": "Yoghurt",
            "sipuli": "Lök",
            "valkosipuli": "Vitlök",
        }
        mapping = fi_en if lang_code == "en" else fi_sv
        def _match_first_letter_case(src: str, dst: str) -> str:
            # Match the case of the first alphabetic character from src to dst
            src_upper = None
            for ch in src:
                if ch.isalpha():
                    src_upper = ch.isupper()
                    break
            if src_upper is None:
                return dst
            dst_list = list(dst)
            for i, ch in enumerate(dst_list):
                if ch.isalpha():
                    dst_list[i] = ch.upper() if src_upper else ch.lower()
                    break
            return "".join(dst_list)
        parts = [p.strip() for p in re.split(r",\s*", base) if p.strip()]
        out: List[str] = []
        for p in parts:
            # Try phrase mapping first
            low = p.lower()
            if low == "laktoositon täysmaitojuoma":
                phrase = "Lactose-free whole milk" if lang_code == "en" else "Laktosfri helmjölksdryck"
                out.append(_match_first_letter_case(p, phrase))
                continue
            if low == "laktoositon jogurtti":
                phrase = "Lactose-free yogurt" if lang_code == "en" else "Laktosfri yoghurt"
                out.append(_match_first_letter_case(p, phrase))
                continue
            if low in mapping:
                out.append(_match_first_letter_case(p, mapping[low]))
                continue
            # Token-map words within the phrase
            def _map_token(word: str) -> str:
                m = re.match(r"^([^A-Za-zÅÄÖåäö]*)([A-Za-zÅÄÖåäö]+)([^A-Za-zÅÄÖåäö]*)$", word)
                if not m:
                    return word
                pre, core, post = m.groups()
                dst_core = mapping.get(core.lower(), core)
                dst_core = _match_first_letter_case(core, dst_core)
                return f"{pre}{dst_core}{post}"
            words = re.split(r"\s+", p)
            trans = [_map_token(w) for w in words]
            out.append(" ".join(trans))
        return ", ".join(out)

    if ingredients:
        ing_render = _translate_ingredients_list(ingredients, lang)
        heading = {"fi": "Ainesosat:", "sv": "Ingredienser:", "en": "Ingredients:"}[lang]
        lines.append(f"<strong>{heading}</strong> {ing_render}")
    if allergens:
        heading_all = {"fi": "Allergeenit:", "sv": "Allergener:", "en": "Allergens:"}[lang]
        lines.append(f"<strong>{heading_all}</strong> {allergens}")
    else:
        # Try to infer allergens heuristically from description/ingredients (FI + SV tokens)
        desc = it.get("description") or ""
        text_block = desc + "\n" + (ingredients or "")
        inferred_fi = _detect_allergens_fi(text_block)
        inferred_sv = _detect_allergens_sv(text_block)
        inferred = []
        for k in (inferred_fi + inferred_sv):
            if k not in inferred:
                inferred.append(k)
        # Vegan hint: if product name/description indicates vegan, suppress milk and egg
        name_l = (name or "").lower()
        if any(tag in (name_l + " " + desc.lower()) for tag in ["vegaani", "vegan"]):
            inferred = [k for k in inferred if k not in ("milk", "egg")]
        if inferred:
            name_map = {
                "fi": {"milk": "Maito", "gluten": "Gluteeni", "egg": "Kananmuna"},
                "sv": {"milk": "Mjölk", "gluten": "Gluten", "egg": "Ägg"},
                "en": {"milk": "Milk", "gluten": "Gluten", "egg": "Egg"},
            }
            labels = [name_map[lang].get(k, k) for k in inferred]
            heading_all = {"fi": "Allergeenit:", "sv": "Allergener:", "en": "Allergens:"}[lang]
            lines.append(f"<strong>{heading_all}</strong> {', '.join(labels)}")
    # Add standard disclaimer
    amap = load_allergens()
    disclaimer = amap.disclaimer_for("allergens", lang)
    if disclaimer:
        lines.append(disclaimer)
    # Ensure the message is treated as HTML in the chat UI
    html = "<div class=\"prod-detail\">" + "<br>".join(lines) + "</div>"
    return html


def resolve_allergens(query: str, lang: str) -> str:
    amap = load_allergens()
    key = amap.lookup(query) or "allergens"
    disclaimer = amap.disclaimer_for(key, lang)
    if not disclaimer:
        disclaimer = {
            "fi": "Käytämme leipomossa viljaa ja maitotuotteita; ristikontaminaatiota ei voida täysin poissulkea.",
            "sv": "Vi använder spannmål och mjölk i bageriet; korskontaminering kan inte helt uteslutas.",
            "en": "We handle cereals and dairy in the bakery; cross‑contamination cannot be fully excluded.",
        }[lang]
    # Try to find a product name mentioned and echo it
    aliases = load_product_aliases()
    mention = None
    t = query.lower()
    for term in aliases.all_terms():
        if term.lower() in t:
            mention = term
            break
    if mention:
        if lang == "fi":
            return f"{mention}: {disclaimer} Kysy henkilökunnalta tarkemmat allergiatiedot."
        if lang == "sv":
            return f"{mention}: {disclaimer} Fråga personalen för exakt allergeninfo."
        return f"{mention}: {disclaimer} Please ask staff for precise allergen information."
    return disclaimer


def resolve_hours(lang: str) -> str:
    hours = load_weekly_hours()
    return format_hours_response(hours, lang)


def resolve_blackout(query: str, lang: str) -> str:
    if not ecwid.get_order_constraints or not ecwid.is_blackout:
        if lang == "fi":
            return "Saatavuus vaihtelee. Kysy erikoispäivistä tai katso verkkokaupasta."
        if lang == "sv":
            return "Tillgänglighet varierar. Fråga om specialdagar eller se webbutiken."
        return "Availability varies. Ask about special dates or check the online store."
    # Try to find a date in query: YYYY-MM-DD
    m = re.search(r"(20\d{2}-\d{2}-\d{2})", query)
    if not m:
        cons = ecwid.get_order_constraints()
        bl = cons.get("blackout_dates") or []
        if not bl:
            if lang == "fi":
                return "Ei erikseen ilmoitettuja sulkupäiviä."
            if lang == "sv":
                return "Inga särskilda avstängningsdagar angivna."
            return "No specific blackout dates listed."
        if lang == "fi":
            return "Mahdollisia sulkupäiviä on kalenterissa. Kokeile kysyä tiettyä päivää muodossa YYYY-MM-DD."
        if lang == "sv":
            return "Det kan finnas avstängningsdagar. Fråga ett specifikt datum i format YYYY-MM-DD."
        return "There may be blackout dates. Ask about a specific date in YYYY-MM-DD format."
    date_s = m.group(1)
    try:
        from datetime import datetime
        dt = datetime.strptime(date_s, "%Y-%m-%d")
        is_bl = ecwid.is_blackout(dt, ecwid.get_order_constraints().get("blackout_dates") or [])
        if is_bl:
            if lang == "fi":
                return f"Päivä {date_s}: ei noutoja (sulkupäivä)."
            if lang == "sv":
                return f"{date_s}: inga upphämtningar (avstängning)."
            return f"{date_s}: no pickups (blackout)."
        else:
            if lang == "fi":
                return f"Päivä {date_s}: mahdollinen, tarkista verkkokaupasta."
            if lang == "sv":
                return f"{date_s}: möjlig, kontrollera i webbutiken."
            return f"{date_s}: likely available, please check the online store."
    except Exception:
        if lang == "fi":
            return "En pystynyt tulkitsemaan päivämäärää. Käytä muotoa YYYY-MM-DD."
        if lang == "sv":
            return "Kunde inte tolka datumet. Använd format YYYY-MM-DD."
    return "Could not parse the date. Use YYYY-MM-DD."


def resolve_faq(query: str, lang: str) -> Optional[str]:
    # Dynamic FAQ composition based on topic detection and settings
    t = query.lower()
    s = load_settings()
    # Pickup / address topic
    if any(k in t for k in [
        # generic address/location
        "pickup", "address", "location", "adress",
        # English phrases
        "where are you located", "where is your shop", "where is the shop", "located",
        "where in helsinki are you", "where in helsinki", "nearest stop", "closest stop", "nearest bus", "nearest tram",
        # Finnish
        "nouto", "osoite", "sijainti", "sijaitse", "missä sijaitsette", "missä olette", "missä helsingissä",
        "lähin pysäkki", "lähin bussi", "lähin ratikka", "lähin spora", "lähin pysäkk", "pysäkki",
        # Swedish
        "hämt", "var hämtar", "var ligger", "var finns", "butikens adress", "var i helsingfors",
        "närmsta hållplats", "närmaste hållplats", "närmsta buss", "närmsta spårvagn",
    ]):
        # Localize city name for Swedish if needed
        city_val = s.city
        try:
            if lang == "sv" and (s.city or "").strip().lower() == "helsinki":
                city_val = "Helsingfors"
        except Exception:
            pass
        addr = ", ".join([p for p in [s.address_line, s.postal_code, city_val] if p]) or ""
        district = s.district or ""
        park = (s.parking_note.get(lang) or s.parking_note.get("fi") or "").strip()
        stops = (s.nearest_stops.get(lang) or s.nearest_stops.get("fi") or "").strip()
        if lang == "fi":
            # Requested exact phrasing for Finnish location answer
            return "Leipomomyymälämme sijaitsee osoitteessa Kumpulantie 15, 00520 Helsinki"
        if lang == "sv":
            lines = [
                f"Vi finns i {district} på {addr}. Välkommen!".replace("  ", " ").strip(),
                "Butiken ligger på gatuplan och gatuparkering finns mot avgift.",
                (stops if stops else ""),
                "Om du har gjort en webborder, ta med orderbekräftelsen (från e‑posten).",
            ]
            return " ".join(lines)
        # en
        lines = [
            f"We are located in {district} at {addr}. Welcome!".replace("  ", " ").strip(),
            "The shop is at street level and street parking is available for a fee.",
            (stops if stops else ""),
            "If you placed an online order, please bring your order confirmation email.",
        ]
        return " ".join(lines)

    # Prefer specific FAQ items before generic order/preorder messaging
    items = load_faq()
    if items:
        def _tokens(s: str) -> set[str]:
            import re
            return {w for w in re.split(r"[^a-zåäöA-ZÅÄÖ0-9]+", s.lower()) if len(w) >= 3}
        qtoks = _tokens(t)
        best = None
        best_score = 0
        for it in items:
            q_all = " ".join([v.lower() for v in it.q.values()])
            atoks = _tokens(q_all)
            score = 0
            # tag hits
            for tag in it.tags:
                if tag and tag.lower() in t:
                    score += 3
            # token overlap
            score += sum(1 for w in atoks if w in qtoks)
            # lead-time phrasing boost across languages
            if any(k in t for k in [
                "kuinka ajoissa", "edellisenä päivänä", "milloin pitää tilata",
                "hur långt i förväg", "dagen innan",
                "how early should i", "day before"
            ]):
                score += 2
            if score > best_score:
                best_score = score
                best = it
        if best and best_score > 0:
            ans = best.text_for(lang, "a")
            veg_tags = {"vegaaninen", "vegaani", "maidoton", "laktoositon", "vegan", "dairy-free"}
            if any(tag in veg_tags for tag in best.tags):
                label = {"fi": "Tuotteet", "sv": "Produkter", "en": "Goodies"}.get(lang, "Tuotteet")
                trigger = {"fi": "vegaaninen maidoton", "sv": "vegansk mjölkfri", "en": "vegan dairy-free"}.get(lang, "vegaaninen maidoton")
                suggest_html = (
                    f"""
<div class=\"suggest\">\n  <div class=\"buttons\">\n    <button type=\"button\" class=\"btn suggest-btn\" data-suggest=\"{trigger}\">{label}</button>\n  </div>\n</div>
"""
                )
                return f"<div class=\"faq-ans\"><p>{ans}</p>{suggest_html}</div>"
            return ans

    # Order / preorder topic
    if any(k in t for k in ["preorder", "order", "tilaa", "ennakkotilaus", "beställ"]):
        url = s.store_url
        if lang == "fi":
            return f"Tee tilaus verkkokaupassa ja nouda aukioloaikoina. {url or ''}".strip()
        if lang == "sv":
            return f"Gör en beställning i webbutiken och hämta under öppettider. {url or ''}".strip()
        return f"Place an order in the online shop and pick up during opening hours. {url or ''}".strip()

    # Final fallback to first entry if present
    items2 = load_faq()
    if items2:
        return items2[0].text_for(lang, "a")
    return None


def resolve_diet_options(query: str, lang: str) -> str:
    # Fetch a broad list of products and filter based on name markers
    items = _get_products_cached(limit=200)
    vegan_list: list[str] = []
    dairyfree_list: list[str] = []
    for it in items:
        if not it.get("enabled", True):
            continue
        name = (it.get("name") or "").strip()
        low = name.lower()
        # Match vegan markers even inside compound words (e.g., "vegaanipiirakka")
        is_vegan = bool(re.search(r"(vegaani|vegaaninen|vegan|vegansk)", low))
        # Dairy-free (non‑vegan) should NOT rely on 'laktoositon' (lactose‑free ≠ dairy‑free).
        # Curate true dairy‑free non‑vegan items here (e.g., Lihacurry‑pasteija).
        curated_df_nonvegan_keys = [
            "lihacurry-pasteija", "lihacurry", "meat curry pastry"
        ]
        is_true_dairy_free_marker = bool(re.search(r"\b(maidoton|mjölkfri|mjolkfri|dairy\s*-?free)\b", low))
        is_curated_df = any(k in low for k in curated_df_nonvegan_keys)
        if is_vegan:
            vegan_list.append(name)
        elif (is_true_dairy_free_marker or is_curated_df):
            dairyfree_list.append(name)

    if not (vegan_list or dairyfree_list):
        if lang == "sv":
            return "För tillfället kunde jag inte hitta veganska eller mjölkfria produkter. Vänligen kontrollera menyn."
        if lang == "fi":
            return "Tällä hetkellä en löytänyt vegaanisia tai maidottomia tuotteita. Tarkista valikko."
        return "I couldn’t find vegan or dairy‑free items right now. Please check the menu."

    # Localized headings
    vegan_h = {"fi": "Vegaaniset", "sv": "Veganska", "en": "Vegan"}[lang]
    dairy_h = {"fi": "Maidottomat (ei‑vegaaniset)", "sv": "Mjölkfria (inte veganska)", "en": "Dairy‑free (non‑vegan)"}[lang]

    def _ul(items: list[str]) -> str:
        return "".join(f"<li>{n}</li>" for n in items)

    # Build HTML with readable category headings and compact lists
    parts: list[str] = ["<div class=\"diet-list\">"]
    if vegan_list:
        parts.append(f"<div class=\"diet-cat\">{vegan_h}</div>")
        parts.append(f"<ul class=\"diet-items\">{_ul(vegan_list)}</ul>")
    if dairyfree_list:
        parts.append(f"<div class=\"diet-cat\">{dairy_h}</div>")
        parts.append(f"<ul class=\"diet-items\">{_ul(dairyfree_list)}</ul>")
    parts.append("</div>")
    # Inline styles to keep readability consistent going forward
    parts.append(
        "<style>"
        ".diet-list,.diet-list *{box-sizing:border-box}"
        ".diet-list{width:100%}"
        ".diet-list .diet-cat{font-size:16px;font-weight:700;margin:6px 0 2px}"
        ".diet-list .diet-items{margin:4px 0 8px 14px;padding-left:0;list-style:disc inside}"
        ".diet-list .diet-items li{margin:2px 0;font-size:14px;line-height:1.35;word-break:break-word;overflow-wrap:anywhere}"
        "</style>"
    )
    return "".join(parts)

def resolve_product_suggest(query: str, lang: str) -> Optional[str]:
    items = _get_products_cached(limit=100)
    it = _find_product_by_name_or_alias(query, items) if items else None
    name = (it.get("name") if it else None) or query.strip()
    if lang == "fi":
        return (
            f"""
<div class=\"suggest\">\n  <div class=\"title\">{name}</div>\n  <div class=\"buttons\">\n    <button type=\"button\" class=\"btn suggest-btn\" data-suggest=\"{name} ainesosat ja allergeenit\">Haluatko tiedot?</button>\n    <button type=\"button\" class=\"btn suggest-btn\" data-action=\"start-order\">Haluatko tilata {name}?</button>\n  </div>\n</div>
"""
        )
    if lang == "sv":
        return (
            f"""
<div class=\"suggest\">\n  <div class=\"title\">{name}</div>\n  <div class=\"buttons\">\n    <button type=\"button\" class=\"btn suggest-btn\" data-suggest=\"{name} ingredienser och allergener\">Vill du se uppgifter?</button>\n    <button type=\"button\" class=\"btn suggest-btn\" data-action=\"start-order\">Vill du beställa {name}?</button>\n  </div>\n</div>
"""
        )
    return (
        f"""
<div class=\"suggest\">\n  <div class=\"title\">{name}</div>\n  <div class=\"buttons\">\n    <button type=\"button\" class=\"btn suggest-btn\" data-suggest=\"{name} ingredients and allergens\">Want details?</button>\n    <button type=\"button\" class=\"btn suggest-btn\" data-action=\"start-order\">Want to order {name}?</button>\n  </div>\n</div>
"""
    )


def answer(query: str, lang: str) -> Optional[str]:
    intent = detect_intent(query)
    if intent == "hours":
        return resolve_hours(lang)
    if intent == "menu":
        return resolve_menu(lang, query=query)
    if intent == "diet":
        return resolve_diet_options(query, lang)
    if intent == "product_detail":
        txt = resolve_product_detail(query, lang)
        if txt:
            return txt
        # fallback to allergens if we couldn't bind to a product
        return resolve_allergens(query, lang)
    if intent == "product_suggest":
        return resolve_product_suggest(query, lang)
    if intent == "allergens":
        return resolve_allergens(query, lang)
    if intent == "blackout":
        return resolve_blackout(query, lang)
    if intent == "faq":
        return resolve_faq(query, lang)
    return None
