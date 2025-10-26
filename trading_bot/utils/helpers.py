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


def get_nearest_weekly_expiry(instrument_df, index_name):
    """
    Finds the nearest weekly expiry date for a given index.
    """
    today = datetime.date.today()

    if index_name == "NIFTY":
        filtered_df = instrument_df[instrument_df['tradingsymbol'].str.startswith('NIFTY')]
    elif index_name == "SENSEX":
        filtered_df = instrument_df[instrument_df['tradingsymbol'].str.startswith('SENSEX')]
    else:
        return None

    options_df = filtered_df[filtered_df['InstrumentType'] == 'OPTIDX']

    expiry_dates = pd.to_datetime(options_df['ExpiryDate'], unit='s').dt.date.unique()

    future_expiries = [d for d in expiry_dates if d >= today]
    if not future_expiries:
        return None

    return min(future_expiries)

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
