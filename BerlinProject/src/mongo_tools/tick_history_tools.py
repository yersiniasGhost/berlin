from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Iterable, Iterator
from bson import ObjectId
from config.types import PYMONGO_ID, SAMPLE_COLLECTION, TICK_HISTORY_COLLECTION
from environments.tick_data import TickData

from pymongo.collection import Collection

from models.tick_history import TickHistory
from mongo_tools.mongo import Mongo
from pymongo import InsertOne
import logging


class TickHistoryTools:
    def __init__(self, history: Optional[TickHistory] = None, start_date: datetime = None,
                 end_date: datetime = None):
        self.history = history
        self.start_date = start_date
        self.end_date = end_date
        self.current_date = start_date
        self.current_day = None
        self.current_day_times = None
        self.tick_index = 0
        self.current_month_data = None

    def get_stats(self):
        stats = {
            'open': {
                'min': 99.15896984401,
                'max': 105.30305284485804,
                'sd': 1.2180969988222845
            },
            'high': {
                'min': 100.54738434516165,
                'max': 106.15452024531899,
                'sd': 1.1511031022346536
            },
            'low': {
                'min': 98.60951743684032,
                'max': 104.2451994302003,
                'sd': 1.1300040109322043
            },
            'close': {
                'min': 99.87850316060282,
                'max': 104.37585767144925,
                'sd': 1.077354096304813
            }
        }
        return stats

    @classmethod
    def get_collection(cls) -> Collection:
        return Mongo().database[TICK_HISTORY_COLLECTION]

    @classmethod
    def get_history_data(cls, ticker: str, date: datetime, time_increments: int = 1) -> Optional[TickHistory]:
        """Fetch tick history data for given parameters"""
        collection = cls.get_collection()

        query = {
            "ticker": ticker,
            "time_increments": time_increments,
            "year": date.year,
            "month": date.month,
        }

        retrieved_data = collection.find_one(query)
        if retrieved_data:
            return TickHistory(**retrieved_data)
        return None

    @classmethod
    def get_tools(cls, ticker: str, start_date: datetime, end_date: datetime,
                  time_increments) -> 'TickHistoryTools':
        # Get first month's data
        # to my future self.. .ha ha. told you you'd be back
        history = cls.get_history_data(ticker, start_date, time_increments)
        return cls(history, start_date, end_date)

    def serve_next_tick(self) -> Iterable[TickData]:
        """Iterate through tick data chronologically within date range"""
        if not self.history:
            return

        current_date = self.start_date
        while current_date <= self.end_date:
            day = current_date.day

            day_data = self.history.data[str(day)]
            times = sorted([int(t) for t in day_data.keys()])

            for time_str in [str(t) for t in times]:
                tick = day_data[time_str]
                yield tick

            # Move to next day
            current_date += timedelta(days=1)

