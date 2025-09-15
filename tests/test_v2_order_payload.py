import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.app import app


def _next_thu_12(now: datetime) -> str:
    # Thu=3 in Python weekday
    days_ahead = (3 - now.weekday()) % 7
    if days_ahead == 0 and now.hour >= 12:
        days_ahead = 7
    dt = (now + timedelta(days=days_ahead)).replace(hour=12, minute=0, second=0, microsecond=0)
    # Ensure lead time: add 1 day if too soon (< 2h lead buffer for test)
    if dt < now + timedelta(hours=2):
        dt = dt + timedelta(days=7)
    return dt.strftime('%Y-%m-%dT%H:%M')


class TestV2OrderPayload(unittest.TestCase):
    def test_two_real_items_payload(self):
        # Mock Ecwid shipping/profile to present a pickup option
        fake_ship_opts = [
            {
                "id": "4495-1651228010529",
                "title": "Nouto VALLILAN myymälästä",
                "fulfillmentType": "PICKUP",
                "settings": {"pickupPreparationTimeMinutes": 60},
                "availabilityPeriod": "ONE_MONTH",
            }
        ]
        fake_profile = {"settings": {"shipping": {}}}

        # Capture outgoing Ecwid order JSON
        captured = {}

        class FakeResp:
            status_code = 200
            text = ""

            def raise_for_status(self):
                return None

            def json(self):
                return {"id": 123, "orderNumber": "TEST123"}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def post(self, url, headers=None, json=None):
                captured["url"] = url
                captured["headers"] = headers
                captured["json"] = json
                return FakeResp()

        with TestClient(app) as client:
            with patch("backend.routers.orders.ecwid_get_shipping_options", return_value=fake_ship_opts), \
                 patch("backend.routers.orders.ecwid_get_profile", return_value=fake_profile), \
                 patch("backend.routers.orders.httpx.Client", FakeClient):
                payload = {
                    "items": [
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
                    ],
                    "name": "Test",
                    "phone": "+358 000",
                    "email": "test@example.com",
                    "pickup_time": _next_thu_12(datetime.now()),
                }
                r = client.post("/api/v2/order", json=payload)
                self.assertEqual(r.status_code, 200, r.text)

        # Assert payload sent to Ecwid contains both items with productId, sku, and name
        sent = captured.get("json") or {}
        self.assertIn("items", sent)
        self.assertEqual(len(sent["items"]), 2)
        a, b = sent["items"][0], sent["items"][1]
        self.assertEqual(a.get("productId"), 771476057)
        self.assertEqual(a.get("sku"), "00071")
        self.assertIn("name", a)
        self.assertEqual(b.get("productId"), 708500182)
        self.assertEqual(b.get("sku"), "00064")
        self.assertIn("name", b)


if __name__ == "__main__":
    unittest.main()

