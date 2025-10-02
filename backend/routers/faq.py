from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..faq_repository import get_faq_repository
from ..intent_router import resolve_menu, build_dietary_menu

router = APIRouter(prefix="/faq", tags=["faq"])


@router.get("/tree")
def get_tree(lang: Optional[str] = Query(None, description="Preferred language code (fi/en/sv)")) -> dict:
    repo = get_faq_repository()
    tree = repo.tree(lang)
    return {"version": repo.version, "tree": tree}


@router.get("/entries")
def get_entries(
    path: str = Query(..., description="Dot-separated category path e.g. menu.menu-tuoreet.karjalanpiirakat"),
    lang: Optional[str] = Query(None, description="Preferred language code (fi/en/sv)"),
) -> dict:
    repo = get_faq_repository()
    parts: List[str] = [segment for segment in path.split(".") if segment]
    if not parts:
        raise HTTPException(status_code=400, detail="Path cannot be empty")
    items = repo.entries_for(parts, lang)
    if not items:
        raise HTTPException(status_code=404, detail="No FAQ entries for given path")
    return {"version": repo.version, "items": items}

@router.get("/menu")
def get_menu(
    menu_type: str = Query("fresh", description="fresh | frozen"),
    lang: Optional[str] = Query(None, description="Preferred language code (fi/en/sv)"),
) -> dict:
    kind = (menu_type or "").strip().lower() or "fresh"
    if kind not in {"fresh", "frozen"}:
        raise HTTPException(status_code=400, detail="menu_type must be 'fresh' or 'frozen'")
    language = (lang or os.getenv("PRIMARY_LANG", "fi")).strip().lower() or "fi"
    query = "pakasteet" if kind == "frozen" else None
    html = resolve_menu(language, query=query)
    repo = get_faq_repository()
    return {"version": repo.version, "type": kind, "html": html}


@router.get("/menu/diet")
def get_menu_diet(
    lang: Optional[str] = Query(None, description="Preferred language code (fi/en/sv)"),
) -> dict:
    language = (lang or os.getenv("PRIMARY_LANG", "fi")).strip().lower() or "fi"
    data = build_dietary_menu(language)
    repo = get_faq_repository()
    payload = {"version": repo.version, "groups": data.get("groups", [])}
    if data.get("disclaimer"):
        payload["disclaimer"] = data["disclaimer"]
    return payload
