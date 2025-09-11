import unittest
from backend.order_constraints import infer_constraints


class TestConstraints(unittest.TestCase):
    def test_infer_from_shipping_options_sample(self):
        shipping_options = [
            {
                "id": "4495-1651228010529",
                "title": "Nouto VALLILAN myymälästä",
                "enabled": True,
                "fulfilmentType": "pickup",
                "blackoutDates": [
                    {"fromDate": "2025-10-08", "toDate": "2025-10-11", "repeatedAnnually": False}
                ],
                "scheduled": True,
                "fulfillmentTimeInMinutes": 660,
                "availabilityPeriod": "ONE_MONTH",
            }
        ]
        profile = {"settings": {"shipping": {}}}

        res = infer_constraints(
            shipping_options,
            profile,
            default_min_lead_minutes=720,
            default_max_days=60,
        )

        self.assertEqual(res["min_lead_minutes"], 660)
        self.assertEqual(res["max_days"], 30)
        self.assertEqual(
            res["blackout_dates"],
            [{"from": "2025-10-08", "to": "2025-10-11", "repeatedAnnually": False}],
        )


if __name__ == "__main__":
    unittest.main()
