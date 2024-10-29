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
    def test_number_of_days(self):
        """Test that a single trading day returns exactly 390 ticks (6.5 hours of trading)"""
        # Create tools instance for a single day (April 2, 2024)
        tools = TickHistoryTools.get_tools(
            ticker="NVDA",
            start_date=datetime(2024, 10, 22),
            end_date=datetime(2024, 10, 24),
            time_increments=1
        )

        check = tools.daily_data
        # Assert we get exactly 390 ticks (one trading day)
        self.assertEqual(len(check), 3,
                         f"Expected 3 trading days got {len(check)}")


    def test_ticks_in_day(self):
        """Test that we can get tick data across multiple days"""
        tools = TickHistoryTools.get_tools(
            ticker="NVDA",
            start_date=datetime(2024, 6, 20),
            end_date=datetime(2024, 6, 20),
            time_increments=5
        )

        ticks = list(tools.serve_next_tick())
        self.assertTrue(ticks, 78)

    def test_multi_months(self):
        """Test getting NVDA tick data from the database"""
        # Create tools instance
        tools = TickHistoryTools.get_tools(
            ticker="NVDA",
            start_date=datetime(2024, 3, 20),
            end_date=datetime(2024, 7, 12),
            time_increments=1
        )

        check = tools.daily_data

        self.assertEqual(len(check), 60,
                         f"Expected 60 trading days got {len(check)}")

    def test_serve_next(self):
        """Test getting NVDA tick data from the database"""
        # Create tools instance
        tools = TickHistoryTools.get_tools(
            ticker="NVDA",
            start_date=datetime(2024, 9, 20),
            end_date=datetime(2024, 9, 25),
            time_increments=1
        )

