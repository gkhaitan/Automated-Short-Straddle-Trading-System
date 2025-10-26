import unittest
import pandas as pd
import datetime
from trading_bot.core.strategy import TradingStrategy
from trading_bot.api.fyers import FyersAPI

class TestTradingStrategy(unittest.TestCase):

    def setUp(self):
        # Mock FyersAPI and instrument_df
        self.fyers_api = FyersAPI()

        # Use a future date for expiry to ensure the test passes
        future_expiry = datetime.datetime.now() + datetime.timedelta(days=7)

        self.instrument_df = pd.DataFrame({
            'tradingsymbol': ['NIFTY23OCT18500CE', 'NIFTY23OCT18500PE', 'NIFTY23NOV18500CE'],
            'instrument_type': ['OPTIDX', 'OPTIDX', 'OPTIDX'],
            'expiry_date': [
                int(future_expiry.timestamp()),
                int(future_expiry.timestamp()),
                int((future_expiry + datetime.timedelta(days=30)).timestamp())
            ]
        })
        self.strategy = TradingStrategy(self.fyers_api, "NIFTY", self.instrument_df)

    def test_get_atm_strike(self):
        self.strategy.get_atm_strike()
        self.assertEqual(self.strategy.atm_strike, 18550)

    def test_calculate_opening_range(self):
        self.strategy.get_atm_strike()
        self.strategy.calculate_opening_range()
        self.assertIsNotNone(self.strategy.opening_range_high)
        self.assertIsNotNone(self.strategy.opening_range_low)

if __name__ == '__main__':
    unittest.main()
