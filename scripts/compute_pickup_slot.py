#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, time


def main():
    if len(sys.argv) < 2:
        print("Usage: compute_pickup_slot.py <shipping_options.json>", file=sys.stderr)
        sys.exit(2)
    data = json.load(open(sys.argv[1], "r", encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("items", [])
    pickup = None
    for o in items:
        ft = (o.get("fulfilmentType") or o.get("fulfillmentType") or o.get("type") or "").lower()
        nm = (o.get("title") or o.get("name") or "").lower()
        if ft == "pickup" or "nouto" in nm or "pickup" in nm:
            pickup = o
            break
    if not pickup:
        print(json.dumps({}))
        return
    lead = (
        pickup.get("fulfillmentTimeInMinutes")
        or (pickup.get("settings") or {}).get("pickupPreparationTimeMinutes")
        or 660
    )
    hours_json = pickup.get("pickupBusinessHours") or pickup.get("businessHours") or "{}"
    try:
        hours = json.loads(hours_json)
    except Exception:
        hours = {}
    now = datetime.now()
    min_t = now + timedelta(minutes=int(lead))
    keys = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    slot_d, slot_t = None, None
    for i in range(0, 30):
        d = (now + timedelta(days=i)).date()
        wins = hours.get(keys[d.weekday()], [])
        for start, end in wins:
            sh, sm = map(int, start.split(":"))
            eh, em = map(int, end.split(":"))
            window_start = datetime.combine(d, time(sh, sm))
            window_end = datetime.combine(d, time(eh, em))
            # Start at the later of window_start and min_t rounded up to next hour
            start_cand = window_start
            mt = min_t.replace(minute=0, second=0, microsecond=0)
            if min_t > mt:
                mt = mt + timedelta(hours=1)
            if mt > start_cand:
                start_cand = mt
            # Step by 60 minutes until end
            cand = start_cand
            while cand <= window_end:
                if cand >= window_start:
                    slot_d = d.isoformat(); slot_t = cand.strftime("%H:%M")
                    break
                cand += timedelta(hours=1)
            if slot_d:
                break
        if slot_d:
            break
    out = {
        "id": pickup.get("id") or pickup.get("shippingMethodId") or pickup.get("methodId"),
        "name": pickup.get("title") or pickup.get("name") or "Pickup",
        "date": slot_d,
        "time": slot_t,
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
