from typing import Dict, Optional
from abc import ABC, abstractmethod
import numpy as np
from environments.tick_data import TickData


class ExternalTool(ABC):
    @abstractmethod
    def feature_vector(self, fv: np.array, tick: TickData) -> None:
        raise NotImplemented

    @abstractmethod
    def indicator_vector(self, indicators: Dict[str, float], tick: TickData, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        raise NotImplemented

    # Not required to be implemented
    def present_sample(self, sample: dict, index: int):
        pass

    # Not required to be implemented
    def reset_next_sample(self):
        pass
