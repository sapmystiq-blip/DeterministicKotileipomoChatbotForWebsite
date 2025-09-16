#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path
import json
from datetime import datetime, timedelta, time

# Ensure the repo root is on sys.path so `backend` can be imported
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient


def _aligned_candidates(cons: dict, hours: dict, count: int = 12) -> list[str]:
    lead = int(cons.get("min_lead_minutes", 720))
    now = datetime.now()
    min_t = now + timedelta(minutes=lead)
    out: list[str] = []
    # hours dict keys are strings of weekday ints: Mon=0..Sun=6
    for i in range(0, 30):
        d = (now + timedelta(days=i)).date()
        wins = hours.get(str(datetime.combine(d, time()).weekday()), [])
        for start, end in wins:
            sh, sm = map(int, start.split(":"))
            eh, em = map(int, end.split(":"))
            ws = datetime.combine(d, time(sh, sm))
            we = datetime.combine(d, time(eh, em))
            mt = min_t.replace(minute=0, second=0, microsecond=0)
            if min_t > mt:
                mt = mt + timedelta(hours=1)
            cand = max(ws, mt)
            while cand <= we and len(out) < count:
                out.append(cand.strftime("%Y-%m-%dT%H:%M"))
                cand += timedelta(hours=1)
        if len(out) >= count:
            break
    # Fallback one week ahead Fri 13:00 if empty
    if not out:
        d = now + timedelta(days=((4 - now.weekday()) % 7) or 7)
        out = [d.replace(hour=13, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")]
    return out


def main():
    # Ensure chat ordering is enabled for this run
    os.environ["ENABLE_CHAT_ORDERING"] = os.environ.get("ENABLE_CHAT_ORDERING", "true")

    # Import after setting env
    from backend.app import app  # type: ignore

    client = TestClient(app)
    # Fetch constraints + pickup hours from backend
    cons = client.get("/api/v2/order_constraints").json()
    hours = client.get("/api/v2/pickup_hours").json().get("hours", {})
    cands = _aligned_candidates(cons, hours)

    items = [
        {
            "productId": 771476057,
            "sku": "00071",
            "name": "Voisilmäpulla (vegaani), paistettu, 4 kpl",
            "quantity": 1,
        },
        {
            "productId": 708500182,
            "sku": "00064",
            "name": "Karjalanpiirakka (laktoositon), raakapakaste, 20 kpl",
            "quantity": 1,
        },
    ]

    for iso in cands:
        payload = {
            "items": items,
            "name": "Chat Test",
            "email": "test@example.com",
            "phone": "+358 123 456 789",
            "pickup_time": iso,
            "note": "Chatbot test order",
        }
        r = client.post("/api/v2/order", json=payload)
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text}
        print(json.dumps({"attempt": iso, "status": r.status_code, "body": body}, ensure_ascii=False))
        if r.status_code == 200:
            break


if __name__ == "__main__":
    main()
