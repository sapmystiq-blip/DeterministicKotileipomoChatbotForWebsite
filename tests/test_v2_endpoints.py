import unittest
from fastapi.testclient import TestClient
from backend.app import app


class TestV2Endpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_v2_pickup_hours(self):
        r = self.client.get('/api/v2/pickup_hours')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('hours', data)
        self.assertIsInstance(data['hours'], dict)

    def test_v2_order_constraints(self):
        r = self.client.get('/api/v2/order_constraints')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('min_lead_minutes', data)
        self.assertIn('max_days', data)


if __name__ == '__main__':
    unittest.main()

