from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..order_constraints import infer_constraints
from ..ecwid_client import (
    get_products as ecwid_get_products,
    get_categories as ecwid_get_categories,
    get_profile as ecwid_get_profile,
    get_shipping_options as ecwid_get_shipping_options,
)
import os
from datetime import datetime, timedelta
import httpx
from ..time_rules import SHOP_HOURS, validate_pickup_time, parse_pickup_iso, is_blackout


router = APIRouter()


def _curate_products(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    keep: List[Dict[str, Any]] = []
    KEYWORDS = [
        "karjalan", "karelian", "piirakka", "pie", "samosa", "curry", "twist",
        "mustikkakukko", "blueberry", "marjapiirakka", "berry", "pulla", "bun"
    ]
    for it in items:
        name = (it.get("name") or "").lower()
        if not it.get("enabled", True):
            continue
        if any(k in name for k in KEYWORDS):
            keep.append({
                "id": it.get("id"),
                "sku": it.get("sku"),
                "name": it.get("name"),
                "price": it.get("price"),
                "enabled": True,
                "imageUrl": (
                    it.get("thumbnailUrl")
                    or it.get("imageUrl")
                    or ((it.get("image") or {}).get("url"))
                ),
                "inStock": it.get("inStock"),
                "quantity": it.get("quantity") or it.get("quantityAvailable"),
            })
    seen, out = set(), []
    for it in keep:
        key = it.get("id") or it.get("sku")
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out[:25]


@router.get("/api/v2/categories")
def api_categories():
    try:
        cats = ecwid_get_categories(limit=200)
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
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch categories.")


@router.get("/api/v2/products")
def api_products(category: Optional[int] = None):
    try:
        items = ecwid_get_products(limit=100, category=category)
        curated = _curate_products(items)
        return {"items": curated}
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch products.")


@router.get("/api/v2/order_constraints")
def api_order_constraints():
    try:
        ship_opts = ecwid_get_shipping_options()
        profile = ecwid_get_profile()
    except Exception:
        ship_opts, profile = [], {}
    res = infer_constraints(
        shipping_options=ship_opts,
        profile=profile,
        default_min_lead_minutes=int(os.getenv("ECWID_MIN_LEAD_MINUTES", "720")),
        default_max_days=int(os.getenv("ECWID_MAX_ORDER_DAYS", "60")),
    )
    return {
        "source": "ecwid" if (res.get("found_min") or res.get("found_max")) else "defaults",
        "min_lead_minutes": int(res["min_lead_minutes"]),
        "max_days": int(res["max_days"]),
        "blackout_dates": res.get("blackout_dates") or [],
    }


@router.get("/api/v2/pickup_hours")
def api_pickup_hours_v2():
    tz = os.getenv("LOCAL_TZ", "Europe/Helsinki")
    return {"timezone": tz, "hours": SHOP_HOURS}


@router.get("/api/v2/check_pickup")
def api_check_pickup_v2(iso: str):
    ok, reason = validate_pickup_time(iso, SHOP_HOURS)
    return {"ok": ok, "reason": reason}


class OrderItem(BaseModel):
    productId: int | None = None
    sku: str | None = None
    quantity: int


class OrderRequest(BaseModel):
    items: List[OrderItem]
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    pickup_time: str
    note: str | None = None


@router.post("/api/v2/order")
def api_order_v2(req: OrderRequest):
    ok, reason = validate_pickup_time(req.pickup_time, SHOP_HOURS)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Pickup time not available: {reason}")

    res = infer_constraints(
        shipping_options=ecwid_get_shipping_options(),
        profile=ecwid_get_profile(),
        default_min_lead_minutes=int(os.getenv("ECWID_MIN_LEAD_MINUTES", "720")),
        default_max_days=int(os.getenv("ECWID_MAX_ORDER_DAYS", "60")),
    )
    min_lead = int(res.get("min_lead_minutes", 0))
    max_days = int(res.get("max_days", 0))
    blackouts = res.get("blackout_dates") or []

    now = datetime.now()
    dt = parse_pickup_iso(req.pickup_time)
    if not dt:
        raise HTTPException(status_code=400, detail="Invalid time format. Use YYYY-MM-DDTHH:MM.")
    if min_lead > 0 and dt < (now + timedelta(minutes=min_lead)):
        raise HTTPException(status_code=400, detail=f"Pickup must be at least {int(round(min_lead/60))} hours from now.")
    if max_days > 0 and dt.date() > (now + timedelta(days=max_days)).date():
        raise HTTPException(status_code=400, detail=f"Pickup cannot be more than {max_days} days ahead.")
    if is_blackout(dt, blackouts):
        raise HTTPException(status_code=400, detail="Pickup date is not available (blackout).")

    items: List[Dict[str, Any]] = []
    for it in req.items:
        if (not it.productId) and (not it.sku):
            raise HTTPException(status_code=400, detail="Each item must have productId or sku.")
        if it.quantity and it.quantity > 0:
            entry: Dict[str, Any] = {"quantity": it.quantity}
            if it.productId:
                entry["productId"] = it.productId
            if it.sku:
                entry["sku"] = it.sku
            items.append(entry)
    if not items:
        raise HTTPException(status_code=400, detail="All quantities are zero.")

    from ..ecwid_client import ecwid_base, ecwid_headers
    url = f"{ecwid_base()}/orders"
    body = {
        "name": req.name or "Chat Customer",
        "email": req.email or "",
        "phone": req.phone or "",
        "paymentMethod": "Pay at pickup",
        "paymentStatus": "AWAITING_PAYMENT",
        "shippingOption": {"shippingMethodName": "Pickup", "fulfillmentType": "PICKUP"},
        "items": items,
        "customerComment": " | ".join([p for p in [f"Pickup: {req.pickup_time}", req.note] if p]),
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(url, headers=ecwid_headers(), json=body)
            r.raise_for_status()
            data = r.json()
        return {"ok": True, "id": data.get("id"), "orderNumber": data.get("orderNumber")}
    except httpx.HTTPStatusError as he:
        detail = he.response.text or f"Ecwid API error {he.response.status_code}"
        raise HTTPException(status_code=he.response.status_code, detail=detail)
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to create order.")
