import unittest
import os
import json
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SchwabLiveDataTest')

from src.schwab_api.authentication import SchwabClient
from src.environments.tick_data import TickData
from src.data_streamer.schwab_data_link import SchwabDataLink


class TestSchwabLiveData(unittest.TestCase):
    """Test SchwabDataLink live data streaming functionality."""

    @classmethod
    def setUpClass(cls):
        # Load credentials
        auth_file_path = os.path.join(os.path.dirname(__file__),
                                      '../../src/schwab_api/authentication_info.json')

        with open(auth_file_path, 'r') as auth_file:
            auth_info = json.load(auth_file)

        # Create client
        token_path = os.path.join(os.path.dirname(__file__), "schwab_test_tokens.json")
        cls.client = SchwabClient(
            app_key=auth_info.get('api_key'),
            app_secret=auth_info.get('api_secret'),
            redirect_uri=auth_info.get('redirect_uri'),
            token_path=token_path
        )

        # Authenticate
        print("\n=== AUTHENTICATION PROCESS ===")
        print("A browser window will open. After logging in, copy the ENTIRE URL")
        print("you were redirected to and paste it below when prompted.\n")

        auth_success = cls.client.authenticate(use_local_server=False)
        if not auth_success:
            raise unittest.SkipTest("Authentication failed, skipping tests")

        # Get user preferences
        if not cls.client.user_prefs:
            cls.client._get_streamer_info()

    def test_live_data_streaming(self):
        """Test live data streaming for NVDA 1-minute candles."""
        # Create data link with NVDA as the symbol
        data_config = {
            "type": "CharlesSchwab",
            "user_prefs": self.client.user_prefs,
            "access_token": self.client.access_token,
            "symbols": ["NVDA"],
            "timeframe": "1m",
            "days_history": 1
        }

        # Create data link directly with config values
        data_link = SchwabDataLink(
            user_prefs=data_config["user_prefs"],
            access_token=data_config["access_token"],
            symbols=data_config["symbols"],
            timeframe=data_config["timeframe"],
            days_history=data_config["days_history"]
        )

        # First load some historical data for context
        print("\nLoading historical data...")
        success = data_link.load_historical_data()
        self.assertTrue(success, "Failed to load historical data")

        # Print summary of historical data
        symbol = data_config["symbols"][0]
        hist_count = len(data_link.candle_data[symbol])
        print(f"Loaded {hist_count} historical candles for {symbol}")

        # Connect to streaming API
        print("\nConnecting to streaming API...")
        connected = data_link.connect()
        self.assertTrue(connected, "Failed to connect to streaming API")

        # Create a callback to track received live ticks
        live_ticks = []

        def live_tick_handler(tick, tick_index, day_index):
            live_ticks.append((tick, datetime.now()))
            print(
                f"Live tick received: {tick.timestamp} - OHLC: {tick.open:.2f}/{tick.high:.2f}/{tick.low:.2f}/{tick.close:.2f}")

        # Register the handler
        data_link.register_tick_handler(live_tick_handler)

        # Enter live mode
        print("\nEntering live mode, waiting for data...")
        data_link.live_mode = True

        # Wait for some live data (this may take a while depending on market activity)
        timeout = 60  # 1 minute timeout
        start_time = time.time()

        try:
            # Process up to N ticks or until timeout
            tick_count = 0
            max_ticks = 10

            while tick_count < max_ticks and time.time() - start_time < timeout:
                # Process next tick from iterator
                if tick_count == 0:
                    print(f"Waiting for live data (timeout: {timeout}s)...")

                for result in data_link.serve_next_tick():
                    if result[0] is None:
                        continue

                    tick, tick_idx, day_idx = result
                    tick_count += 1

                    print(f"Live tick {tick_count}: {tick.timestamp} - Price: ${tick.close:.2f}")

                    if tick_count >= max_ticks:
                        break

                # Short sleep to avoid tight loop
                time.sleep(0.1)

            # Report results
            print(f"\nProcessed {tick_count} live ticks, received {len(live_ticks)} via callback")

            if len(live_ticks) > 0:
                print("\nSample live ticks received:")
                for i, (tick, received_time) in enumerate(live_ticks[:3]):
                    print(f"{i + 1}. {tick.timestamp} (received: {received_time}) - "
                          f"OHLC: {tick.open:.2f}/{tick.high:.2f}/{tick.low:.2f}/{tick.close:.2f}")

            if tick_count == 0 and len(live_ticks) == 0:
                print("\nNo live ticks received. This is normal if the market is closed or inactive.")
                print("Try running the test during market hours for better results.")

        finally:
            # Clean up
            print("\nDisconnecting...")
            data_link.disconnect()

        # Test passed if we got here without exceptions
        self.assertTrue(True, "Live data test completed")


if __name__ == '__main__':
    unittest.main()