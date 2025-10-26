import datetime
import time
import pandas as pd
import numpy as np
from stocktrends import Renko
from trading_bot.api.fyers import FyersAPI
from trading_bot.core.models import Candle, CombinedPremium
from trading_bot.utils.helpers import get_nearest_weekly_expiry, construct_option_symbol
import trading_bot.config as config

class TradingStrategy:
    def __init__(self, fyers_api: FyersAPI, index: str, instrument_df, backtest=False):
        self.fyers_api = fyers_api
        self.index = index
        self.instrument_df = instrument_df
        self.backtest = backtest
        self.atm_strike = None
        self.opening_range_high = None
        self.opening_range_low = None
        self.bull_breakout_confirmed = False
        self.trade_log = pd.DataFrame(columns=['EntryTime', 'EntryPrice', 'EntryCondition', 'ExitTime', 'ExitPrice', 'ExitReason', 'PnL'])
        self.combined_premium_df = pd.DataFrame()
        self.in_trade = False
        self.entry_condition = None
        self.entry_price = None
        self.entry_time = None
        self.re_entry_count = 0
        self.last_exit_time = None
        self.capital = config.CAPITAL
        self.lot_size = None

    def calculate_lot_size(self):
        """
        Calculates the lot size based on capital and expiry day.
        """
        is_expiry_day = datetime.date.today().weekday() == 3  # Thursday is 3

        if is_expiry_day:
            self.lot_size = int(self.capital / 175000)
        else:
            self.lot_size = int(self.capital / 120000)

        print(f"[{datetime.datetime.now()}] Lot size calculated as: {self.lot_size}")

    def get_atm_strike(self):
        """
        Fetches the index close at 9:21 AM and calculates the ATM strike.
        """
        if self.index == "NIFTY":
            symbol = "NSE:NIFTY50-INDEX"
            rounding = 50
        elif self.index == "SENSEX":
            symbol = "BSE:SENSEX"
            rounding = 100
        else:
            raise ValueError("Invalid index specified.")

        try:
            quote = self.fyers_api.get_quotes([symbol])
            if quote and quote['s'] == 'ok':
                index_price = quote['d'][0]['v']['lp']
                self.atm_strike = round(index_price / rounding) * rounding
                print(f"[{datetime.datetime.now()}] ATM Strike for {self.index} calculated at {self.atm_strike}")
            else:
                print(f"[{datetime.datetime.now()}] Error fetching index price: {quote}")
                index_price = 18534.10 if self.index == "NIFTY" else 62501.69
                self.atm_strike = round(index_price / rounding) * rounding
                print(f"[{datetime.datetime.now()}] Using fallback ATM Strike: {self.atm_strike}")
        except Exception as e:
            print(f"[{datetime.datetime.now()}] An exception occurred while fetching ATM strike: {e}")
            index_price = 18534.10 if self.index == "NIFTY" else 62501.69
            self.atm_strike = round(index_price / rounding) * rounding
            print(f"[{datetime.datetime.now()}] Using fallback ATM Strike on exception: {self.atm_strike}")

    def calculate_opening_range(self):
        """
        Calculates the opening range high and low from the combined premium chart.
        """
        if self.atm_strike is None:
            print("ATM strike not calculated yet.")
            return

        expiry_date = get_nearest_weekly_expiry(self.instrument_df, self.index)
        if not expiry_date:
            print(f"Could not find a valid weekly expiry for {self.index}.")
            return

        call_symbol = construct_option_symbol(self.index, expiry_date, self.atm_strike, "CE")
        put_symbol = construct_option_symbol(self.index, expiry_date, self.atm_strike, "PE")

        today_str = datetime.date.today().strftime("%Y-%m-%d")
        range_from = f"{today_str}"
        range_to = f"{today_str}"

        try:
            call_data = self.fyers_api.get_historical_data(call_symbol, "1", "1", range_from, range_to, "0")
            put_data = self.fyers_api.get_historical_data(put_symbol, "1", "1", range_from, range_to, "0")

            if call_data['s'] != 'ok' or put_data['s'] != 'ok':
                print(f"[{datetime.datetime.now()}] Error fetching historical data: {call_data} | {put_data}")
                return

            call_df = pd.DataFrame(call_data['candles'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            put_df = pd.DataFrame(put_data['candles'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

            call_df['timestamp'] = pd.to_datetime(call_df['timestamp'], unit='s')
            put_df['timestamp'] = pd.to_datetime(put_df['timestamp'], unit='s')

            call_df.set_index('timestamp', inplace=True)
            put_df.set_index('timestamp', inplace=True)

            call_df = call_df.between_time('09:15', '09:21')
            put_df = put_df.between_time('09:15', '09:21')

        except Exception as e:
            print(f"[{datetime.datetime.now()}] An exception occurred while fetching historical data: {e}")
            return

        self.combined_premium_df['open'] = call_df['open'] + put_df['open']
        self.combined_premium_df['high'] = call_df['high'] + put_df['high']
        self.combined_premium_df['low'] = call_df['low'] + put_df['low']
        self.combined_premium_df['close'] = call_df['close'] + put_df['close']
        self.combined_premium_df['volume'] = call_df['volume'] + put_df['volume']

        self.opening_range_high = self.combined_premium_df['high'].max()
        self.opening_range_low = self.combined_premium_df['low'].min()

        print(f"[{datetime.datetime.now()}] Opening Range High: {self.opening_range_high}")
        print(f"[{datetime.datetime.now()}] Opening Range Low: {self.opening_range_low}")

    def calculate_indicators(self):
        """
        Calculates VWAP and EMA bands on the combined premium data.
        """
        if self.combined_premium_df.empty:
            return

        vp = self.combined_premium_df['volume'] * (self.combined_premium_df['high'] + self.combined_premium_df['low'] + self.combined_premium_df['close']) / 3
        self.combined_premium_df['vwap'] = vp.cumsum() / self.combined_premium_df['volume'].cumsum()

        self.combined_premium_df['ema_high_75'] = self.combined_premium_df['high'].ewm(span=75, adjust=False).mean()
        self.combined_premium_df['ema_low_75'] = self.combined_premium_df['low'].ewm(span=75, adjust=False).mean()
        self.combined_premium_df['upper_band'] = self.combined_premium_df['ema_high_75'].rolling(window=9).mean()
        self.combined_premium_df['lower_band'] = self.combined_premium_df['ema_low_75'].rolling(window=9).mean()

    def calculate_hedge_offset_and_strikes(self, combined_premium):
        """
        Calculates the hedge offset and OTM strikes.
        """
        hedge_offset = round((combined_premium * 3) / (50 if self.index == "NIFTY" else 100)) * (50 if self.index == "NIFTY" else 100)
        otm_call_strike = self.atm_strike + hedge_offset
        otm_put_strike = self.atm_strike - hedge_offset
        return otm_call_strike, otm_put_strike

    def enter_trade(self, condition, price, timestamp):
        """
        Enters a short straddle trade.
        """
        self.in_trade = True
        self.entry_condition = condition
        self.entry_price = price
        self.entry_time = timestamp

        otm_call_strike, otm_put_strike = self.calculate_hedge_offset_and_strikes(price)

        print(f"[{timestamp}] Entering trade due to {condition} at {price}")
        print(f"[{timestamp}] ATM Strike: {self.atm_strike}, Hedge Strikes: {otm_call_strike} (Call), {otm_put_strike} (Put)")

        if not self.backtest:
            expiry_date = get_nearest_weekly_expiry(self.instrument_df, self.index)
            short_call_symbol = construct_option_symbol(self.index, expiry_date, self.atm_strike, "CE")
            short_put_symbol = construct_option_symbol(self.index, expiry_date, self.atm_strike, "PE")
            long_call_symbol = construct_option_symbol(self.index, expiry_date, otm_call_strike, "CE")
            long_put_symbol = construct_option_symbol(self.index, expiry_date, otm_put_strike, "PE")

            orders = [
                {"symbol": short_call_symbol, "qty": self.lot_size, "type": 2, "side": -1, "productType": "INTRADAY"},
                {"symbol": short_put_symbol, "qty": self.lot_size, "type": 2, "side": -1, "productType": "INTRADAY"},
                {"symbol": long_call_symbol, "qty": self.lot_size, "type": 2, "side": 1, "productType": "INTRADAY"},
                {"symbol": long_put_symbol, "qty": self.lot_size, "type": 2, "side": 1, "productType": "INTRADAY"},
            ]
            for order in orders:
                response = self.fyers_api.place_order(**order)
                print(f"[{timestamp}] Order placement response: {response}")

    def exit_trade(self, reason, price, timestamp):
        """
        Exits the current trade.
        """
        self.in_trade = False
        self.last_exit_time = timestamp
        pnl = self.entry_price - price

        print(f"[{timestamp}] Exiting trade due to {reason} at {price}. PnL: {pnl}")

        if self.backtest:
            new_log = pd.DataFrame([{
                'EntryTime': self.entry_time,
                'EntryPrice': self.entry_price,
                'EntryCondition': self.entry_condition,
                'ExitTime': timestamp,
                'ExitPrice': price,
                'ExitReason': reason,
                'PnL': pnl
            }])
            self.trade_log = pd.concat([self.trade_log, new_log], ignore_index=True)
        else:
            # The exit_positions method is not in the Fyers API wrapper.
            # A more robust implementation would be to cancel all open orders and square off all positions.
            print(f"[{timestamp}] Exiting all positions (simulation).")

    def calculate_supertrend(self, df):
        """Calculates the SuperTrend indicator."""
        if self.index == "NIFTY":
            st_length, st_multiplier = 10, 4
        else:
            st_length, st_multiplier = 10, 3

        df['tr0'] = abs(df["high"] - df["low"])
        df['tr1'] = abs(df["high"] - df["close"].shift(1))
        df['tr2'] = abs(df["low"] - df["close"].shift(1))
        df["tr"] = round(df[['tr0', 'tr1', 'tr2']].max(axis=1), 2)
        df["atr"] = df['tr'].rolling(st_length).mean()

        df['upper_basic'] = df['high'] + (st_multiplier * df['atr'])
        df['lower_basic'] = df['low'] - (st_multiplier * df['atr'])
        df['upper_band_st'] = df['upper_basic']
        df['lower_band_st'] = df['lower_basic']

        for i in range(st_length, len(df)):
            if df['close'][i-1] <= df['upper_band_st'][i-1]:
                df.loc[df.index[i], 'upper_band_st'] = min(df['upper_basic'][i], df['upper_band_st'][i-1])
            else:
                df.loc[df.index[i], 'upper_band_st'] = df['upper_basic'][i]

        for i in range(st_length, len(df)):
            if df['close'][i-1] >= df['lower_band_st'][i-1]:
                df.loc[df.index[i], 'lower_band_st'] = max(df['lower_basic'][i], df['lower_band_st'][i-1])
            else:
                df.loc[df.index[i], 'lower_band_st'] = df['lower_basic'][i]

        df['supertrend'] = 0.0
        for i in range(st_length, len(df)):
            if df['close'][i] <= df['upper_band_st'][i]:
                df.loc[df.index[i], 'supertrend'] = df['upper_band_st'][i]
            else:
                df.loc[df.index[i], 'supertrend'] = df['lower_band_st'][i]

        return df

    def check_re_entry_conditions(self, current_premium, timestamp):
        """
        Checks the re-entry conditions for a short straddle.
        """
        if self.in_trade or self.re_entry_count >= 3:
            return

        current_time = timestamp

        if self.last_exit_time and (current_time - self.last_exit_time).total_seconds() < 120:
            return

        print(f"[{current_time}] Checking re-entry conditions...")

        if not self.backtest:
            self.get_atm_strike()

        self.combined_premium_df = self.calculate_supertrend(self.combined_premium_df)
        last_candle = self.combined_premium_df.iloc[-1]
        supertrend_value = last_candle['supertrend']

        multiplier = 0.99 if self.index == "NIFTY" else 0.98

        if current_premium < (supertrend_value * multiplier):
            self.re_entry_count += 1
            self.enter_trade(f"RE_ENTRY_{self.re_entry_count}", current_premium, current_time)
            return

    def check_exit_conditions(self, current_premium, timestamp):
        """
        Checks the exit conditions for the current trade.
        """
        if not self.in_trade:
            return

        current_time = timestamp
        last_candle = self.combined_premium_df.iloc[-1]

        max_loss = 20 if self.index == "NIFTY" else 60
        if (self.entry_price - current_premium) < -max_loss:
            self.exit_trade("MAX_LOSS", current_premium, current_time)
            return

        if current_time.time() >= datetime.time(15, 29):
            self.exit_trade("EOD", current_premium, current_time)
            return

        if "RE_ENTRY" in self.entry_condition:
            supertrend_value = last_candle['supertrend']
            multiplier = 1.01 if self.index == "NIFTY" else 1.02
            if current_premium > (supertrend_value * multiplier):
                self.exit_trade("SUPER_TREND_EXIT", current_premium, current_time)
                return
        elif self.entry_condition in ["ORL_BREAKDOWN", "VWAP_BREAKDOWN"]:
            if current_premium > (last_candle['upper_band'] * 1.01):
                self.exit_trade("UPPER_BAND_CROSS", current_premium, current_time)
                return
            if current_premium > (last_candle['vwap'] * 1.05):
                self.exit_trade("VWAP_CROSS", current_premium, current_time)
                return
        elif self.entry_condition == "FAILED_BULL_BREAKOUT":
            if current_premium > (last_candle['upper_band'] * 1.01):
                self.exit_trade("UPPER_BAND_CROSS", current_premium, current_time)
                return

    def check_entry_conditions(self, current_premium, timestamp):
        """
        Checks the entry conditions for a short straddle.
        """
        if self.in_trade:
            return

        current_time = timestamp
        last_candle = self.combined_premium_df.iloc[-1]

        if current_premium < (self.opening_range_low * 0.98):
            self.enter_trade("ORL_BREAKDOWN", current_premium, current_time)
            return

        if current_premium < (last_candle['vwap'] * 0.99):
            self.enter_trade("VWAP_BREAKDOWN", current_premium, current_time)
            return

        if self.bull_breakout_confirmed:
            if current_premium < (self.opening_range_high * 0.98):
                self.enter_trade("FAILED_BULL_BREAKOUT", current_premium, current_time)
                return
        elif current_premium > self.opening_range_high:
            self.bull_breakout_confirmed = True
            print(f"[{current_time}] Bull breakout confirmed.")

    def on_websocket_message(self, message):
        """
        Callback function to handle incoming websocket messages.
        """
        if 'ltp' in message:
            symbol = message['symbol']
            ltp = message['ltp']

            if symbol == self.call_symbol:
                self.call_ltp = ltp
            elif symbol == self.put_symbol:
                self.put_ltp = ltp

            if self.call_ltp is not None and self.put_ltp is not None:
                current_premium = self.call_ltp + self.put_ltp

                current_time = datetime.datetime.now()
                if not self.in_trade:
                    self.check_entry_conditions(current_premium, current_time)
                    self.check_re_entry_conditions(current_premium, current_time)
                else:
                    self.check_exit_conditions(current_premium, current_time)

    def run_backtest(self, historical_data, atm_strike):
        """
        Runs the backtesting simulation for a single day.
        """
        print(f"Running backtest for {historical_data.index[0].date()}...")
        self.atm_strike = atm_strike
        self.calculate_lot_size()

        opening_range_data = historical_data.between_time('09:15', '09:21')
        if opening_range_data.empty:
            print("Not enough data to calculate opening range.")
            return

        self.opening_range_high = opening_range_data['high'].max()
        self.opening_range_low = opening_range_data['low'].min()
        print(f"ORH: {self.opening_range_high}, ORL: {self.opening_range_low}")

        trading_data = historical_data.between_time('09:22', '15:29')

        for timestamp, candle in trading_data.iterrows():
            current_premium = candle['close']

            live_data_subset = historical_data.loc[:timestamp]
            self.combined_premium_df = live_data_subset.copy()
            self.calculate_indicators()

            if not self.in_trade:
                self.check_entry_conditions(current_premium, timestamp)
                self.check_re_entry_conditions(current_premium, timestamp)
            else:
                self.check_exit_conditions(current_premium, timestamp)

        print("Backtest for the day finished.")

    def run(self):
        """
        Main loop for live trading.
        """
        if self.backtest:
            print("Strategy is in backtest mode. Use run_backtest() for simulations.")
            return

        print(f"[{datetime.datetime.now()}] Starting trading strategy for {self.index}")
        self.get_atm_strike()
        self.calculate_opening_range()
        self.calculate_indicators()

        expiry_date = get_nearest_weekly_expiry(self.instrument_df, self.index)
        self.call_symbol = construct_option_symbol(self.index, expiry_date, self.atm_strike, "CE")
        self.put_symbol = construct_option_symbol(self.index, expiry_date, self.atm_strike, "PE")
        self.call_ltp = None
        self.put_ltp = None

        access_token = f"{self.fyers_api.client_id}:{self.fyers_api.fyers.token}"
        fyers_ws = fyersModel.FyersSocket(access_token=access_token, log_path="")
        fyers_ws.on_message = self.on_websocket_message
        fyers_ws.subscribe(symbols=[self.call_symbol, self.put_symbol], data_type="symbolData")

        print(f"[{datetime.datetime.now()}] WebSocket connected and subscribed to symbols.")
        while datetime.datetime.now().time() < datetime.time(15, 30):
            time.sleep(1)
        print(f"[{datetime.datetime.now()}] Trading session finished.")
