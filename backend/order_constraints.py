from __future__ import annotations

from typing import Any, Dict, List, Tuple


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


def _scan_days_candidates(obj: Any) -> List[int]:
    out: List[int] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = str(k).lower()
            if isinstance(v, int) and (
                ("day" in lk and any(t in lk for t in ("advance", "ahead", "period", "custom", "limit")))
            ):
                out.append(int(v))
            elif isinstance(v, (dict, list)):
                out.extend(_scan_days_candidates(v))
    elif isinstance(obj, list):
        for it in obj:
            out.extend(_scan_days_candidates(it))
    return out


def infer_constraints(
    shipping_options: List[Dict[str, Any]] | None,
    profile: Dict[str, Any] | None,
    default_min_lead_minutes: int,
    default_max_days: int,
) -> Dict[str, Any]:
    """Pure inference from Ecwid payloads.
    Returns dict with min_lead_minutes, max_days, blackout_dates, found_min, found_max.
    """
    min_lead: int | None = None
    max_days: int | None = None
    found_min = False
    found_max = False
    blackouts: List[Dict[str, Any]] = []

    opts = shipping_options or []
    for opt in opts:
        settings = opt.get("settings") or {}
        # Lead minutes
        prep_mins = (
            settings.get("pickupPreparationTimeMinutes")
            or settings.get("preparationTimeMinutes")
            or settings.get("leadTimeMinutes")
            or opt.get("pickupPreparationTimeMinutes")
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

        # Max days
        md = (
            settings.get("daysInAdvance")
            or settings.get("maxAdvanceDays")
            or settings.get("orderAheadDays")
            or _availability_to_days(opt.get("availabilityPeriod"))
            or opt.get("availabilityPeriodCustomDays")
            or settings.get("availabilityPeriodCustomDays")
        )
        if not md:
            cands = _scan_days_candidates({"opt": opt, "settings": settings})
            if cands:
                md = max(cands)
        if isinstance(md, int) and md > 0:
            val = int(md)
            max_days = val if (max_days is None or val < max_days) else max_days
            found_max = True

        # Blackout
        bl = opt.get("blackoutDates")
        if isinstance(bl, list):
            for it in bl:
                fd = it.get("fromDate") or it.get("from")
                td = it.get("toDate") or it.get("to")
                ra = bool(it.get("repeatedAnnually"))
                if fd and td:
                    blackouts.append({"from": fd, "to": td, "repeatedAnnually": ra})

    ship = (profile or {}).get("settings", {}).get("shipping", {})
    md_profile = ship.get("maxOrderAheadDays")
    if isinstance(md_profile, int) and md_profile > 0:
        val = int(md_profile)
        max_days = val if (max_days is None or val < max_days) else max_days
        found_max = True

    for opt in ship.get("shippingOptions", []) or []:
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

        md = (
            _availability_to_days(opt.get("availabilityPeriod"))
            or opt.get("availabilityPeriodCustomDays")
        )
        if not md:
            cands = _scan_days_candidates(opt)
            if cands:
                md = max(cands)
        if isinstance(md, int) and md > 0:
            val = int(md)
            max_days = val if (max_days is None or val < max_days) else max_days
            found_max = True

        bl = opt.get("blackoutDates")
        if isinstance(bl, list):
            for it in bl:
                fd = it.get("fromDate") or it.get("from")
                td = it.get("toDate") or it.get("to")
                ra = bool(it.get("repeatedAnnually"))
                if fd and td:
                    blackouts.append({"from": fd, "to": td, "repeatedAnnually": ra})

    if min_lead is None:
        min_lead = default_min_lead_minutes
    if max_days is None:
        max_days = default_max_days

    return {
        "min_lead_minutes": int(min_lead),
        "max_days": int(max_days),
        "blackout_dates": blackouts,
        "found_min": bool(found_min),
        "found_max": bool(found_max),
    }

