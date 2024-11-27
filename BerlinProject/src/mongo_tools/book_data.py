import numpy as np
from dataclasses import dataclass
from typing import List, Tuple
from environments.tick_data import TickData

DAILY_TICS = List[TickData]
@dataclass
class BookData:
    data: List[DAILY_TICS]

    def __post_init__(self):
        self.lengths = list(np.cumsum([len(d) for d in self.data]))
        self.index = 0

    def get_next_tick(self, day: int) -> Tuple[int, TickData]:
        last_index = self.lengths[day - 1] if day > 0 else 0
        for tick_index, tick in enumerate(self.data[day]):
            absolute_index = last_index + tick_index
            yield absolute_index, tick
        yield None, None

    def get_tick(self, day: int, tick_index: int) -> Tuple[int, TickData]:
        last_index = self.lengths[day - 1] if day > 0 else 0
        absolute_index = last_index + tick_index
        td = self.data[day][tick_index]
        return absolute_index, td

    def data_length(self) -> int:
        return len(self.data)