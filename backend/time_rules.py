from __future__ import annotations

from typing import Dict, List, Tuple, Any
from datetime import datetime


# Default pickup hours (local time). Python weekday: Mon=0 .. Sun=6
# Thu 11–17, Fri 11–17, Sat 11–15
SHOP_HOURS: Dict[int, List[Tuple[str, str]]] = {
    3: [("11:00", "17:00")],
    4: [("11:00", "17:00")],
    5: [("11:00", "15:00")],
}


def parse_pickup_iso(s: str) -> datetime | None:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def validate_pickup_time(pickup_iso: str, shop_hours: Dict[int, List[Tuple[str, str]]] | None = None) -> Tuple[bool, str | None]:
    dt = parse_pickup_iso(pickup_iso)
    if not dt:
        return False, "Invalid time format. Use YYYY-MM-DDTHH:MM."
    hours = shop_hours or SHOP_HOURS
    dow = dt.weekday()  # Mon=0
    windows = hours.get(dow) or []
    if not windows:
        return False, "Closed that day."
    mins = dt.hour * 60 + dt.minute
    for start, end in windows:
        sh, sm = map(int, start.split(":"))
        eh, em = map(int, end.split(":"))
        if (sh * 60 + sm) <= mins <= (eh * 60 + em):
            return True, None
    return False, "Outside pickup hours."


def is_blackout(dt: datetime, blackouts: List[Dict[str, Any]] | None) -> bool:
    try:
        y = dt.year
        for b in blackouts or []:
            fd = (b.get("from") or b.get("fromDate") or "").strip()
            td = (b.get("to") or b.get("toDate") or "").strip()
            ra = bool(b.get("repeatedAnnually"))
            if not (fd and td):
                continue
            parts_f = (fd.split("-") + ["1", "1"])[:3]
            parts_t = (td.split("-") + ["1", "1"])[:3]
            fy, fm, fdn = [int(x) for x in parts_f]
            ty, tm, tdn = [int(x) for x in parts_t]
            if ra:
                fy = ty = y
            start = datetime(fy, fm, fdn, 0, 0)
            end = datetime(ty, tm, tdn, 23, 59)
            if start <= dt <= end:
                return True
        return False
    except Exception:
        return False
