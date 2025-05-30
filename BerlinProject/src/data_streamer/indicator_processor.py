# File: BerlinProject/src/data_streamer/indicator_processor.py
# PRODUCTION VERSION - Clean, no debug code

"""
Indicator processor for calculating technical indicators
"""

import logging
from typing import List, Dict, Tuple
import numpy as np

from models.monitor_configuration import MonitorConfiguration
from environments.tick_data import TickData
from features.indicators import *

logger = logging.getLogger('IndicatorProcessor')


class IndicatorProcessor:
    """
    Indicator processor that calculates indicators from tick history
    """

    def __init__(self, configuration: MonitorConfiguration):
        self.config: MonitorConfiguration = configuration

    def calculate_indicators(self, tick_history: List[TickData]) -> Tuple[
        Dict[str, float], Dict[str, float], Dict[str, float]]:
        """
        Calculate indicators from tick history

        Args:
            tick_history: List of recent TickData objects

        Returns:
            Tuple of (indicators, raw_indicators, bar_scores)
        """
        if not tick_history or len(tick_history) < 20:
            return {}, {}, {}

        try:
            indicators = {}
            raw_indicators = {}

            # Calculate each indicator
            for indicator_def in self.config.indicators:
                try:
                    # Calculate the indicator
                    result = self._calculate_single_indicator(tick_history, indicator_def)

                    if result is not None:
                        # Get the most recent value
                        if isinstance(result, np.ndarray) and len(result) > 0:
                            raw_value = result[-1]
                            raw_indicators[indicator_def.name] = float(raw_value)

                            # Apply time-based metric
                            lookback = indicator_def.parameters.get('lookback', 10)
                            metric = self._calculate_time_based_metric(result, lookback)
                            indicators[indicator_def.name] = float(metric)
                        else:
                            indicators[indicator_def.name] = 0.0
                            raw_indicators[indicator_def.name] = 0.0

                except Exception as e:
                    logger.error(f"Error calculating indicator {indicator_def.name}: {e}")
                    indicators[indicator_def.name] = 0.0
                    raw_indicators[indicator_def.name] = 0.0

            # Calculate bar scores
            bar_scores = self._calculate_bar_scores(indicators)

            return indicators, raw_indicators, bar_scores

        except Exception as e:
            logger.error(f"Error in calculate_indicators: {e}")
            return {}, {}, {}

    def _calculate_single_indicator(self, tick_history: List[TickData], indicator_def) -> np.ndarray:
        """Calculate a single indicator"""
        try:
            if indicator_def.function == 'sma_crossover':
                return sma_crossover(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'macd_histogram_crossover':
                return macd_histogram_crossover(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'bol_bands_lower_band_bounce':
                return bol_bands_lower_band_bounce(tick_history, indicator_def.parameters)
            else:
                logger.warning(f"Unknown indicator function: {indicator_def.function}")
                return np.array([0.0])

        except Exception as e:
            logger.error(f"Error calculating {indicator_def.function}: {e}")
            return np.array([0.0])

    def _calculate_time_based_metric(self, indicator_data: np.ndarray, lookback: int) -> float:
        """Calculate time-based metric for an indicator"""
        try:
            if len(indicator_data) == 0:
                return 0.0

            search = indicator_data[-lookback:] if len(indicator_data) >= lookback else indicator_data
            non_zero_indices = np.nonzero(search)[0]

            if non_zero_indices.size == 0:
                return 0.0

            c = search[non_zero_indices[-1]]
            lookback_location = len(search) - non_zero_indices[-1] - 1
            lookback_ratio = lookback_location / float(lookback)
            metric = (1.0 - lookback_ratio) * np.sign(c)

            return float(metric)

        except Exception as e:
            logger.error(f"Error calculating time-based metric: {e}")
            return 0.0

    def _calculate_bar_scores(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """Calculate bar scores from indicators"""
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