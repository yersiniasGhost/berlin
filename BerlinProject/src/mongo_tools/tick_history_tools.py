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

    def serve_next_tick(self) -> Iterable[TickData]:
        """Iterate through tick data chronologically within date range"""
        if not self.history:
            return

        current_date = self.start_date
        while current_date <= self.end_date:
            # Get data for current month if needed
            if (not self.history or
                    self.history.month != current_date.month or
                    self.history.year != current_date.year):
                self.history = self.get_history_data(
                    self.history.ticker,
                    current_date,
                    self.history.time_increments
                )
                if not self.history:
                    current_date = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1)
                    continue

            # Get data for current day
            day_str = str(current_date.day)
            if day_str in self.history.data:
                day_data = self.history.data[day_str]
                times = sorted([int(t) for t in day_data.keys()])

                for time_str in [str(t) for t in times]:
                    tick_data = day_data[time_str]
                    yield TickData(
                        open=tick_data.open,
                        high=tick_data.high,
                        low=tick_data.low,
                        close=tick_data.close
                    )

            # Move to next day
            current_date += timedelta(days=1)


    # def get_history_data(cls,
    #              ticker: str,
    #              start_date: datetime,
    #              end_date: datetime,
    #              time_increments: int = 5) -> Optional[Dict[str, TickData]]:
    #     """Fetch data for a specific date from MongoDB."""
    #     query = {
    #         'ticker': self.ticker,
    #         'month': date.month,
    #         'year': date.year,
    #         'time_increments': self.time_increments
    #     }
    #
    #     result = self.get_collection().find_one(query)
    #     if result:
    #         tick_history = TickHistory(**result)
    #         day_str = str(date.day)
    #         return tick_history.data.get(day_str)
    #     return None
    #
    # def __iter__(self) -> Iterator[Dict]:
    #     """Make the class iterable."""
    #     self.current_date = self.start_date
    #     self.time_index = 0
    #     self.current_day_data = None
    #     self.current_day_times = None
    #     return self
    #
    # def __next__(self) -> Dict:
    #     """Get the next tick of data."""
    #     if self.current_date > self.end_date:
    #         raise StopIteration
    #
    #     # If we don't have current day's data or we've finished the current day
    #     if (not self.current_day_data or
    #             not self.current_day_times or
    #             self.time_index >= len(self.current_day_times)):
    #
    #         # Move to next day with data
    #         while self.current_date <= self.end_date:
    #             self.current_day_data = self.get_history_data(self.current_date)
    #
    #             if self.current_day_data:
    #                 self.current_day_times = sorted(
    #                     [int(t) for t in self.current_day_data.keys()]
    #                 )
    #                 self.time_index = 0
    #                 break
    #
    #             self.current_date += timedelta(days=1)
    #
    #         if self.current_date > self.end_date or not self.current_day_data:
    #             raise StopIteration
    #
    #     # Get current tick and increment index
    #     current_time = str(self.current_day_times[self.time_index])
    #     tick_data = self.current_day_data[current_time]
    #     self.time_index += 1
    #
    #     # If we've reached the end of the day's data
    #     if self.time_index >= len(self.current_day_times):
    #         self.current_date += timedelta(days=1)
    #         self.current_day_data = None
    #         self.current_day_times = None
    #         self.time_index = 0
    #
    #     return {
    #         'date': self.current_date,
    #         'time': int(current_time),
    #         'open': tick_data.open,
    #         'high': tick_data.high,
    #         'low': tick_data.low,
    #         'close': tick_data.close
    #     }
    #
    # @classmethod
    # def get_available_tickers(cls) -> List[str]:
    #     """Get list of all available tickers in the database."""
    #     return cls.get_collection().distinct('ticker')
    #
    # @classmethod
    # def get_date_range_for_ticker(cls, ticker: str) -> tuple:
    #     """Get the full date range available for a specific ticker."""
    #     pipeline = [
    #         {'$match': {'ticker': ticker}},
    #         {'$group': {
    #             '_id': None,
    #             'min_date': {'$min': {
    #                 '$dateFromParts': {
    #                     'year': '$year',
    #                     'month': '$month',
    #                     'day': 1
    #                 }
    #             }},
    #             'max_date': {'$max': {
    #                 '$dateFromParts': {
    #                     'year': '$year',
    #                     'month': '$month',
    #                     'day': 31  # Using 31 as max possible day
    #                 }
    #             }}
    #         }}
    #     ]
    #
    #     result = list(cls.get_collection().aggregate(pipeline))
    #     if result:
    #         return result[0]['min_date'], result[0]['max_date']
    #     return None, None
    #     result = list(collection.aggregate(pipeline))
    #     if result:
    #         return result[0]['min_date'], result[0]['max_date']
    #     return None, None
    #
    #
