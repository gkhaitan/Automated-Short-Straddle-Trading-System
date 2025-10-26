# This file will contain the backtesting logic for the trading strategy.
import argparse
import pandas as pd
from datetime import datetime

# Add the project root to the Python path
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading_bot.core.strategy import TradingStrategy
from trading_bot.api.fyers import FyersAPI
from trading_bot.utils.helpers import download_instrument_master

from trading_bot.utils.helpers import fetch_backtesting_data

def run_backtest(start_date, end_date, index):
    """
    Runs the backtesting simulation for the given date range and index.
    """
    print(f"Starting backtest from {start_date} to {end_date} for {index}...")

    fyers_api = FyersAPI()
    if not fyers_api.fyers:
        try:
            with open(".fyers_auth_code", "r") as f:
                auth_code = f.read().strip()
            fyers_api.set_access_token(auth_code)
        except FileNotFoundError:
            auth_code = fyers_api.generate_auth_code()
            with open(".fyers_auth_code", "w") as f:
                f.write(auth_code)
            fyers_api.set_access_token(auth_code)

    instrument_df = download_instrument_master()
    if instrument_df is None:
        print("Failed to load instrument master. Aborting backtest.")
        return

    all_trade_logs = pd.DataFrame()
    date_range = pd.to_datetime(pd.date_range(start=start_date, end=end_date))

    for current_date in date_range:
        if current_date.weekday() >= 5: # Skip weekends
            continue

        print(f"\n--- Processing {current_date.strftime('%Y-%m-%d')} ---")

        data = fetch_backtesting_data(fyers_api, instrument_df, current_date, index)
        if data is None:
            print(f"Could not fetch data for {current_date.strftime('%Y-%m-%d')}. Skipping.")
            continue

        historical_data, atm_strike = data

        strategy = TradingStrategy(fyers_api, index, instrument_df, backtest=True)
        strategy.run_backtest(historical_data, atm_strike)

        all_trade_logs = pd.concat([all_trade_logs, strategy.trade_log], ignore_index=True)

    # 4. Generate and display performance report
    print("\n--- Backtest Finished ---")
    if not all_trade_logs.empty:
        generate_performance_report(all_trade_logs)
    else:
        print("No trades were made during the backtest period.")

def generate_performance_report(trade_log):
    """
    Generates and prints a performance report from the trade log.
    """
    print("\n--- Performance Report ---")

    total_trades = len(trade_log)
    net_pnl = trade_log['PnL'].sum()

    wins = trade_log[trade_log['PnL'] > 0]
    losses = trade_log[trade_log['PnL'] <= 0]

    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0

    average_profit = wins['PnL'].mean()
    average_loss = losses['PnL'].mean()

    profit_factor = abs(wins['PnL'].sum() / losses['PnL'].sum()) if losses['PnL'].sum() != 0 else float('inf')

    trade_log['CumulativePnL'] = trade_log['PnL'].cumsum()
    max_drawdown = (trade_log['CumulativePnL'].cummax() - trade_log['CumulativePnL']).max()

    print(f"Total Trades: {total_trades}")
    print(f"Net Profit/Loss: {net_pnl:.2f} points")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Average Profit per Trade: {average_profit:.2f} points")
    print(f"Average Loss per Trade: {average_loss:.2f} points")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Max Drawdown: {max_drawdown:.2f} points")

    # Optional: Plotting the equity curve
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 6))
        trade_log['CumulativePnL'].plot()
        plt.title('Equity Curve')
        plt.xlabel('Trade Number')
        plt.ylabel('Cumulative PnL (in points)')
        plt.grid(True)
        plt.savefig('equity_curve.png')
        print("\nEquity curve plot saved to equity_curve.png")
    except ImportError:
        print("\nMatplotlib not found. Skipping equity curve plot. `pip install matplotlib` to enable.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest the short straddle trading strategy.")
    parser.add_argument("--start_date", required=True, help="Start date for the backtest (YYYY-MM-DD)")
    parser.add_argument("--end_date", required=True, help="End date for the backtest (YYYY-MM-DD)")
    parser.add_argument("--index", required=True, choices=["NIFTY", "SENSEX"], help="Index to backtest (NIFTY or SENSEX)")
    args = parser.parse_args()

    run_backtest(args.start_date, args.end_date, args.index)
