from abc import ABC, abstractmethod
import numpy as np

from tick_data import TickData


class ExternalTool(ABC):
    @abstractmethod
    def feature_vector(self, fv: np.array, tick: TickData) -> None:
        raise NotImplemented
