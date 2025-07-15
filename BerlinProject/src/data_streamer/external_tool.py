from typing import Dict, Optional, Any
from abc import ABC, abstractmethod
import numpy as np
from models.tick_data import TickData


class ExternalTool(ABC):
    @abstractmethod
    def feature_vector(self, fv: np.array, tick: TickData) -> None:
        raise NotImplemented

    @abstractmethod
    def indicator_vector(self, indicators: Dict[str, float], tick: TickData, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None,
                         bar_scores: Optional[Dict[str, float]] = None,
                         combination_id: Optional[str] = None) -> None:
        raise NotImplemented

    # Not required to be implemented
    def present_sample(self, sample: dict, index: int):
        pass

    # Not required to be implemented
    def reset_next_sample(self):
        pass

    def handle_completed_candle(self, symbol: str, candle: TickData) -> None:
        pass

    def process_tick(self, card_id: str, symbol: str, tick_data: TickData,
                     indicators: Dict[str, float], raw_indicators: Dict[str, float],
                     bar_scores: Dict[str, float], portfolio_metrics: Optional[Dict[str, Any]] = None) -> None:
        pass
