import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Iterable, Iterator
from bson import ObjectId
from config.types import PYMONGO_ID, SAMPLE_COLLECTION, TICK_HISTORY_COLLECTION
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
            #  THIS IS WHERE I WOULD FIX TIMESTAMP FOR EACH DATA IF NEED BE
            return TickHistory(**retrieved_data)
        return None

    # [{0: [TickData]}, {1:[TickData]}, {2:[TickData]}...]
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

    def set_iteration_mode(self, mode: str, episode_count: int = 1, randomize: bool = True):
        self.episodes = []
        if mode == STREAMING_MODE:
            # Create tuples for all combinations of (book_idx, value_idx)
            indices = []
            for book_idx, book in enumerate(self.books):
                data_length = book.data_length()
                for value_idx in range(data_length):
                    indices.append((book_idx, value_idx))
            self.episodes.append(indices)

        elif mode == BOOK_MODE:
            for book_idx, book in enumerate(self.books):
                indices = []
                data_length = book.data_length()
                for value_idx in range(data_length):
                    indices.append((book_idx, value_idx))
                if randomize:
                    random.shuffle(indices)
                self.episodes.append(indices)
        elif mode == RANDOM_MODE:
            indices = []
            for book_idx, book in enumerate(self.books):
                data_length = book.data_length()
                for value_idx in range(data_length):
                    indices.append((book_idx, value_idx))
            random.shuffle(indices)
            self.episodes = self.split_list(indices, episode_count)

        self.iteration_mode = mode



    def serve_next_tick(self) -> Iterable[TickData]:

        for episode in self.episodes:
            for book_index, day_index in episode:
                book = self.books[book_index]
                for (absolute_index, td) in book.get_next_tick(day_index):
                    yield td
            yield None
        yield None

        # elif self.iteration_mode == RANDOM_MODE:
        #     count_of_days =0
        #     for book in self.books:
        #         for day in range(len(book.data)):




    # new serve next tick to handle the indexed dict.
    def serve_next_tick2(self) -> Iterable[TickData]:

        for day_index in sorted(self.books.keys()):
            self.tick_index = 0
            data = self.books[day_index]

            for tick in data:
                yield tick
                self.tick_index += 1

            yield None

    def get_history(self, separate_days: bool = False) -> List[TickData]:
        history = []
        for daily_data in self.books:
            history += daily_data['data']
            if separate_days:
                history += [None]
        return history
