#!/usr/bin/env python3
"""
Place a test order via the local API.

Defaults:
- base URL: http://localhost:8000
- pickup_time: 2025-09-13T14:00 (Saturday 14:00)

Usage:
  python3 scripts/place_order.py
  python3 scripts/place_order.py --base http://localhost:8000 --pickup 2025-09-13T14:00
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request


def get_json(url: str):
    with urllib.request.urlopen(url) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser(description="Place a test order via local API")
    ap.add_argument("--base", default="http://localhost:8000", help="Base URL of the running app")
    ap.add_argument("--pickup", default="2025-09-13T14:00", help="Pickup time ISO YYYY-MM-DDTHH:MM")
    args = ap.parse_args()

    base = args.base.rstrip("/")
    pickup_time = args.pickup

    # Status
    status = get_json(f"{base}/api/v2/ecwid_status")
    print("ecwid_status:", status)

    # Validate pickup time
    chk = get_json(f"{base}/api/v2/check_pickup?{urllib.parse.urlencode({'iso': pickup_time})}")
    if not chk.get("ok"):
        sys.exit(f"Pickup time rejected: {chk.get('reason')}")

    # Choose first category/product
    cats = get_json(f"{base}/api/v2/categories").get("items", [])
    if not cats:
        sys.exit("No categories available")
    cat_id = cats[0]["id"]

    prods = get_json(f"{base}/api/v2/products?{urllib.parse.urlencode({'category': cat_id})}").get("items", [])
    if not prods:
        sys.exit("No products available in selected category")
    prod_id = prods[0]["id"]

    payload = json.dumps({
        "items": [{"productId": int(prod_id), "quantity": 1}],
        "name": "CLI Test",
        "phone": "+358...",
        "email": "test@example.com",
        "pickup_time": pickup_time,
        "note": "Terminal test",
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base}/api/v2/order",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            print("Order response:", json.load(r))
    except urllib.error.HTTPError as e:
        print("HTTPError:", e.code)
        try:
            print(e.read().decode())
        except Exception:
            pass
        sys.exit(2)


if __name__ == "__main__":
    main()

