import datetime
import pandas as pd
import requests
import os
import io

def download_instrument_master(url="https://public.fyers.in/sym_details/NSE_FO.csv"):
    """
    Downloads the Fyers instrument master file if it's not already cached.
    """
    cache_dir = ".cache"
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    filename = os.path.join(cache_dir, os.path.basename(url))

    if os.path.exists(filename):
        print("Instrument master file found in cache.")
    else:
        print("Downloading instrument master file...")
        try:
            response = requests.get(url)
            response.raise_for_status()
            with open(filename, "wb") as f:
                f.write(response.content)
            print("Instrument master file downloaded successfully.")
        except requests.exceptions.RequestException as e:
            print(f"Error downloading instrument master file: {e}")
            return None

    try:
        df = pd.read_csv(filename, header=None)
        df.columns = [
            'FyersToken', 'Unknown1', 'InstrumentType', 'ExchangeInstrumentID',
            'MinimumLotSize', 'TickSize', 'ISIN', 'TradingSession',
            'LastUpdateDate', 'ExpiryDate', 'Unknown2', 'StrikePrice',
            'OptionType', 'Unknown3', 'Unknown4', 'tradingsymbol'
        ]
        return df
    except Exception as e:
        print(f"Error reading instrument master file: {e}")
        return None


def get_nearest_weekly_expiry_for_date(instrument_df, index_name, target_date):
    """
    Finds the nearest weekly expiry date for a given index on a specific historical date.
    """
    if index_name == "NIFTY":
        filtered_df = instrument_df[instrument_df['tradingsymbol'].str.startswith('NIFTY')]
    elif index_name == "SENSEX":
        filtered_df = instrument_df[instrument_df['tradingsymbol'].str.startswith('SENSEX')]
    else:
        return None

    options_df = filtered_df[filtered_df['InstrumentType'] == 'OPTIDX']
    expiry_dates = pd.to_datetime(options_df['ExpiryDate'], unit='s').dt.date.unique()

    future_expiries = sorted([d for d in expiry_dates if d >= target_date])
    if not future_expiries:
        return None

    return future_expiries[0]

def fetch_backtesting_data(fyers_api, instrument_df, date, index_name):
    """
    Fetches all required historical data for a single day of backtesting.
    """
    target_date_str = date.strftime("%Y-%m-%d")
    index_symbol = f"NSE:{index_name}50-INDEX" if index_name == "NIFTY" else f"BSE:{index_name}"

    # 1. Fetch index data to find ATM strike at 9:21
    index_data_raw = fyers_api.get_historical_data(index_symbol, "1", "1", target_date_str, target_date_str, "0")
    if index_data_raw.get('s') != 'ok' or not index_data_raw.get('candles'):
        print(f"Could not fetch index data for {target_date_str}")
        return None

    index_df = pd.DataFrame(index_data_raw['candles'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    index_df['timestamp'] = pd.to_datetime(index_df['timestamp'], unit='s')
    index_df.set_index('timestamp', inplace=True)

    time_921 = pd.to_datetime(f"{target_date_str} 09:21:00").tz_localize(index_df.index.tz)
    price_at_921 = index_df.asof(time_921)['close']

    rounding = 50 if index_name == "NIFTY" else 100
    atm_strike = round(price_at_921 / rounding) * rounding
    print(f"[{target_date_str}] ATM Strike determined at 9:21 AM: {atm_strike}")

    # 2. Find relevant option symbols
    expiry_date = get_nearest_weekly_expiry_for_date(instrument_df, index_name, date.date())
    if not expiry_date:
        print(f"Could not find expiry date for {target_date_str}")
        return None

    call_symbol = construct_option_symbol(index_name, expiry_date, atm_strike, "CE")
    put_symbol = construct_option_symbol(index_name, expiry_date, atm_strike, "PE")
    print(f"[{target_date_str}] Using symbols: {call_symbol} and {put_symbol}")

    # 3. Fetch historical data for the options
    call_data_raw = fyers_api.get_historical_data(call_symbol, "1", "1", target_date_str, target_date_str, "0")
    put_data_raw = fyers_api.get_historical_data(put_symbol, "1", "1", target_date_str, target_date_str, "0")

    if call_data_raw.get('s') != 'ok' or not call_data_raw.get('candles') or \
       put_data_raw.get('s') != 'ok' or not put_data_raw.get('candles'):
        print(f"Could not fetch options data for {target_date_str}")
        return None

    call_df = pd.DataFrame(call_data_raw['candles'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    put_df = pd.DataFrame(put_data_raw['candles'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    # 4. Merge and create combined premium chart
    merged_df = pd.merge(call_df, put_df, on='timestamp', suffixes=('_call', '_put'))
    merged_df['timestamp'] = pd.to_datetime(merged_df['timestamp'], unit='s')

    combined_df = pd.DataFrame()
    combined_df['timestamp'] = merged_df['timestamp']
    combined_df['open'] = merged_df['open_call'] + merged_df['open_put']
    combined_df['high'] = merged_df['high_call'] + merged_df['high_put']
    combined_df['low'] = merged_df['low_call'] + merged_df['low_put']
    combined_df['close'] = merged_df['close_call'] + merged_df['close_put']
    combined_df['volume'] = merged_df['volume_call'] + merged_df['volume_put']

    return combined_df.set_index('timestamp'), atm_strike

def get_nearest_weekly_expiry(instrument_df, index_name):
    """
    Finds the nearest weekly expiry date for a given index.
    """
    today = datetime.date.today()
    return get_nearest_weekly_expiry_for_date(instrument_df, index_name, today)

def construct_option_symbol(index_name, expiry_date, strike, option_type):
    """
    Constructs the Fyers symbol for an option contract.
    e.g., NSE:NIFTY23OCT18500CE
    """
    expiry_str = expiry_date.strftime("%y%b%d").upper()
    if index_name == "NIFTY":
        return f"NSE:NIFTY{expiry_str}{strike}{option_type}"
    elif index_name == "SENSEX":
        return f"BSE:SENSEX{expiry_str}{strike}{option_type}"
    return None
