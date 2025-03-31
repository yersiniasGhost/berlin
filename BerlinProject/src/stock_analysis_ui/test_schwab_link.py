# test_schwab_link.py
import os
import sys
import time
import logging
from datetime import datetime

# Add the project root to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from stock_analysis_ui.services.schwab_auth import SchwabAuthManager
from data_streamer.schwab_data_link import SchwabDataLink

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SchwabDataLinkTest')


# Test script
def test_schwab_data_link():
    # Initialize authentication
    auth = SchwabAuthManager()

    if not auth.load_tokens():
        print("No tokens found, authenticating...")
        auth.authenticate()

    # Create data link
    data_link = SchwabDataLink(
        user_prefs=auth.user_prefs,
        access_token=auth.access_token,
        symbols=["NVDA", "AAPL"],
        timeframe="1m",
        days_history=1
    )

    # Load historical data
    print("Loading historical data...")
    success = data_link.load_historical_data()
    print(f"Historical data loaded: {success}")

    if success:
        # Print summary
        for symbol in data_link.symbols:
            candles = data_link.candle_data.get(symbol, [])
            print(f"{symbol}: {len(candles)} historical candles")

            if candles:
                first = candles[0]
                last = candles[-1]
                print(f"First: {first.timestamp}, Close: {first.close}")
                print(f"Last: {last.timestamp}, Close: {last.close}")

    # Test iterator
    print("\nTesting serve_next_tick()...")
    count = 0
    try:
        for result in data_link.serve_next_tick():
            if result[0] is None:
                print("None tick received (end of data or day boundary)")
                continue

            tick, idx, day = result
            count += 1

            if count <= 5 or count % 20 == 0:
                print(f"Tick {count}: Symbol {data_link.symbols[day]}, Time {tick.timestamp}, Close ${tick.close:.2f}")

            if count >= 100:
                print("Reached 100 ticks, breaking...")
                break

    except Exception as e:
        print(f"Error during iteration: {e}")
        import traceback
        traceback.print_exc()

    print(f"Processed {count} ticks")

    # Test live mode
    print("\nSwitching to live mode...")
    try:
        data_link.live_mode = True
        data_link.connect()

        print("Waiting for live data (10 seconds)...")
        start_time = time.time()
        live_count = 0

        while time.time() - start_time < 10:
            # Check for new data
            for symbol in data_link.symbols:
                if symbol in data_link.latest_data and data_link.latest_data[symbol]:
                    tick = data_link.latest_data[symbol]
                    live_count += 1
                    print(f"Live tick {live_count}: {symbol} @ {tick.timestamp}, Close: ${tick.close:.2f}")
                    data_link.latest_data[symbol] = None  # Clear so we don't process again

            time.sleep(0.5)

        print(f"Received {live_count} live ticks")

    except KeyboardInterrupt:
        print("Test interrupted by user")
    finally:
        if hasattr(data_link, 'disconnect') and callable(data_link.disconnect):
            data_link.disconnect()
        print("Test completed")


if __name__ == "__main__":
    test_schwab_data_link()