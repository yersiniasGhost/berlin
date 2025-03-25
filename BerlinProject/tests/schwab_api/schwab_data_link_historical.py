import unittest
import os
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SchwabDataLinkTest')

from src.schwab_api.authentication import SchwabClient
from src.environments.tick_data import TickData
from src.data_streamer.schwab_data_link import SchwabDataLink
from src.data_streamer.data_streamer import DataStreamer


class TestSchwabHistoricalData(unittest.TestCase):
    """Basic test for SchwabDataLink historical data functionality."""

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

    def test_data_loading_with_config(self):
        """Test loading historical data with JSON config."""
        # Create JSON config
        data_config = {
            "type": "CharlesSchwab",
            "user_prefs": self.client.user_prefs,
            "access_token": self.client.access_token,
            "symbols": ["NVDA", "PLTR"],
            "timeframe": "5m",
            "days_history": 3
        }

        # Create data link directly with config values
        data_link = SchwabDataLink(
            user_prefs=data_config["user_prefs"],
            access_token=data_config["access_token"],
            symbols=data_config["symbols"],
            timeframe=data_config["timeframe"],
            days_history=data_config["days_history"]
        )

        # Load historical data
        print("\nLoading historical data...")
        success = data_link.load_historical_data()
        self.assertTrue(success, "Failed to load historical data")

        # Print summary
        print("\nHistorical Data Summary:")
        for symbol in data_link.symbols:
            count = len(data_link.candle_data[symbol])
            print(f"{symbol}: {count} candles")

            if count > 0:
                first = data_link.candle_data[symbol][0]
                last = data_link.candle_data[symbol][-1]

                print(
                    f"First candle: {first.timestamp} - OHLC: {first.open:.2f}/{first.high:.2f}/{first.low:.2f}/{first.close:.2f}")
                print(
                    f"Last candle: {last.timestamp} - OHLC: {last.open:.2f}/{last.high:.2f}/{last.low:.2f}/{last.close:.2f}")

        # Test history for compatibility with indicator processors
        history = data_link.get_history()
        print(f"\nHistory format: {len(history)} day(s)")

        # Test getting ticks through the iterator
        print("\nTesting data iteration:")
        count = 0
        for result in data_link.serve_next_tick():
            if result[0] is None:
                print("End of data or day boundary")
                continue

            tick, idx, day = result
            count += 1

            if count <= 3 or count % 50 == 0:
                print(f"Tick {count}: Day {day}, Time {tick.timestamp}, Price ${tick.close:.2f}")

            if count >= 100:
                break

        print(f"Processed {count} ticks")
        self.assertGreater(count, 0, "No ticks were processed")


if __name__ == '__main__':
    unittest.main()