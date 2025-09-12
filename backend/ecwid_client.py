from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx


def _require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"{name} is not set")
    return val


def ecwid_base() -> str:
    store_id = _require_env("ECWID_STORE_ID")
    return f"https://app.ecwid.com/api/v3/{store_id}"


def ecwid_headers() -> Dict[str, str]:
    token = _require_env("ECWID_API_TOKEN")
    # Some Ecwid deployments expect X-Ecwid-Api-Token, others accept Bearer auth.
    # Send both headers (safe and supported) for maximum compatibility.
    return {
        "Authorization": f"Bearer {token}",
        "X-Ecwid-Api-Token": token,
        "X-Ecwid-Token": token,
        "Content-Type": "application/json",
    }


def get_products(limit: int = 100, category: Optional[int] = None) -> List[Dict[str, Any]]:
    base = ecwid_base()
    headers = ecwid_headers()
    url = f"{base}/products"
    params: Dict[str, Any] = {"limit": limit}
    if category is not None:
        params["category"] = int(category)
    with httpx.Client(timeout=10.0) as client:
        r = client.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
    return data.get("items", [])


def get_categories(limit: int = 200) -> List[Dict[str, Any]]:
    base = ecwid_base()
    headers = ecwid_headers()
    url = f"{base}/categories"
    params: Dict[str, Any] = {"limit": limit}
    with httpx.Client(timeout=10.0) as client:
        r = client.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
    return data.get("items", [])


def get_profile() -> Dict[str, Any]:
    base = ecwid_base()
    headers = ecwid_headers()
    url = f"{base}/profile"
    with httpx.Client(timeout=10.0) as client:
        r = client.get(url, headers=headers)
        r.raise_for_status()
        return r.json()


def get_shipping_options() -> List[Dict[str, Any]]:
    base = ecwid_base()
    headers = ecwid_headers()
    url = f"{base}/profile/shippingOptions"
    with httpx.Client(timeout=10.0) as client:
        r = client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
    if isinstance(data, dict):
        return data.get("items", [])
    if isinstance(data, list):
        return data
    return []
