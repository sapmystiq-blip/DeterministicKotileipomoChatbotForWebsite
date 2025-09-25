from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
import logging
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
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


router = APIRouter()
logger = logging.getLogger(__name__)


def _split_name(full_name: Optional[str]) -> tuple[str, str]:
    """Return (first, last) components for Ecwid contact payloads."""
    if not full_name:
        return "", ""
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


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


@router.get("/api/v2/ecwid_status")
def api_ecwid_status():
    """Lightweight diagnostics for Ecwid auth and basic permissions.
    Does not expose secrets. Useful for confirming token/store configuration.
    """
    from ..ecwid_client import ecwid_base, ecwid_headers
    status: Dict[str, Any] = {"base": ecwid_base()}
    # Profile
    try:
        profile = ecwid_get_profile()
        status["profile_ok"] = True
        status["storeId"] = (
            (profile.get("generalInfo") or {}).get("storeId")
            or profile.get("id")
        )
        status["storeName"] = (
            (profile.get("generalInfo") or {}).get("storeName")
            or (profile.get("settings") or {}).get("storeName")
        )
    except Exception as e:
        status["profile_ok"] = False
        status["profile_error"] = str(e)
    # Shipping options
    try:
        ship_opts = ecwid_get_shipping_options()
        status["shipping_ok"] = True
        status["shipping_count"] = len(ship_opts)
        # Include a concise summary of options to aid debugging
        status["shipping_options"] = [
            {
                "id": (o.get("id") or o.get("shippingMethodId") or o.get("methodId")),
                "name": (
                    o.get("title")
                    or o.get("name")
                    or o.get("shippingMethodName")
                ),
                "fulfillmentType": (
                    o.get("fulfillmentType")
                    or o.get("type")
                    or ""
                ),
            }
            for o in ship_opts
        ]
    except Exception as e:
        status["shipping_ok"] = False
        status["shipping_error"] = str(e)
    # Orders read (permission check)
    try:
        url = f"{ecwid_base()}/orders"
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url, headers=ecwid_headers(), params={"limit": 1})
        status["orders_get_status"] = r.status_code
    except Exception as e:
        status["orders_get_status"] = None
        status["orders_get_error"] = str(e)
    return status

@router.get("/api/v2/check_pickup")
def api_check_pickup_v2(iso: str):
    ok, reason = validate_pickup_time(iso, SHOP_HOURS)
    return {"ok": ok, "reason": reason}


class OrderItem(BaseModel):
    productId: int | None = None
    sku: str | None = None
    name: str | None = None
    price: float | None = None
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
    # Feature flag: allow/disallow ordering via chat
    if (os.getenv("ENABLE_CHAT_ORDERING", "false").lower() in {"0", "false", "no", "off"}):
        raise HTTPException(status_code=403, detail="Ordering is disabled")
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
            if it.name:
                entry["name"] = it.name
            if it.price is not None:
                try:
                    entry["price"] = float(it.price)
                except Exception:
                    pass
            items.append(entry)
    if not items:
        raise HTTPException(status_code=400, detail="All quantities are zero.")

    # Ensure each item has required name and price per Ecwid API (fallback to catalog)
    try:
        from ..ecwid_client import ecwid_base, ecwid_headers
        base = ecwid_base(); headers = ecwid_headers()
        def _fill_item(i: Dict[str, Any]) -> Dict[str, Any]:
            if ("name" in i) and ("price" in i):
                # even if name/price present, try to backfill weight if missing
                need_weight = ("weight" not in i) or (i.get("weight") in (None, 0, 0.0))
                if not need_weight:
                    return i
            # Try by productId
            prod = None
            try:
                if i.get("productId"):
                    with httpx.Client(timeout=10.0) as client:
                        r = client.get(f"{base}/products/{int(i['productId'])}", headers=headers)
                        if r.status_code == 200:
                            prod = r.json()
            except Exception:
                prod = None
            # If not found and we have sku, try search by SKU
            if (not prod) and i.get("sku"):
                try:
                    with httpx.Client(timeout=10.0) as client:
                        r = client.get(f"{base}/products", headers=headers, params={"sku": i.get("sku"), "limit": 1})
                        if r.status_code == 200:
                            items_json = r.json().get("items") or []
                            if items_json:
                                prod = items_json[0]
                except Exception:
                    prod = None
            # Fill name/price if available
            if prod:
                if "name" not in i or not i.get("name"):
                    nm = prod.get("name") or ""
                    if nm:
                        i["name"] = nm
                if "price" not in i or i.get("price") is None:
                    pr = prod.get("price")
                    if isinstance(pr, (int, float)):
                        i["price"] = float(pr)
                # Backfill weight if available
                try:
                    w = prod.get("weight")
                    if isinstance(w, (int, float)) and w > 0:
                        i["weight"] = float(w)
                except Exception:
                    pass
            return i
        items = [_fill_item(i) for i in items]
        # Validate again
        for i in items:
            if ("name" not in i) or ("price" not in i):
                raise HTTPException(status_code=400, detail="Each item must include name and price (resolved from catalog or provided).")
    except HTTPException:
        raise
    except Exception:
        # If filling fails silently, proceed (Ecwid will validate and return a clear error)
        pass

    from ..ecwid_client import ecwid_base, ecwid_headers
    url = f"{ecwid_base()}/orders"
    # Determine shipping (Pickup) option from store configuration
    ship_opts = []
    try:
        ship_opts = ecwid_get_shipping_options()
    except Exception:
        ship_opts = []
    def _opt_name(o: Dict[str, Any]) -> str:
        return (
            o.get("title")
            or o.get("name")
            or o.get("shippingMethodName")
            or "Pickup"
        )
    def _opt_rate(o: Dict[str, Any]) -> float:
        r = o.get("rate")
        try:
            return float(r) if r is not None else 0.0
        except Exception:
            return 0.0
    pickup = None
    # Prefer explicit pickup options
    for o in ship_opts:
        ft = (o.get("fulfillmentType") or o.get("type") or "").upper()
        name = (_opt_name(o) or "").lower()
        if ft == "PICKUP" or "nouto" in name or "pickup" in name:
            pickup = o
            break
    # Try to include Ecwid method ID if present so Ecwid can apply the exact option's rules
    method_id_any = None  # keep original type (str or int)
    if isinstance(pickup, dict):
        for key in ("id", "shippingMethodId", "methodId"):
            if key in pickup and pickup.get(key) is not None:
                method_id_any = pickup.get(key)
                break
    shipping_option = {
        "shippingMethodName": _opt_name(pickup or {}),
        "shippingRate": _opt_rate(pickup or {}),
        "fulfillmentType": "PICKUP",
    }
    if method_id_any is not None:
        # Ecwid expects `id` for the chosen shipping method; include both for compatibility
        shipping_option["id"] = method_id_any
        shipping_option["shippingMethodId"] = method_id_any

    # Format pickup time as RFC3339-like with explicit offset (Ecwid samples show: YYYY-MM-DD HH:MM:SS +0000)
    pickup_time_str = req.pickup_time
    pickup_date_str = (req.pickup_time or "").split("T")[0].replace("/", "-")
    pickup_time_only = None
    try:
        tzname = os.getenv("LOCAL_TZ", "Europe/Helsinki")
        dt_local = parse_pickup_iso(req.pickup_time)
        if dt_local is not None:
            # Attach proper timezone and format with seconds + offset
            if ZoneInfo:
                dt_z = dt_local.replace(tzinfo=ZoneInfo(tzname))
            else:
                dt_z = dt_local
            pickup_time_str = dt_z.strftime("%Y-%m-%d %H:%M:00 %z")
            pickup_date_str = dt_local.strftime("%Y-%m-%d")
            pickup_time_only = dt_local.strftime("%H:%M")
    except Exception:
        # Fallback to original string if tz conversion fails
        pickup_time_str = req.pickup_time
        pickup_date_str = (req.pickup_time or "").split("T")[0].replace("/", "-")
        try:
            pickup_time_only = req.pickup_time.split('T',1)[1]
        except Exception:
            pickup_time_only = None
    # Compute totals (Ecwid POST /orders is manual: must include subtotal/total)
    try:
        subtotal = 0.0
        for it in items:
            p = float(it.get("price", 0))
            q = int(it.get("quantity", 0))
            subtotal += p * q
        shipping_cost = float(shipping_option.get("shippingRate") or 0.0)
        # Tax handling: flat percentage possibly included in prices
        rate = float(os.getenv("ECWID_TAX_RATE_PERCENT", os.getenv("TAX_RATE_PERCENT", "14"))) / 100.0
        prices_include_tax = (os.getenv("ECWID_TAX_INCLUDED", os.getenv("TAX_PRICES_INCLUDED", "true")).lower() not in {"0","false","no","off"})
        if rate > 0:
            if prices_include_tax:
                tax_amount = round(subtotal * rate / (1.0 + rate), 2)
                total = round(subtotal + shipping_cost, 2)
            else:
                tax_amount = round(subtotal * rate, 2)
                total = round(subtotal + tax_amount + shipping_cost, 2)
        else:
            tax_amount = 0.0
            total = round(subtotal + shipping_cost, 2)
    except Exception:
        subtotal = 0.0
        tax_amount = 0.0
        total = 0.0

    first_name, last_name = _split_name(req.name)
    display_name = " ".join([p for p in (first_name, last_name) if p]) or ((req.name or "").strip()) or "Chat Customer"
    contact_block = {
        "name": display_name,
        "phone": req.phone or "",
        "email": req.email or "",
    }

    body = {
        "name": display_name,
        "email": req.email or "",
        "phone": req.phone or "",
        "paymentMethod": "Pay at pickup",
        "paymentStatus": "AWAITING_PAYMENT",
        "shippingOption": shipping_option,
        # Manual totals as per Ecwid API
        "subtotal": round(subtotal, 2),
        "tax": round(tax_amount, 2),
        "total": round(total, 2),
        # Include pickup time in order payload for clarity in Ecwid
        "pickupTime": pickup_time_str,
        # Provide preferred delivery fields as Ecwid scheduled pickup uses these
        "preferredDeliveryDate": pickup_date_str,
        **({"preferredDeliveryTime": pickup_time_only} if pickup_time_only else {}),
        # Provide contact under shippingPerson as well
        "shippingPerson": dict(contact_block),
        "billingPerson": dict(contact_block),
        "items": items,
        "customerComment": " | ".join([p for p in [f"Pickup: {req.pickup_time}", req.note] if p]),
    }
    try:
        # Optional: pre-calculate to validate totals and timing before creating the order
        try:
            calc_url = f"{ecwid_base()}/orders/calculate"
            with httpx.Client(timeout=10.0) as client:
                rc = client.post(calc_url, headers=ecwid_headers(), json={
                    "items": items,
                    "shippingOption": shipping_option,
                    "pickupTime": pickup_time_str,
                })
                if rc.status_code >= 400:
                    # Some stores do not support /orders/calculate and return 404/405. Proceed to create the order.
                    if rc.status_code in (404, 405):
                        logger.info("Ecwid calculate not available (status %s). Proceeding to create order.", rc.status_code)
                    else:
                        # Surface calculation error directly for other statuses
                        detail = rc.text
                        try:
                            j = rc.json()
                            detail = j.get("errorMessage") or j.get("message") or detail
                        except Exception:
                            pass
                        raise HTTPException(status_code=rc.status_code, detail=f"Ecwid calculate error: {detail}")
        except HTTPException:
            raise
        except Exception:
            logger.exception("Ecwid calculate step failed")

        with httpx.Client(timeout=10.0) as client:
            r = client.post(url, headers=ecwid_headers(), json=body)
            r.raise_for_status()
            data = r.json()
        return {"ok": True, "id": data.get("id"), "orderNumber": data.get("orderNumber")}
    except httpx.RequestError as re:
        logger.exception("Ecwid network error")
        raise HTTPException(status_code=502, detail=f"Ecwid network error: {str(re)}")
    except httpx.HTTPStatusError as he:
        # Parse Ecwid error JSON when possible for clearer messages
        status = he.response.status_code
        detail = ""
        try:
            payload = he.response.json()
            if isinstance(payload, dict):
                detail = (
                    payload.get("errorMessage")
                    or payload.get("message")
                    or payload.get("error")
                    or ""
                )
                errs = payload.get("errors")
                if (not detail) and isinstance(errs, list) and errs:
                    detail = str(errs[0])
        except Exception:
            # Fall back to raw text if body isn't JSON
            detail = (he.response.text or "").strip()
        if not detail:
            if status == 403:
                detail = "Ecwid API error 403: Forbidden. Check that ECWID_API_TOKEN has write access to Orders for this store."
            else:
                detail = f"Ecwid API error {status}"
        raise HTTPException(status_code=status, detail=detail)
    except Exception as e:
        logger.exception("Order creation failed")
        raise HTTPException(status_code=502, detail=f"Failed to create order: {e.__class__.__name__}: {str(e)}")
