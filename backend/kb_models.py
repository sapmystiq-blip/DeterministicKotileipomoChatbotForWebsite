from __future__ import annotations

from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field, validator


class DayHours(BaseModel):
    # 24h HH:MM strings, e.g., "11:00"
    start: str
    end: str

    @validator("start", "end")
    def _validate_time(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("time must be HH:MM")
        hh, mm = parts
        if not (hh.isdigit() and mm.isdigit()):
            raise ValueError("time must be HH:MM digits")
        h, m = int(hh), int(mm)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("invalid time range")
        return v


class WeeklyHours(BaseModel):
    # Mon=0 .. Sun=6 as strings for JSON friendliness
    hours: Dict[str, List[DayHours]] = Field(default_factory=dict)
    # ISO date keyed exceptions, e.g., {"2025-12-24": [{"start":"10:00","end":"14:00"}]}
    exceptions: Dict[str, List[DayHours]] = Field(default_factory=dict)
    notes: Dict[str, str] = Field(default_factory=dict)

    @validator("hours")
    def _validate_dow(cls, v: Dict[str, List[DayHours]]):
        for k in v.keys():
            if k not in {str(i) for i in range(7)}:
                raise ValueError("hours keys must be '0'..'6'")
        return v


class FaqItem(BaseModel):
    q: Dict[str, str]  # {"fi": "...", "en": "...", "sv": "..."}
    a: Dict[str, str]
    tags: List[str] = Field(default_factory=list)

    def text_for(self, lang: str, kind: Literal["q", "a"]) -> str:
        src = self.q if kind == "q" else self.a
        return src.get(lang) or src.get("fi") or next(iter(src.values()), "")


class AllergenInfo(BaseModel):
    canonical: str  # e.g., "gluten", "nuts", "milk"
    synonyms: List[str] = Field(default_factory=list)
    disclaimer: Dict[str, str] = Field(default_factory=dict)


class AllergenMap(BaseModel):
    items: List[AllergenInfo] = Field(default_factory=list)

    def lookup(self, text: str) -> Optional[str]:
        t = text.lower()
        for it in self.items:
            if it.canonical in t:
                return it.canonical
            for s in it.synonyms:
                if s.lower() in t:
                    return it.canonical
        return None

    def disclaimer_for(self, key: str, lang: str) -> str:
        for it in self.items:
            if it.canonical == key:
                return it.disclaimer.get(lang) or it.disclaimer.get("fi") or ""
        return ""


class ProductAlias(BaseModel):
    name: str
    aliases: List[str] = Field(default_factory=list)


class ProductAliases(BaseModel):
    items: List[ProductAlias] = Field(default_factory=list)

    def all_terms(self) -> List[str]:
        out: List[str] = []
        for it in self.items:
            out.append(it.name)
            out.extend(it.aliases)
        # dedupe, preserve order
        seen = set()
        res: List[str] = []
        for s in out:
            k = s.lower().strip()
            if k in seen:
                continue
            seen.add(k)
            res.append(s)
        return res


class Settings(BaseModel):
    shop_name: Optional[str] = None
    address_line: Optional[str] = None  # e.g., "Kumpulantie 15"
    postal_code: Optional[str] = None   # e.g., "00520"
    city: Optional[str] = None          # e.g., "Helsinki"
    district: Optional[str] = None      # e.g., "Vallila"
    store_url: Optional[str] = None
    parking_note: Dict[str, str] = Field(default_factory=dict)  # localized note
    nearest_stops: Dict[str, str] = Field(default_factory=dict) # localized nearest stops text
