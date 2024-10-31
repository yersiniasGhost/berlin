from typing import Dict, Callable, Optional, List
from dataclasses import dataclass, field
import talib as ta
import numpy as np
from environments.tick_data import TickData



def initialize_pattern_matchers(selected_patterns: List[str]):
    available_patterns = ta.get_function_groups()['Pattern Recognition']
    pattern_matchers = {}
    for pattern in selected_patterns:
        if pattern not in available_patterns:
            continue
        pattern_matchers[pattern] = lambda open, high, low, close: getattr(ta, pattern)(open, high, low, close)
    return pattern_matchers


def get_ta_candlestick_patterns() -> List[str]:
    return ta.get_function_groups()['Pattern Recognition']


@dataclass
class CandlePatterns:
    selected_patterns: List[str] = field(default_factory=get_ta_candlestick_patterns)
    pattern_matchers: Optional[Dict[str, Callable]] = field(init=False)

    def __post_init__(self):
        self.pattern_matchers = initialize_pattern_matchers(self.selected_patterns)

    def find_patterns(self, opens: np.array, highs: np.array, lows: np.array, closes: np.array) -> Dict[str, np.ndarray]:
        results = {n: f(opens, highs, lows, closes) for n, f in self.pattern_matchers.items()}
        return results

    def process_candlestick_data(self, opens: List[float], highs: List[float], lows: List[float],
                                 closes: List[float]) -> Dict[str, np.ndarray]:
        opens_np = np.array(opens)
        highs_np = np.array(highs)
        lows_np = np.array(lows)
        closes_np = np.array(closes)
        return self.find_patterns(opens_np, highs_np, lows_np, closes_np)

    def process_tick_data(self, tick_data: List[TickData], look_back: int) -> Dict[str, np.array]:
        opens, highs, lows, closes = [], [], [], []
        for history_tick in tick_data[-look_back:]:
            opens.append(history_tick.open)
            highs.append(history_tick.high)
            lows.append(history_tick.low)
            closes.append(history_tick.close)

        # Add in the last tick
        # opens.append(tick.open)
        # highs.append(tick.high)
        # lows.append(tick.low)
        # closes.append(tick.close)

        return self.process_candlestick_data(opens, highs, lows, closes)
