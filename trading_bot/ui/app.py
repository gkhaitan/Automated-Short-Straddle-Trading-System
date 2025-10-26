import streamlit as st
import sys
import os
from contextlib import contextmanager
from io import StringIO

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.fyers import FyersAPI
from core.strategy import TradingStrategy
from utils.helpers import download_instrument_master
import config

# A simple context manager to redirect stdout to a string
@contextmanager
def st_capture(output_func):
    with StringIO() as stdout, redirect_stdout(stdout):
        old_write = stdout.write

        def new_write(data):
            old_write(data)
            output_func(stdout.getvalue())

        stdout.write = new_write
        yield


def main():
    st.title("Automated Short Straddle Trading System")

    st.sidebar.header("Configuration")
    index = st.sidebar.selectbox("Select Index", ["NIFTY", "SENSEX"])

    fyers_api = FyersAPI()
    if 'access_token' not in st.session_state:
        auth_code = st.text_input("Enter Fyers Auth Code")
        if st.button("Generate Token"):
            try:
                fyers_api.set_access_token(auth_code)
                st.session_state.access_token = fyers_api.fyers.token
                st.success("Access Token Generated!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to generate token: {e}")

    if st.button("Start Auto-Trading") and 'access_token' in st.session_state:
        st.info("Starting the automated trading system...")

        log_placeholder = st.empty()
        log_text = ""

        def append_log(message):
            nonlocal log_text
            log_text = message
            log_placeholder.text_area("Live Logs", log_text, height=400)

        instrument_df = download_instrument_master()
        if instrument_df is None:
            st.error("Failed to load instrument master. Cannot start trading.")
            return

        # We need to run the strategy in a way that doesn't block the UI thread.
        # For simplicity here, we'll just run it directly, but a real app
        # would use threading or asyncio.
        with st_capture(append_log):
             try:
                 # FyersAPI instance needs to be properly authenticated here
                 fyers_api = FyersAPI()
                 # auth_code = ...
                 # fyers_api.set_access_token(auth_code)

                 strategy = TradingStrategy(fyers_api, index, instrument_df)
                 strategy.run()

             except Exception as e:
                 st.error(f"An error occurred: {e}")

        st.success("Trading session finished.")

if __name__ == "__main__":
    from streamlit.helpers import redirect_stdout
    main()
