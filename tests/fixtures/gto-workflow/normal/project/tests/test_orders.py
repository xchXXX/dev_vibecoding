import unittest

from modules.orders.domain import quote


class OrderTests(unittest.TestCase):
    def test_quote(self):
        self.assertEqual(quote([{"unit_price_cents": 125, "quantity": 2}]),
                         {"line_amounts": [250], "total_cents": 250})
