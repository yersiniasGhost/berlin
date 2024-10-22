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
            ticker="AAPL",
            start_date=datetime(2024, 4, 2),
            end_date=datetime(2024, 4, 2),
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
        """Test that a single trading day returns exactly 390 ticks (6.5 hours of trading)"""
        # Create tools instance for a single day (April 2, 2024)
        tools = TickHistoryTools.get_tools(
            ticker="AMD",
            start_date=datetime(2024, 10, 2),
            end_date=datetime(2024, 10, 2),
            time_increments=5
        )

        # Collect all ticks for the day
        ticks = list(tools.serve_next_tick())

        # Assert we get exactly 390 ticks (one trading day)
        self.assertEqual(len(ticks), 78,
                         f"Expected 78*4 ticks for one trading day, got {len(ticks)}")

        # Verify each tick has the required data
        for tick in ticks:
            self.assertIsNotNone(tick.open)
            self.assertIsNotNone(tick.close)
            self.assertIsNotNone(tick.high)
            self.assertIsNotNone(tick.low)