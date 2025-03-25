import unittest
import os
import json
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SchwabLiveHistoryTest')

from src.schwab_api.authentication import SchwabClient
from src.environments.tick_data import TickData
from src.data_streamer.schwab_data_link import SchwabDataLink


class TestSchwabLiveHistoryAppend(unittest.TestCase):
    """
    Test SchwabDataLink functionality of loading historical data
    and dynamically appending live ticks
    """

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
        auth_success = cls.client.authenticate(use_local_server=False)
        if not auth_success:
            raise unittest.SkipTest("Authentication failed, skipping tests")

        # Get user preferences
        if not cls.client.user_prefs:
            cls.client._get_streamer_info()

    def test_historical_data_with_live_append(self):
        """
        Test loading historical data and appending live ticks
        """
        # Test configuration
        symbols = ["NVDA"]
        timeframe = "1m"
        days_history = 3  # Load 3 days of historical data
        max_live_ticks = 10  # Limit live ticks to prevent long-running test
        test_timeout = 300  # 5 minutes maximum test runtime

        # Create data link
        data_link = SchwabDataLink(
            user_prefs=self.client.user_prefs,
            access_token=self.client.access_token,
            symbols=symbols,
            timeframe=timeframe,
            days_history=days_history
        )

        # Load historical data
        historical_success = data_link.load_historical_data()
        self.assertTrue(historical_success, "Failed to load historical data")

        # Initial data verification
        for symbol in symbols:
            hist_count = len(data_link.candle_data[symbol])
            print(f"Loaded {hist_count} historical ticks for {symbol}")
            self.assertGreater(hist_count, 0, f"No historical data for {symbol}")

        # Track live ticks
        live_ticks = []

        def live_tick_handler(tick, tick_index, day_index):
            if tick is not None:
                # Append live tick to historical data
                data_link.candle_data[symbols[day_index]].append(tick)
                live_ticks.append(tick)
                print(f"Live Tick {len(live_ticks)}: {tick.timestamp} - ${tick.close:.2f}")

        # Register handler
        data_link.register_tick_handler(live_tick_handler)

        # Connect and start streaming
        connect_success = data_link.connect()
        self.assertTrue(connect_success, "Failed to connect to streaming API")

        # Wait for live ticks or timeout
        start_time = time.time()
        try:
            while (len(live_ticks) < max_live_ticks and
                   time.time() - start_time < test_timeout):
                time.sleep(1)
        except KeyboardInterrupt:
            pass

        # Disconnect
        data_link.disconnect()

        # Verification
        for symbol in symbols:
            total_ticks = len(data_link.candle_data[symbol])
            historical_tick_count = total_ticks - len(live_ticks)

            print(f"\nVerification for {symbol}:")
            print(f"Total ticks: {total_ticks}")
            print(f"Historical ticks: {historical_tick_count}")
            print(f"Live ticks: {len(live_ticks)}")

            # Assert that live ticks were added
            self.assertGreater(len(live_ticks), 0, "No live ticks received")
            self.assertTrue(total_ticks > historical_tick_count, "Live ticks not appended to history")

            # Additional tick validation
            if len(live_ticks) > 0:
                first_live_tick = live_ticks[0]
                last_historical_tick = data_link.candle_data[symbol][historical_tick_count - 1]

                print(f"Last historical tick: {last_historical_tick.timestamp}")
                print(f"First live tick: {first_live_tick.timestamp}")

                # Ensure live ticks are chronologically after historical ticks
                self.assertGreater(
                    first_live_tick.timestamp,
                    last_historical_tick.timestamp,
                    "Live ticks are not chronologically later than historical ticks"
                )


if __name__ == '__main__':
    unittest.main()