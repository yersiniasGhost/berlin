from dataclasses import dataclass
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Iterable, Iterator
from bson import ObjectId
from config.types import PYMONGO_ID, SAMPLE_COLLECTION, TICK_HISTORY_COLLECTION
from environments.tick_data import TickData

from pymongo.collection import Collection

from models.tick_history import TickHistory
from mongo_tools.mongo import Mongo
from pymongo import InsertOne, collection
import logging


@dataclass
class DailyTickHistory:
    data: Dict[str, List[TickData]]


class TickHistoryTools:
    def __init__(self, daily_data: List[Dict[str, List[TickData]]]):  # Updated type hint
        self.daily_data = daily_data
        self.tick_index = 0
        self.time_tick = time.time()
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
            #  THIS IS WHERE I WOULD FIX TIMESTAMP FOR EACH DATA IF NEED BE
            return TickHistory(**retrieved_data)
        return None


    @classmethod
    def get_tools(cls, ticker: str, start_date: datetime, end_date: datetime, time_increments):
        processed_days = []
        current_date = start_date

        while current_date <= end_date:
            history = cls.get_history_data(ticker, current_date, time_increments)
            history.process_timestamps()
            if history:
                month_data = history.data
                days = list(month_data.keys())

                for day in days:
                    day_int = int(day)
                    current_day_date = current_date.replace(day=day_int)
                    if start_date <= current_day_date <= end_date:
                        day_ticks = list(month_data[day].values())
                        daily_history = {'data': day_ticks}
                        processed_days.append(daily_history)

            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)

        return cls(daily_data=processed_days)

    def serve_next_tick(self) -> Iterable[TickData]:
        for daily_data in self.daily_data:
            self.tick_index = 0
            data = daily_data['data']  # Changed to dictionary access
            for tick in data:
                print("yield", tick)
                yield tick

                self.tick_index += 1
                if self.delay:
                    time.sleep(self.delay)
                    # now = time.time()
                    # remaining_time = self.delay - (now - self.time_tick)
                    # print(remaining_time, self.time_tick, now)
                    # self.time_tick = now
                    # if remaining_time > 0:
                    #     time.sleep(remaining_time+1)

            yield None

    def get_history(self, separate_days: bool = False) -> List[TickData]:
        history = []
        for daily_data in self.daily_data:
            history += daily_data['data']
            if separate_days:
                history += [None]
        return history
