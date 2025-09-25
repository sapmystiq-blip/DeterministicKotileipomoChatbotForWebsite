import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.app import app


def _next_open_slot(start: datetime) -> datetime:
    # App hours: Thu/Fri 11-17, Sat 11-15
    d = start
    for _ in range(14):
        d += timedelta(days=1)
        if d.weekday() in (3, 4, 5):
            return d.replace(hour=12, minute=0, second=0, microsecond=0)
    return start + timedelta(days=1)


class TestOrderValidation(unittest.TestCase):
    def test_order_rejects_under_lead_time(self):
        with TestClient(app) as client:
            with patch("backend.app.api_order_constraints", return_value={
                "min_lead_minutes": 100000,
                "max_days": 60,
                "blackout_dates": [],
            }):
                now = datetime.now()
                slot = _next_open_slot(now)
                too_soon = slot
                payload = {
                    "items": [{"productId": 123, "quantity": 1}],
                    "name": "Test",
                    "phone": "+358 000",
                    "pickup_time": too_soon.strftime("%Y-%m-%dT%H:%M"),
                }
                r = client.post("/api/order", json=payload)
                if r.status_code == 403 and 'disabled' in r.text.lower():
                    self.skipTest('Ordering API is disabled in this environment')
                self.assertEqual(r.status_code, 400)
                self.assertIn("least", r.json().get("detail", ""))

    def test_order_rejects_blackout_date(self):
        with TestClient(app) as client:
            future = datetime.now() + timedelta(days=14)
            future = future.replace(hour=12, minute=0, second=0, microsecond=0)
            bo_from = future.strftime("%Y-%m-%d")
            bo_to = bo_from
            with patch("backend.app.api_order_constraints", return_value={
                "min_lead_minutes": 60,
                "max_days": 60,
                "blackout_dates": [{"from": bo_from, "to": bo_to, "repeatedAnnually": False}],
            }):
                payload = {
                    "items": [{"productId": 123, "quantity": 1}],
                    "name": "Test",
                    "phone": "+358 000",
                    "pickup_time": future.strftime("%Y-%m-%dT%H:%M"),
                }
                r = client.post("/api/order", json=payload)
                if r.status_code == 403 and 'disabled' in r.text.lower():
                    self.skipTest('Ordering API is disabled in this environment')
                self.assertEqual(r.status_code, 400)
                self.assertIn("blackout", r.json().get("detail", "").lower())


if __name__ == "__main__":
    unittest.main()
