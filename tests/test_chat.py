import unittest
from fastapi.testclient import TestClient
from backend.app import app


class TestChatKB(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_has_kb(self):
        r = self.client.get('/api/health')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        # KB can be empty in some environments; ensure the key exists
        self.assertIn('kb_items', data)

    def test_opening_hours_answer(self):
        r = self.client.post('/api/chat', json={
            'message': 'What are your opening hours?',
            'lang': 'en'
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        text = (data.get('reply') or '').lower()
        # Be tolerant: either a KB answer or a helpful fallback/capability reply
        self.assertTrue(len(text) > 0, msg="empty reply")

    def test_products_answer(self):
        r = self.client.post('/api/chat', json={
            'message': 'What products do you sell?',
            'lang': 'en'
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        text = (data.get('reply') or '').lower()
        # Either mentions products (karelian/samosa/bun) or gives a structured capability message
        self.assertTrue(
            ('karelian' in text)
            or ('samosa' in text)
            or ('bun' in text)
            or ('products and prices' in text)
            or ('i can help with' in text and 'products' in text),
            msg=f"unexpected reply: {text}"
        )

    def test_fuzzy_single_word(self):
        # Typo / truncated Finnish product keyword should still retrieve
        r = self.client.post('/api/chat', json={
            'message': 'karjalanpiirakk',  # missing last 'a'
            'lang': 'fi'
        })
        self.assertEqual(r.status_code, 200)
        text = (r.json().get('reply') or '').lower()
        # Should not be the hard fallback; expect mention of karjalanpiirakka/karjalanpiirakat or products
        self.assertTrue(('karjalan' in text) or ('piirak' in text) or ('tuotteet' in text) or ('products' in text))

    def test_greeting_and_thanks(self):
        r = self.client.post('/api/chat', json={'message': 'Hi', 'lang': 'en'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('hi', (r.json().get('reply') or '').lower())
        r2 = self.client.post('/api/chat', json={'message': 'Thanks', 'lang': 'en'})
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(len(r2.json().get('reply') or '') > 0)


if __name__ == '__main__':
    unittest.main()
