import unittest
from fastapi.testclient import TestClient
from backend.app import app


class TestFAQAnswersSV(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _chat(self, msg: str) -> str:
        r = self.client.post('/api/chat', json={'message': msg, 'lang': 'sv'})
        self.assertEqual(r.status_code, 200)
        return (r.json().get('reply') or '')

    def test_location_sv(self):
        reply = self._chat('Var ligger ni?')
        self.assertIn('Kumpulantie 15', reply)
        self.assertTrue('Helsing' in reply or 'Helsingfors' in reply)

    def test_hours_sv(self):
        reply = self._chat('Vilka är era öppettider?')
        self.assertIn('torsdagar', reply)
        self.assertIn('lördagar', reply)
        self.assertIn('11', reply)
        self.assertIn('17', reply)
        self.assertIn('15', reply)

    def test_lead_time_sv(self):
        reply = self._chat('Hur långt i förväg bör jag beställa?')
        self.assertIn('dagen innan', reply)

    def test_minimum_order_sv(self):
        reply = self._chat('Har ni någon minsta beställning?')
        self.assertIn('Minsta beställningen är 10 euro', reply)

    def test_payment_sv(self):
        reply = self._chat('Accepterar ni betalkort och mobilbetalningar?')
        self.assertIn('endast kort', reply)
        self.assertIn('nästan alla', reply)

    def test_prepayment_sv(self):
        reply = self._chat('Kräver ni förskottsbetalning för beställningsprodukter?')
        self.assertTrue('över 150' in reply or '150' in reply)

    def test_nuts_sv(self):
        reply = self._chat('Hur beaktar ni nötallergier?')
        self.assertTrue('inga nötter' in reply.lower())

    def test_gluten_sv(self):
        reply = self._chat('Har ni glutenfria alternativ?')
        self.assertIn('inga glutenfria', reply.lower())


class TestFAQAnswersEN(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _chat(self, msg: str) -> str:
        r = self.client.post('/api/chat', json={'message': msg, 'lang': 'en'})
        self.assertEqual(r.status_code, 200)
        return (r.json().get('reply') or '')

    def test_location_en(self):
        reply = self._chat('Where are you located?')
        self.assertIn('Kumpulantie 15', reply)
        self.assertIn('Helsinki', reply)

    def test_hours_en(self):
        reply = self._chat('What are your opening hours?')
        self.assertIn('Thursdays', reply)
        self.assertIn('Saturdays', reply)
        # Accept either 24h numbers or am/pm formatting
        self.assertTrue(('17' in reply and '15' in reply) or ('5 pm' in reply.lower() and '3 pm' in reply.lower()))

    def test_lead_time_en(self):
        reply = self._chat('How early should I place my order?')
        self.assertIn('day before', reply.lower())

    def test_minimum_order_en(self):
        reply = self._chat('Is there a minimum order amount?')
        self.assertTrue('€10' in reply or '10 euro' in reply.lower())

    def test_payment_en(self):
        reply = self._chat('Do you accept payment cards and mobile payments?')
        self.assertIn('card only', reply.lower())
        self.assertIn('almost all cards', reply.lower())

    def test_prepayment_en(self):
        reply = self._chat('Do you require prepayment for orders?')
        self.assertTrue('over €150' in reply.lower() or 'over 150' in reply.lower())

    def test_nuts_en(self):
        reply = self._chat('How do you handle nut allergies?')
        self.assertIn('no nuts', reply.lower())

    def test_gluten_en(self):
        reply = self._chat('Do you have gluten-free options?')
        self.assertTrue('do not have' in reply.lower() and 'gluten' in reply.lower())


if __name__ == '__main__':
    unittest.main()
