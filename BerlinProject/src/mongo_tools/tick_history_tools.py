import time
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Iterable, Iterator
from config.types import TICK_HISTORY_COLLECTION
from environments.tick_data import TickData
from .book_data import BookData, DAILY_TICS
from pymongo.collection import Collection

from models.tick_history import TickHistory
from mongo_tools.mongo import Mongo
from pymongo import InsertOne, collection
import logging

STREAMING_MODE = "stream"
RANDOM_MODE = "random"
BOOK_MODE = "book mode"


@dataclass
class DailyTickHistory:
    data: Dict[str, List[TickData]]


class TickHistoryTools:
    def __init__(self, daily_data: List[BookData]):
        self.books = daily_data
        self.tick_index = 0
        self.episodes = []
        self.episode_index = 0
        self.delay: Optional[int] = None

    def get_stats(self) -> dict:
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
    def get_history_data(cls, ticker: str, date: datetime, time_increments: str = '1') -> Optional[TickHistory]:
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
            t = TickHistory(**retrieved_data)
            t.process_timestamps()
            return t
        return None

    @classmethod
    def get_tools2(cls, selected_data_config: List[Dict]) -> "TickHistoryTools":
        books = []

        for spec in selected_data_config:
            start_date = datetime.strptime(spec['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(spec['end_date'], '%Y-%m-%d')
            time_increments = int(spec['time_increments'])
            book_data = cls.get_the_data_for_tools(spec['ticker'], start_date,
                                                   end_date, time_increments)
            books.append(book_data)

        tools = cls(books)

        return tools

    @classmethod
    def get_the_data_for_tools(cls, ticker: str, start_date: datetime, end_date: datetime, time_increments) -> BookData:
        processed_days = []
        current_date = start_date

        while current_date <= end_date:
            history = cls.get_history_data(ticker, current_date, time_increments)

            if history:
                month_data = history.data
                days = list(month_data.keys())

                for day in days:
                    day_int = int(day)
                    current_day_date = current_date.replace(day=day_int)
                    if start_date <= current_day_date <= end_date:
                        day_ticks = list(month_data[day].values())
                        processed_days.append(day_ticks)

            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)

        bd = BookData(processed_days)
        return bd

    # Function to take the daily data and make it the indexed format...
    # may refactor it somewhere else
    @classmethod
    def index_days(cls, daily_data: List) -> Dict[int, List[TickData]]:
        indexed_day_dict = {}
        current_index = 0

        for ticker_data in daily_data:

            for day_dict in ticker_data:
                indexed_day_dict[current_index] = day_dict['data']
                current_index += 1

        return indexed_day_dict

    @classmethod
    def get_tools(cls, ticker: str, start_date: datetime, end_date: datetime, time_increments):
        processed_days = cls.get_the_data_for_tools(ticker, start_date, end_date, time_increments)
        return cls(daily_data=[processed_days])

    def set_iteration_mode(self, mode: str, episode_count: int = 1):
        self.episodes = []
        all_day_indices = []
        current_idx = 0
        for book_idx, book in enumerate(self.books):
            book_days = len(book.data)
            for _ in range(book_days):
                all_day_indices.append(current_idx)
                current_idx += 1

        if mode == STREAMING_MODE:
            # In streaming mode, just create episodes with sequential days
            self.episodes = self.split_list(all_day_indices, episode_count)

        elif mode == RANDOM_MODE:
            # For random mode, shuffle all days then split
            random.shuffle(all_day_indices)
            self.episodes = self.split_list(all_day_indices, episode_count)

    @staticmethod
    def split_list(lst, n):
        """Split a list into n roughly equal parts"""
        k, m = divmod(len(lst), n)
        return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

    #  day 5
    # book1: [0,1,2] book2: [3,4,5,6,7]
    def get_day_tick_list(self, day_index: int) -> DAILY_TICS | None:
        last_count = 0
        for b in self.books:
            book_count = last_count + b.data_length()
            if day_index < book_count:
                day_spot = day_index - last_count
                return b.data[day_spot]
            last_count = book_count

        return None  # if the index is in error

    def update_episode(self):
        self.episode_index += 1
        if self.episode_index >= len(self.episodes):
            self.episode_index = 0

    def serve_next_tick(self) -> Iterable[TickData]:
        for day_index in self.episodes[self.episode_index]:
            day_tick_list = self.get_day_tick_list(day_index)
            for tick_index, tick in enumerate(day_tick_list):
                yield day_index, tick_index, tick

    def get_history(self) -> Dict[int, List[TickData]]:
        """Returns dictionary mapping day indices to TickData lists for current episode"""
        if not self.episodes or not self.books:
            return {}

        history = {}
        current_episode = self.episodes[self.episode_index]

        for day_index in current_episode:
            # Find which book contains this day
            current_day = 0
            for book_idx, book in enumerate(self.books):
                book_length = len(book.data)
                if current_day <= day_index < current_day + book_length:
                    # Found the correct book, adjust index for this book
                    book_day_index = day_index - current_day
                    history[day_index] = book.data[book_day_index]
                    break
                current_day += book_length

        return history
