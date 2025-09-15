import os
import unittest
from fastapi.testclient import TestClient
from backend.app import app


class TestOrderingDisabled(unittest.TestCase):
    def setUp(self):
        # Ensure flag is disabled
        os.environ['ENABLE_CHAT_ORDERING'] = 'false'
        self.client = TestClient(app)

    def test_v2_order_blocked(self):
        payload = {
            "items": [
                {"productId": 123, "sku": "X", "name": "Test", "quantity": 1}
            ],
            "name": "Test",
            "phone": "+358 000",
            "pickup_time": "2025-09-19T12:00",
        }
        r = self.client.post('/api/v2/order', json=payload)
        self.assertEqual(r.status_code, 403)
        self.assertIn('disabled', (r.json().get('detail') or '').lower())

    def test_legacy_order_blocked(self):
        payload = {
            "items": [
                {"productId": 123, "sku": "X", "quantity": 1}
            ],
            "name": "Test",
            "phone": "+358 000",
            "pickup_time": "2025-09-19T12:00",
        }
        r = self.client.post('/api/order', json=payload)
        self.assertEqual(r.status_code, 403)
        self.assertIn('disabled', (r.json().get('detail') or '').lower())


if __name__ == '__main__':
    unittest.main()

