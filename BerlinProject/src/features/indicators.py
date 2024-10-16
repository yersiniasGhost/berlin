import math
from typing import Dict, Callable, Optional, List
from dataclasses import dataclass, field
import talib as ta
import numpy as np
from environments.tick_data import TickData
from models.indicator_configuration import *


def sma_indicator(tick_data: List[TickData], period: int) -> np.ndarray:
    if len(tick_data) < period:
        return np.array([math.nan] * len(tick_data))
    else:
        closes = np.array([tick.close for tick in tick_data])
        return ta.SMA(closes, timeperiod=period)


def sma_trigger_crossover(tick_data: List[TickData], period: int, crossover_value: float, lookback: int) -> np.array:
    if len(tick_data) < period:
        return math.nan  # Not enough data to calculate SMA

    sma = sma_indicator(tick_data, period)
    closes = np.array([tick.close for tick in tick_data])

    if math.isnan(sma[-1]):
        return 0

    crossovers = sma > closes * (1+crossover_value)

    return crossovers.astype(int)

    # if not np.any(crossovers):
    #     return 0
    #
    # last_crossover_index = np.where(crossovers)[0][-1]
    # indices_since_crossover = len(sma) - 1 - last_crossover_index
    #
    # if indices_since_crossover == 0:
    #     return 1
    # elif indices_since_crossover < lookback:
    #     x = 1 - (indices_since_crossover / lookback)
    #     return x
    # else:
    #     return 0


