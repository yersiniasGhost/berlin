import unittest

from mongo_tools.tick_history_tools import TickHistoryTools
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Iterable, Iterator
from bson import ObjectId
from config.types import PYMONGO_ID, SAMPLE_COLLECTION, TICK_HISTORY_COLLECTION
from environments.tick_data import TickData

from pymongo.collection import Collection

from models.tick_history import TickHistory
from mongo_tools.mongo import Mongo


class TestTickHistory(unittest.TestCase):
    # Create tools instance
    def test_single_day_tick_count(self):
        """Test that a single trading day returns exactly 390 ticks (6.5 hours of trading)"""
        # Create tools instance for a single day (April 2, 2024)
        tools = TickHistoryTools.get_tools(
            ticker="NVDA",
            start_date=datetime(2024, 4, 22),
            end_date=datetime(2024, 8, 24),
            time_increments=1
        )

        # Collect all ticks for the day
        ticks = list(tools.serve_next_tick())

        # Assert we get exactly 390 ticks (one trading day)
        self.assertEqual(len(ticks), 390,
                         f"Expected 390 ticks for one trading day, got {len(ticks)}")

        # Verify each tick has the required data
        for tick in ticks:
            self.assertIsNotNone(tick.open)
            self.assertIsNotNone(tick.close)
            self.assertIsNotNone(tick.high)
            self.assertIsNotNone(tick.low)

    def test_multi_day_tick_count_5m(self):
        """Test that we can get tick data across multiple days"""
        tools = TickHistoryTools.get_tools(
            ticker="NVDA",
            start_date=datetime(2024, 6, 20),
            end_date=datetime(2024, 6, 20),
            time_increments=5
        )

        ticks = list(tools.serve_next_tick())
        x


    def test_get_tools_nvda(self):
        """Test getting NVDA tick data from the database"""
        # Create tools instance
        tools = TickHistoryTools.get_tools(
            ticker="NVDA",
            start_date=datetime(2024, 6, 20),
            end_date=datetime(2024, 6, 20),
            time_increments=5
        )

        # Basic assertions to verify the tools instance
        self.assertIsNotNone(tools)
        self.assertIsNotNone(tools.history)
        self.assertEqual(tools.history.ticker, "NVDA")
        self.assertEqual(tools.history.time_increments, 5)
        self.assertEqual(tools.start_date.date(), datetime(2024, 6, 20).date())
        self.assertEqual(tools.end_date.date(), datetime(2024, 6, 20).date())

        # Test that we can get some ticks
        ticks = list(tools.serve_next_tick())
        self.assertGreater(len(ticks), 0)

        # Test the first non-None tick has the correct structure
        first_tick = next(tick for tick in ticks if tick is not None)
        self.assertTrue(hasattr(first_tick, 'open'))
        self.assertTrue(hasattr(first_tick, 'high'))
        self.assertTrue(hasattr(first_tick, 'low'))
        self.assertTrue(hasattr(first_tick, 'close'))
        self.assertTrue(hasattr(first_tick, 'day'))
        self.assertEqual(first_tick.day, 20)

