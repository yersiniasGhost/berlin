
from abc import ABC, abstractmethod
import numpy as np
class State(ABC):
    def __init__(self):
        ...

    @abstractmethod
    def reset(self):
        ...

    @abstractmethod
    def append_state_to_fv(self, fv: np.array) -> np.array:
        ...

    @abstractmethod
    def size(self) -> int:
        ...

    @abstractmethod
    def update_and_calculate_reward(self, trade_action: str):
        ...
    @abstractmethod
    def get_state(self) -> np.array:
        ...