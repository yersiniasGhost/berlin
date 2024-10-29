import unittest
from datetime import datetime, timedelta
from pymongo import MongoClient
from cronjob.data_fetch import DataFetch
import pandas as pd
import time


class TestDataFetch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Setup MongoDB connection
        client = MongoClient('mongodb://localhost:27017/')
        db = client['MTA_devel']
        cls.collection = db['tick_history']
        cls.loader = DataFetch(cls.collection)

        # Test data
        cls.test_ticker = "AAPL"
        cls.test_interval = 1

    def test_seconds_from_midnight(self):
        """Test conversion of time string to seconds"""
        test_cases = [
            ("09:30:00", 34200),  # Market open
            ("16:00:00", 57600),  # Market close
            ("12:00:00", 43200),  # Noon
        ]

        for time_str, expected in test_cases:
            result = self.loader.seconds_from_midnight(time_str)
            self.assertEqual(result, expected, f"Failed for time {time_str}")

    def test_process_interval_data(self):
        """Test processing of interval data"""
        # Create sample DataFrame
        index = pd.date_range('2024-04-22 09:30:00', '2024-04-22 09:35:00', freq='1min')
        data = {
            'Open': [100.0] * len(index),
            'High': [101.0] * len(index),
            'Low': [99.0] * len(index),
            'Close': [100.5] * len(index)
        }
        df = pd.DataFrame(data, index=index)

        # Process the data
        result = self.loader.process_interval_data(df, 22)

        # Verify the results
        self.assertIsInstance(result, dict)
        self.assertTrue(all(str(second) in result for second in range(34200, 34500, 60)))

        # Check data structure
        first_tick = result['34200']
        self.assertEqual(first_tick['open'], 100.0)
        self.assertEqual(first_tick['high'], 101.0)
        self.assertEqual(first_tick['low'], 99.0)
        self.assertEqual(first_tick['close'], 100.5)

    # def test_update_ticker_data(self):
    #     """Test updating ticker data in MongoDB"""
    #     # Get current date info
    #     now = datetime.now()
    #
    #     # Update data for test ticker
    #     self.loader.update_ticker_data(self.test_ticker, self.test_interval)
    #
    #     # Verify document exists in MongoDB
    #     doc = self.collection.find_one({
    #         'ticker': self.test_ticker,
    #         'year': now.year,
    #         'month': now.month,
    #         'time_increments': self.test_interval
    #     })
    #
    #     self.assertIsNotNone(doc)
    #     self.assertIn('data', doc)
    #     self.assertIsInstance(doc['data'], dict)
    #
    #     # Check data structure for a day
    #     if doc['data']:  # If we have data for any day
    #         any_day = next(iter(doc['data'].values()))
    #         any_time = next(iter(any_day.values()))
    #
    #         self.assertIn('open', any_time)
    #         self.assertIn('high', any_time)
    #         self.assertIn('low', any_time)
    #         self.assertIn('close', any_time)

    # def test_market_hours_filtering(self):
    #     """Test that only market hours data is included"""
    #     # Create sample DataFrame with pre-market and post-market data
    #     index = pd.date_range('2024-04-22 08:00:00', '2024-04-22 17:00:00', freq='1min')
    #     data = {
    #         'Open': [100.0] * len(index),
    #         'High': [101.0] * len(index),
    #         'Low': [99.0] * len(index),
    #         'Close': [100.5] * len(index)
    #     }
    #     df = pd.DataFrame(data, index=index)
    #
    #     # Process the data
    #     result = self.loader.process_interval_data(df, 22)
    #
    #     # Verify only market hours data is included
    #     times = [int(t) for t in result.keys()]
    #     self.assertTrue(all(34200 <= t <= 57600 for t in times))

    # def test_update_existing_document(self):
    #     """Test updating an existing document"""
    #     now = datetime.now()
    #
    #     # Make two consecutive updates
    #     self.loader.update_ticker_data(self.test_ticker, self.test_interval)
    #     first_doc = self.collection.find_one({
    #         'ticker': self.test_ticker,
    #         'year': now.year,
    #         'month': now.month,
    #         'time_increments': self.test_interval
    #     })
    #
    #     # Wait a bit and update again
    #     time.sleep(2)
    #     self.loader.update_ticker_data(self.test_ticker, self.test_interval)
    #     second_doc = self.collection.find_one({
    #         'ticker': self.test_ticker,
    #         'year': now.year,
    #         'month': now.month,
    #         'time_increments': self.test_interval
    #     })
    #
    #     # Verify it's the same document
    #     self.assertEqual(first_doc['_id'], second_doc['_id'])
#
#
# if __name__ == '__main__':
#     unittest.main()