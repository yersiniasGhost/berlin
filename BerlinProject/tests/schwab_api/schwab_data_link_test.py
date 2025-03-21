import unittest
import json
import os
from schwab_api.authentication import SchwabClient
from environments.tick_data import TickData
from data_streamer.schwab_data_link import SchwabDataLink


class TestSchwabDataLink(unittest.TestCase):
    """
    Test the SchwabDataLink class with real Schwab API data.
    """

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests"""
        print("Loading Schwab API credentials...")

        # Load credentials from JSON file
        auth_file_path = os.path.join(os.path.dirname(__file__),
                                      '../../src/schwab_api/authentication_info.json')

        # Check if file exists
        if not os.path.exists(auth_file_path):
            raise unittest.SkipTest(f"Authentication file not found: {auth_file_path}")

        try:
            with open(auth_file_path, 'r') as auth_file:
                auth_info = json.load(auth_file)

            # Extract credentials
            cls.app_key = auth_info.get('api_key', '')
            cls.app_secret = auth_info.get('api_secret', '')
            cls.redirect_uri = auth_info.get('redirect_uri', 'https://127.0.0.1')

            print(f"Loaded authentication info for API key: {cls.app_key}")

            # Create Schwab client with token path
            token_path = "schwab_test_tokens.json"
            cls.client = SchwabClient(
                app_key=cls.app_key,
                app_secret=cls.app_secret,
                redirect_uri=cls.redirect_uri,
                token_path=token_path
            )

            # Check if we already have tokens
            if not cls.client.access_token:
                print("Authenticating with Schwab API...")
                print("When the browser opens, log in to Schwab, then copy the redirect URL")
                print("and paste it below when prompted...")

                # Call the authenticate method with use_local_server=False to force manual input
                auth_success = cls.client.authenticate(use_local_server=False)

                if not auth_success:
                    raise unittest.SkipTest("Authentication failed, skipping tests")

            # Common test symbols
            cls.test_symbols = ["AAPL", "MSFT", "NVDA"]

            # Get user preferences for streaming
            if not cls.client.user_prefs:
                cls.client._get_streamer_info()

            # Check if we have valid user preferences
            if not cls.client.user_prefs:
                raise unittest.SkipTest("Failed to get streaming info")

        except Exception as e:
            raise unittest.SkipTest(f"Failed to set up tests: {e}")

    def setUp(self):
        """Set up before each test"""
        # Create a data link for each test
        self.data_link = SchwabDataLink(
            user_prefs=self.client.user_prefs,
            access_token=self.client.access_token,
            symbols=self.test_symbols,
            timeframe="1m",
            days_history=1
        )

    def test_inheritance(self):
        """Test that SchwabDataLink properly inherits from DataLink"""
        from data_streamer.data_link import DataLink
        self.assertIsInstance(self.data_link, DataLink)

    def test_historical_data_loading(self):
        """Test loading historical data"""
        # Load historical data
        success = self.data_link.load_historical_data()
        self.assertTrue(success, "Historical data loading failed")

        # Check that data was loaded for each symbol
        for symbol in self.test_symbols:
            self.assertIn(symbol, self.data_link.candle_data)
            self.assertGreater(len(self.data_link.candle_data[symbol]), 0,
                               f"No historical data loaded for {symbol}")

            # Check first tick has the right structure
            first_tick = self.data_link.candle_data[symbol][0]
            self.assertIsInstance(first_tick, TickData)
            self.assertIsNotNone(first_tick.open)
            self.assertIsNotNone(first_tick.high)
            self.assertIsNotNone(first_tick.low)
            self.assertIsNotNone(first_tick.close)

    def test_get_stats(self):
        """Test getting statistics for normalization"""
        # Load data first
        self.data_link.load_historical_data()

        # Get stats
        stats = self.data_link.get_stats()

        # Check stats structure
        self.assertIn('open', stats)
        self.assertIn('high', stats)
        self.assertIn('low', stats)
        self.assertIn('close', stats)

        for field in ['open', 'high', 'low', 'close']:
            self.assertIn('min', stats[field])
            self.assertIn('max', stats[field])
            self.assertIn('sd', stats[field])

            # Min should be less than max
            self.assertLess(stats[field]['min'], stats[field]['max'])

    def test_get_history(self):
        """Test get_history method for compatibility with indicators"""
        # Load data first
        self.data_link.load_historical_data()

        # Get history
        history = self.data_link.get_history()

        # Check history structure
        self.assertIsInstance(history, dict)

        # Should have an entry for each symbol
        self.assertEqual(len(history), len(self.test_symbols))

        # Each entry should be a list of TickData
        for i in range(len(self.test_symbols)):
            self.assertIn(i, history)
            self.assertIsInstance(history[i], list)

            # Should have some data
            self.assertGreater(len(history[i]), 0)

            # Each item should be TickData
            self.assertIsInstance(history[i][0], TickData)


if __name__ == '__main__':
    unittest.main()