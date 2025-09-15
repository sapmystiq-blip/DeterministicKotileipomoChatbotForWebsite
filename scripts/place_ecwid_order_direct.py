#!/usr/bin/env python3
"""
Place an order directly via Ecwid API using credentials in .env.

Steps:
- Read ECWID_STORE_ID and ECWID_API_TOKEN from .env
- Fetch shipping options, find the pickup method, compute next valid slot
- Fetch products, pick the first enabled product
- Create an order using preferredDeliveryDate/Time and the pickup method id

Usage:
  python3 scripts/place_ecwid_order_direct.py
"""
from __future__ import annotations

import json
import sys
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta, time, date


def read_env_vars(path: str = ".env") -> tuple[str, str]:
    store_id, token = None, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("ECWID_STORE_ID="):
                    store_id = line.strip().split("=", 1)[1]
                elif line.startswith("ECWID_API_TOKEN="):
                    token = line.strip().split("=", 1)[1]
    except Exception:
        pass
    if not store_id or not token:
        raise SystemExit("ECWID_STORE_ID or ECWID_API_TOKEN not found in .env")
    return store_id, token


def get_json(url: str, token: str):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def post_json(url: str, token: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def choose_pickup_and_slot(opts: list[dict]) -> tuple[dict, str, str]:
    # Find pickup option by type or name
    pickup = None
    for o in opts:
        ft = (o.get("fulfilmentType") or o.get("fulfillmentType") or o.get("type") or "").lower()
        name = (o.get("title") or o.get("name") or "").lower()
        if ft == "pickup" or "nouto" in name or "pickup" in name:
            pickup = o
            break
    if not pickup:
        raise SystemExit("No pickup method found in shippingOptions")
    lead = (
        pickup.get("fulfillmentTimeInMinutes")
        or (pickup.get("settings") or {}).get("pickupPreparationTimeMinutes")
        or 0
    )
    hours_json = pickup.get("pickupBusinessHours") or pickup.get("businessHours") or "{}"
    try:
        hours = json.loads(hours_json)
    except Exception:
        hours = {}
    now = datetime.now()
    min_time = now + timedelta(minutes=int(lead))
    keys = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    for i in range(0, 30):
        day = now.date() + timedelta(days=i)
        wins = hours.get(keys[day.weekday()], [])
        for start, end in wins:
            sh, sm = map(int, start.split(":"))
            cand = datetime.combine(day, time(sh, sm))
            if cand >= min_time:
                return pickup, day.isoformat(), start
    raise SystemExit("No valid pickup slot in next 30 days")


def main():
    store_id, token = read_env_vars()
    base = f"https://app.ecwid.com/api/v3/{store_id}"

    # Shipping options
    opts = get_json(f"{base}/profile/shippingOptions", token)
    opts = opts if isinstance(opts, list) else opts.get("items", [])
    pickup, pickup_date, pickup_time = choose_pickup_and_slot(opts)

    # Product
    prods = get_json(f"{base}/products?enabled=true&limit=5", token)
    items = prods.get("items", [])
    if not items:
        raise SystemExit("No products found")
    prod_id = items[0].get("id")
    if not prod_id:
        raise SystemExit("First product has no id")

    # Create order
    ship_name = pickup.get("title") or pickup.get("name") or "Pickup"
    ship_id = pickup.get("id") or pickup.get("shippingMethodId") or pickup.get("methodId")
    payload = {
        "name": "API Test",
        "paymentMethod": "Pay at pickup",
        "paymentStatus": "AWAITING_PAYMENT",
        "shippingOption": {
            "id": ship_id,
            "shippingMethodName": ship_name,
            "shippingRate": 0,
        },
        "preferredDeliveryDate": pickup_date,
        "preferredDeliveryTime": pickup_time,
        "items": [{"productId": int(prod_id), "quantity": 1}],
    }
    try:
        res = post_json(f"{base}/orders", token, payload)
    except urllib.error.HTTPError as e:
        try:
            msg = e.read().decode()
        except Exception:
            msg = str(e)
        print(msg)
        raise SystemExit(2)
    out = {"ok": True, "id": res.get("id"), "orderNumber": res.get("orderNumber"), "pickup": f"{pickup_date} {pickup_time}"}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()

