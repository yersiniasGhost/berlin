import unittest
import os
import json
import logging
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
import math
from typing import List, Dict
import talib as ta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SchwabSMAAnalysis')

from src.schwab_api.authentication import SchwabClient
from src.data_streamer.schwab_data_link import SchwabDataLink
from src.environments.tick_data import TickData
from src.features.indicators import sma_indicator, sma_crossover


def analyze_schwab_data():
    """Direct analysis of Schwab data without unittest framework"""
    # Load credentials directly
    auth_info = {
        "api_key": "QtfsQiLHpno726ZFgRDtvHA3ZItCAkcQ",
        "api_secret": "RmwUJyBGGgW2r2C7",
        "redirect_uri": "https://127.0.0.1"
    }

    # Create a token path to save authentication
    token_path = "schwab_tokens.json"

    # Create client with the credentials
    client = SchwabClient(
        app_key=auth_info["api_key"],
        app_secret=auth_info["api_secret"],
        redirect_uri=auth_info["redirect_uri"],
        token_path=token_path
    )

    # Authenticate
    print("\n=== AUTHENTICATION PROCESS ===")
    print("A browser window will open. After logging in, copy the ENTIRE URL")
    print("you were redirected to and paste it below when prompted.\n")

    auth_success = client.authenticate(use_local_server=False)
    if not auth_success:
        print("Authentication failed")
        return

    # Get user preferences if needed
    if not client.user_prefs:
        client._get_streamer_info()

    # Analysis parameters
    symbol = "NVDA"
    sma_period = 20
    crossover_value = 0.002  # 0.2%
    timeframe = "1m"  # 5-minute candles
    days_history = 1

    # Set up data link
    print(f"\nSetting up data link for {symbol} with {timeframe} candles...")
    data_link = SchwabDataLink(
        user_prefs=client.user_prefs,
        access_token=client.access_token,
        symbols=[symbol],
        timeframe=timeframe,
        days_history=days_history
    )

    # Load historical data
    print(f"Loading {days_history} days of historical data...")
    success = data_link.load_historical_data()
    if not success:
        print("Failed to load historical data")
        return

    # Get candles for the symbol
    candles = data_link.candle_data.get(symbol, [])
    if not candles:
        print(f"No candles found for {symbol}")
        return

    print(f"Loaded {len(candles)} candles for {symbol}")

    # Calculate SMA
    print(f"Calculating {sma_period}-period SMA...")
    sma_values = sma_indicator(candles, sma_period)

    # Check that SMA calculation worked
    valid_sma_count = np.sum(~np.isnan(sma_values))
    print(f"Calculated {valid_sma_count} valid SMA values")

    # Calculate crossover signals
    print("Detecting SMA crossover signals...")
    parameters = {
        "period": sma_period,
        "crossover_value": crossover_value,
        "trend": "bullish"
    }
    signals = sma_crossover(candles, parameters)

    # Count and print signals
    signal_indices = np.where(signals > 0)[0]
    signal_count = len(signal_indices)
    print(f"Found {signal_count} SMA crossover signals")

    # Print details of signals
    if signal_count > 0:
        print("\nSignal details:")
        for i, idx in enumerate(signal_indices):
            if idx < len(candles):
                candle = candles[idx]
                print(f"Signal {i + 1}: Time={candle.timestamp}, Price=${candle.close:.2f}")

    # Create a simple plot if there's data
    plot_results(candles, sma_values, signals)


def plot_results(candles, sma_values, signals):
    """Plot the results of SMA analysis"""
    try:
        # Extract data for plotting
        timestamps = [candle.timestamp for candle in candles]
        prices = [candle.close for candle in candles]

        # Find signal indices and values
        signal_indices = np.where(signals > 0)[0]
        signal_timestamps = [timestamps[i] for i in signal_indices if i < len(timestamps)]
        signal_prices = [prices[i] for i in signal_indices if i < len(prices)]

        # Create the plot
        plt.figure(figsize=(12, 6))

        # Plot price
        plt.plot(timestamps, prices, label='Close Price', color='blue')

        # Plot SMA (skipping NaN values)
        valid_indices = ~np.isnan(sma_values)
        if np.any(valid_indices):
            plt.plot(
                [timestamps[i] for i in range(len(timestamps)) if valid_indices[i]],
                sma_values[valid_indices],
                label=f'SMA ({int(sma_values.size)})',
                color='orange'
            )

        # Plot signals
        if signal_timestamps:
            plt.scatter(
                signal_timestamps,
                signal_prices,
                color='green',
                marker='^',
                s=100,
                label='Buy Signal'
            )

        # Format the plot
        plt.title('SMA Crossover Analysis')
        plt.xlabel('Time')
        plt.ylabel('Price ($)')
        plt.legend()
        plt.grid(True, alpha=0.3)

        # Format date axis if datetime objects
        if hasattr(timestamps[0], 'strftime'):
            plt.gcf().autofmt_xdate()

        # Save and show plot
        plot_filename = f'sma_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        plt.savefig(plot_filename)
        print(f"\nPlot saved as {plot_filename}")

        plt.tight_layout()
        plt.show()  # Show the plot

    except Exception as e:
        print(f"Error plotting results: {e}")


if __name__ == '__main__':
    analyze_schwab_data()