from dataclasses import dataclass
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


@dataclass
class DayData:
    date: datetime
    ticks: List[TickData]


class TickHistoryTools:
    def __init__(self, history: Optional[TickHistory] = None, start_date: datetime = None, end_date: datetime = None):
        self.history = history
        self.start_date = start_date
        self.end_date = end_date
        self.current_date = start_date
        self.current_day = None
        self.current_day_times = None
        self.tick_index = 0
        self.current_month_data = None

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
                  time_increments: int = 1) -> 'TickHistoryTools':
        # Get first month's data
        history = cls.get_history_data(ticker, start_date, time_increments)
        return cls(history, start_date, end_date)

    def serve_next_day(self) -> Optional[DayData]:
        """Iterate through data one day at a time"""
        if not self.history:
            return None

        while self.current_date <= self.end_date:
            # Get data for current month if needed
            if (not self.history or
                    self.history.month != self.current_date.month or
                    self.history.year != self.current_date.year):
                self.history = self.get_history_data(
                    self.history.ticker,
                    self.current_date,
                    self.history.time_increments
                )
                if not self.history:
                    self.current_date = (self.current_date.replace(day=1) + timedelta(days=32)).replace(day=1)
                    continue

            # Get data for current day
            day_str = str(self.current_date.day)
            if day_str in self.history.data:
                day_data = self.history.data[day_str]
                times = sorted([int(t) for t in day_data.keys()])

                # Collect all ticks for the day
                day_ticks = []
                for time_str in [str(t) for t in times]:
                    tick_data = day_data[time_str]
                    day_ticks.append(TickData(
                        open=tick_data.open,
                        high=tick_data.high,
                        low=tick_data.low,
                        close=tick_data.close
                    ))

                # Store current date before incrementing
                current_date = self.current_date
                # Move to next day
                self.current_date += timedelta(days=1)

                # Return the day's data
                return DayData(date=current_date, ticks=day_ticks)

            # Move to next day if no data found
            self.current_date += timedelta(days=1)

        return None

    def serve_next_tick(self) -> Iterable[TickData]:
        """Original method that serves all ticks sequentially"""
        while True:
            day_data = self.serve_next_day()
            if not day_data:
                break
            for tick in day_data.ticks:
                yield tick
