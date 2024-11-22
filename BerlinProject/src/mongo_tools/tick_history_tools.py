import time
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Iterable, Iterator
from config.types import  TICK_HISTORY_COLLECTION
from environments.tick_data import TickData
from .book_data import BookData
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
    def __init__(self, daily_data: List[BookData]):  # Updated type hint
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
            # creates "indexed" which is the index to tickdata dict.

        return cls(books)

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

    @staticmethod
    def split_list(lst, n):
        k, m = divmod(len(lst), n)
        return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

    # def set_iteration_mode(self, mode: str, episode_count: int = 1, randomize: bool = True):
    #     self.episodes = []
    #     if mode == STREAMING_MODE:
    #         # Create tuples for all combinations of (book_idx, value_idx)
    #         indices = []
    #         for book_idx, book in enumerate(self.books):
    #             data_length = book.data_length()
    #             for value_idx in range(data_length):
    #                 indices.append((book_idx, value_idx))
    #         self.episodes.append(indices)
    #
    #     # elif mode == BOOK_MODE:
    #     #     for book_idx, book in enumerate(self.books):
    #     #         indices = []
    #     #         data_length = book.data_length()
    #     #         for value_idx in range(data_length):
    #     #             indices.append((book_idx, value_idx))
    #     #         if randomize:
    #     #             random.shuffle(indices)
    #     #         self.episodes.append(indices)
    #     elif mode == RANDOM_MODE:
    #         indices = []
    #         for book_idx, book in enumerate(self.books):
    #             data_length = book.data_length()
    #             for value_idx in range(data_length):
    #                 indices.append((book_idx, value_idx))
    #         random.shuffle(indices)
    #         self.episodes = self.split_list(indices, episode_count)
    #
    #     self.iteration_mode = mode

    def set_iteration_mode(self, mode: str, episode_count: int = 1):
        self.episodes = []

        # Get all day indices
        day_indices = []
        total_days = 0
        for book in self.books:
            for day_idx in range(len(book.data)):
                day_indices.append(total_days)
                total_days += 1

        if mode == STREAMING_MODE:
            # Split ordered indices into episodes
            self.episodes = self.split_list(day_indices, episode_count)

        elif mode == RANDOM_MODE:
            # Shuffle and split into episodes
            random.shuffle(day_indices)
            self.episodes = self.split_list(day_indices, episode_count)

    # def serve_next_tick(self) -> Iterable[TickData]:
    #     for episode in self.episodes:
    #         for day_index in episode:
    #             # Get all ticks for this day
    #             for tick in self.books[day_index].data:
    #                 yield tick
    #             yield None
    #         yield None
    #     yield None

    def serve_next_tick(self) -> Iterable[Tuple[Optional[TickData], int, int]]:
        current_episode = self.episodes[self.episode_index]

        for day_index in current_episode:
            # Find correct book and day
            current_total = 0
            for book_idx, book in enumerate(self.books):
                if current_total + len(book.data) > day_index:
                    # Found the right book
                    book_day_index = day_index - current_total
                    for tick_index, tick in enumerate(book.data[book_day_index]):
                        yield tick, tick_index, day_index
                    yield None, None, None
                    break
                current_total += len(book.data)

            # def get_history(self, separate_days: bool = False) -> list[list[TickData] | None]:
    #     history = []
    #
    #     # Use first episode's order (whether it's streaming or random)
    #     if self.episodes:
    #         for day_index in self.episodes[0]:
    #             for tick in self.books[day_index].data:
    #                 history.append(tick)
    #             if separate_days:
    #                 history.append(None)
    #
    #     return history

    def get_history(self) -> Dict[int, List[TickData]]:
        history = {}

        if self.episodes:
            episode = self.episodes[self.episode_index]

            for day_index in episode:
                current_day = 0
                current_book = 0

                while current_day <= day_index:
                    if current_book >= len(self.books):
                        break
                    if current_day + len(self.books[current_book].data) > day_index:
                        book_day_index = day_index - current_day
                        # Store using the original day_index as key
                        history[day_index] = self.books[current_book].data[book_day_index]
                        break
                    current_day += len(self.books[current_book].data)
                    current_book += 1

            if self.episode_index < len(self.episodes) - 1:
                self.episode_index += 1

        return history




