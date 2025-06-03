# File: BerlinProject/src/data_streamer/indicator_processor.py
# PRODUCTION VERSION - Clean, no debug code

"""
Indicator processor for calculating technical indicators
"""

import logging
from typing import List, Dict, Tuple
import numpy as np

from features.indicators2 import support_level, resistance_level
from models.monitor_configuration import MonitorConfiguration
from environments.tick_data import TickData
from features.indicators import *

logger = logging.getLogger('IndicatorProcessor')


class IndicatorProcessor:
    def __init__(self, configuration: MonitorConfiguration):
        self.config: MonitorConfiguration = configuration

    def calculate_indicators(self, tick_history: List[TickData]) -> Tuple[
        Dict[str, float], Dict[str, float], Dict[str, float]]:
        """
        Calculate indicators from PURE timeframe-specific tick history
        No more filtering needed - data is already pure!
        """
        if not tick_history or len(tick_history) < 20:
            return {}, {}, {}

        try:
            indicators = {}
            raw_indicators = {}

            for indicator_def in self.config.indicators:
                try:
                    # Use the pure tick history directly (no filtering!)
                    result = self._calculate_single_indicator(tick_history, indicator_def)

                    if result is not None and isinstance(result, np.ndarray) and len(result) > 0:
                        raw_value = result[-1]
                        raw_indicators[indicator_def.name] = float(raw_value)

                        # Apply timeframe-aware decay
                        timeframe = getattr(indicator_def, 'time_increment', '1m')
                        lookback = indicator_def.parameters.get('lookback', 10)

                        metric = self._calculate_timeframe_decay(
                            result, lookback, timeframe
                        )
                        indicators[indicator_def.name] = float(metric)
                    else:
                        indicators[indicator_def.name] = 0.0
                        raw_indicators[indicator_def.name] = 0.0

                except Exception as e:
                    logger.error(f"Error calculating indicator {indicator_def.name}: {e}")
                    indicators[indicator_def.name] = 0.0
                    raw_indicators[indicator_def.name] = 0.0

            bar_scores = self._calculate_bar_scores(indicators)
            return indicators, raw_indicators, bar_scores

        except Exception as e:
            logger.error(f"Error in calculate_indicators: {e}")
            return {}, {}, {}

    def _calculate_timeframe_decay(self, indicator_data: np.ndarray, lookback: int, timeframe: str) -> float:
        """
        Calculate timeframe decay that decreases by 0.1 per time period
        Signal dies after exactly 10 periods regardless of timeframe

        Expected behavior:
        - Signal triggers → value = 1.0
        - 1 period later → value = 0.9
        - 2 periods later → value = 0.8
        - 3 periods later → value = 0.7
        - ...
        - 10 periods later → value = 0.0 (dead)
        """
        try:
            if len(indicator_data) == 0:
                return 0.0

            # Search in the entire array for signals
            non_zero_indices = np.nonzero(indicator_data)[0]

            if non_zero_indices.size == 0:
                return 0.0

            # Get the most recent signal from the entire array
            most_recent_signal_index = non_zero_indices[-1]
            signal_value = indicator_data[most_recent_signal_index]

            # Calculate how many periods have passed since the signal
            periods_since_signal = len(indicator_data) - most_recent_signal_index - 1

            # Signal dies after exactly 10 periods for ALL timeframes
            if periods_since_signal >= 10:
                return 0.0

            # Linear decay: decrease by 0.1 per period
            decay_amount = periods_since_signal * 0.1
            current_value = 1.0 - decay_amount

            # Don't go below 0
            current_value = max(0.0, current_value)

            # Apply sign of original signal
            result = current_value * np.sign(signal_value)

            return float(result)

        except Exception as e:
            logger.error(f"Error calculating timeframe decay: {e}")
            return 0.0

    def _calculate_single_indicator(self, tick_history: List[TickData], indicator_def) -> np.ndarray:
        """Calculate indicator using pure timeframe data"""
        try:
            if indicator_def.function == 'sma_crossover':
                return sma_crossover(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'macd_histogram_crossover':
                return macd_histogram_crossover(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'bol_bands_lower_band_bounce':
                return bol_bands_lower_band_bounce(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'support_level':
                return support_level(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'resistance_level':
                return resistance_level(tick_history, indicator_def.parameters)
            else:
                logger.warning(f"Unknown indicator function: {indicator_def.function}")
                return np.array([0.0])
        except Exception as e:
            logger.error(f"Error calculating {indicator_def.function}: {e}")
            return np.array([0.0])

    def _calculate_bar_scores(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """Calculate weighted bar scores"""
        bar_scores = {}
        if hasattr(self.config, 'bars') and self.config.bars:
            for bar_name, bar_weights in self.config.bars.items():
                weighted_sum = 0.0
                total_weight = 0.0
                for indicator_name, weight in bar_weights.items():
                    if indicator_name in indicators:
                        weighted_sum += indicators[indicator_name] * weight
                        total_weight += weight
                bar_scores[bar_name] = weighted_sum / total_weight if total_weight > 0 else 0.0
        return bar_scores