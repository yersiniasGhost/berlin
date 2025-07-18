from abc import ABC, abstractmethod
import numpy as np
from models.tick_data import TickData


class State(ABC):
    def __init__(self):
        ...

    @abstractmethod
    def reset(self):
        ...

    @abstractmethod
    def append_state_to_fv(self, fv: np.array, tick: TickData) -> np.array:
        ...

    @abstractmethod
    def size(self) -> int:
        ...

    @abstractmethod
    def update_and_calculate_reward(self, action: str, tick: TickData):
        ...

    @abstractmethod
    def get_state(self) -> np.array:
        ...
