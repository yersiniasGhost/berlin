from typing import Dict, Optional
from abc import ABC, abstractmethod
import numpy as np
from environments.tick_data import TickData


class ExternalTool(ABC):
    @abstractmethod
    def indicator_vector(self, combination_id: str, indicators: Dict[str, float],
                         tick: TickData, raw_indicators: Optional[Dict[str, float]] = None,
                         bar_scores: Optional[Dict[str, float]] = None) -> None:
        """
        Handle indicator updates with combination_id for routing

        Args:
            combination_id: Unique identifier for the trading combination
            indicators: Dictionary of indicator results
            tick: Current tick data
            raw_indicators: Raw indicator values (optional)
            bar_scores: Calculated bar scores (optional)
        """
        raise NotImplementedError

    def feature_vector(self, combination_id: str, fv: np.array, tick: TickData) -> None:
        """
        Handle feature vector updates with combination_id for routing

        Args:
            combination_id: Unique identifier for the trading combination
            fv: Feature vector array
            tick: Current tick data
        """
        pass

    # Optional methods that can be implemented by subclasses
    def present_sample(self, combination_id: str, sample: dict, index: int):
        """Handle sample presentation (optional)"""
        pass

    def reset_next_sample(self, combination_id: str):
        """Reset state for next sample (optional)"""
        pass

    def handle_completed_candle(self, combination_id: str, symbol: str, candle: TickData) -> None:
        """Handle completed candle data (optional)"""
        pass