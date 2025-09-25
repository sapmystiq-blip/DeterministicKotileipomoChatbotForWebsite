import unittest
from fastapi.testclient import TestClient
from backend.app import app


class TestFAQAnswers(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _chat(self, msg: str) -> str:
        r = self.client.post('/api/chat', json={'message': msg, 'lang': 'fi'})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        return data.get('reply') or ''

    def test_location_answer_fi(self):
        reply = self._chat('Missä sijaitsette?')
        self.assertIn('Leipomomyymälämme sijaitsee osoitteessa Kumpulantie 15, 00520 Helsinki', reply)

    def test_hours_answer_fi(self):
        reply = self._chat('Mitkä ovat aukioloaikanne?')
        self.assertIn('Olemme avoinna torstaisin ja perjantaisin klo 11-17 ja lauantaisin klo 11-15', reply)

    def test_order_lead_time_answer_fi(self):
        reply = self._chat('Kuinka ajoissa minun tulee tehdä tilaus?')
        self.assertIn('Verkkokauppatilaukset tulee tehdä edellisenä päivänä. Isommat tilaukset mielellään jo aiemmin', reply)

    def test_minimum_order_answer_fi(self):
        reply = self._chat('Onko minimitilausmäärää?')
        self.assertIn('Minimitilaus on 10 euroa', reply)
        self.assertIn('Myymälästä saa toki tulla ostamaan yhdenkin piirakan kerrallaan', reply)

    def test_payment_methods_answer_fi(self):
        reply = self._chat('Hyväksyttekö maksukortit ja mobiilimaksut?')
        self.assertIn('Hyväksymme yleisimmät pankki- ja luottokortit', reply)
        self.assertIn('Emme hyväksy MobilePayta', reply)

    def test_prepayment_answer_fi(self):
        reply = self._chat('Vaaditteko ennakkomaksua tilaustuotteista?')
        self.assertIn('Tuotteet maksetaan noudettaessa', reply)
        # Be tolerant about the euro sign/formatting
        self.assertTrue('(yli 150' in reply or 'yli 150' in reply)

    def test_weekday_pickup_keskiviikko(self):
        reply = self._chat('Voinko noutaa keskiviikkona?')
        self.assertIn('sopimuksen mukaan', reply)
        self.assertIn('rakaskotileipomo@gmail.com', reply)

    def test_weekday_pickup_sunnuntai(self):
        reply = self._chat('Voinko noutaa sunnuntaina?')
        self.assertTrue('ei noutoa' in reply.lower())

    def test_weekday_pickup_torstai(self):
        reply = self._chat('Voinko noutaa torstaina?')
        self.assertIn('aukioloaikoina', reply)

    def test_custom_cakes_policy_fi(self):
        reply = self._chat('Valmistatteko tilaustyönä kakkuja tai leivonnaisia?')
        self.assertIn('Emme leivo kakkuja', reply)
        self.assertIn('voileipäkakkuja', reply)
        self.assertIn('karjalanpiirakkaleipomo', reply)

    def test_no_cake_queries_map_to_policy(self):
        for q in ['onko täytekakku', 'onko kuivakakkuja', 'onko voileipäkakku', 'onko lihapiirakka', 'onko kakkuja', 'onko kakku']:
            reply = self._chat(q)
            self.assertIn('Emme leivo kakkuja', reply)

    def test_nut_allergy_answer_fi(self):
        reply = self._chat('Miten huomioitte pähkinäallergiat?')
        self.assertIn('Tuotteissamme ja leipomossamme ei ole pähkinöitä', reply)

    def test_gluten_free_answer_fi(self):
        reply = self._chat('Onko teillä gluteenittomia vaihtoehtoja?')
        self.assertIn('Meillä ei ole valitettavasti gluteenittomia tuotteita', reply)
        self.assertIn('Tilamme eivät sovellu gluteenittomaan leivontaan', reply)


if __name__ == '__main__':
    unittest.main()
