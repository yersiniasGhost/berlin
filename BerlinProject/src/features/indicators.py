import math
from typing import Dict, Callable, Optional, List
from dataclasses import dataclass, field

import talib
import talib as ta
import numpy as np
from environments.tick_data import TickData
from models.indicator_configuration import *



def sma_indicator(tick_data: List[TickData], period: float) -> np.ndarray:
    if len(tick_data) < period:
        return np.array([math.nan] * len(tick_data))
    else:
        closes = np.array([tick.close for tick in tick_data])
        return ta.SMA(closes, timeperiod=period)


def sma_crossover(tick_data: List[TickData], parameters: Dict[str, float]) -> np.ndarray:
    if len(tick_data) < parameters['period']:
        return np.array([math.nan] * len(tick_data))

    sma = sma_indicator(tick_data, parameters['period'])

    closes = np.array([tick.close for tick in tick_data])
    sma_threshold = sma * (1 + parameters['crossover_value'])
    crossovers = closes > sma_threshold

    # Detect the moment of crossover (1 only when previous was 0 and current is 1)
    result = np.zeros(len(tick_data))
    result[1:] = np.logical_and(crossovers[1:], ~crossovers[:-1])

    return result


def macd_calculation(tick_data: List[TickData], fast, slow, signal) -> np.ndarray:
    if len(tick_data) < slow + signal:
        return np.array([math.nan] * len(tick_data))
    else:
        closes = np.array([tick.close for tick in tick_data], dtype=np.float64)
        return ta.MACD(closes, fastperiod=fast, slowperiod=slow, signalperiod=signal)


# refactor threshold, fast, slow, signal to dict

def macd_histogram_crossover(tick_data: List[TickData], parameters: Dict[str, float]) -> np.ndarray:
    if len(tick_data) < parameters['slow'] + parameters['signal']:
        return np.array([math.nan] * len(tick_data))

    macd, signal, histogram = macd_calculation(tick_data, parameters['fast'], parameters['slow'], parameters['signal'])

    # Create a boolean array where True indicates histogram > threshold
    above_threshold = histogram > parameters['histogram_threshold']

    # Detect the moment of crossover (1 only when previous was 0 and current is 1)
    result = np.zeros(len(tick_data))
    result[1:] = np.logical_and(above_threshold[1:], ~above_threshold[:-1])

    return result


def create_bol_bands(tick_data: List[TickData], parameters: Dict[str, float]) -> np.ndarray:
    if len(tick_data) < parameters['period']:
        return np.array(([math.nan] * 3) * len(tick_data))
    else:
        closes = np.array([tick.close for tick in tick_data])
        upper, middle, lower = talib.BBANDS(closes, parameters['period'], parameters['sd'], parameters['sd'])
        return np.array([upper, middle, lower])


# If the prices touches or move belower the lower band then starts to move back towards the middle band
# After hitting the lower band bounce it should be trending between 20-50% of the middle band... use 25%??
# Should be within 1-3 candles of the lower band touch
# Consider increased volume on the bounce?


def bol_bands_lower_band_bounce(tick_data: List[TickData], parameters: Dict[str, float]) -> np.ndarray:
    if len(tick_data) < parameters['period']:
        return np.array([math.nan] * len(tick_data))

    array = create_bol_bands(tick_data, parameters)
    lower = array[2]
    middle = array[1]
    upper = array[0]

    closes = np.array([tick.close for tick in tick_data])

    signals = np.zeros(len(closes))

    candle_bounce_number = int(parameters['candle_bounce_number'])

    for i in range(candle_bounce_number, len(closes)):
        # Check if price touched or went below the lower band in the last 'candle_bounce_number' candles
        if np.any(closes[i-candle_bounce_number:i] <= lower[i-candle_bounce_number:i]):
            # Calculate the current position between lower and middle band
            band_range = middle[i] - lower[i]
            current_position = closes[i] - lower[i]
            bounce_percentage = current_position / band_range

            # Check if the current close is at least 'bounce_trigger' percentage between lower and middle band
            # AND the previous close was below this threshold
            if (bounce_percentage >= parameters['bounce_trigger'] and
                (i == candle_bounce_number or
                 (closes[i-1] - lower[i-1]) / (middle[i-1] - lower[i-1]) < parameters['bounce_trigger'])):
                signals[i] = 1

    return signals

