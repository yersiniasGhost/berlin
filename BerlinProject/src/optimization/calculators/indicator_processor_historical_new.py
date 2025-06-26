"""
Simple Historical Indicator Processor - Starting Version
"""

import logging
from typing import Dict, List, Tuple
import numpy as np

from candle_aggregator.candle_aggregator import CandleAggregator
from models.monitor_configuration import MonitorConfiguration
from models.tick_data import TickData
from features.indicators import *
from features.indicators2 import support_level, resistance_level

logger = logging.getLogger('IndicatorProcessorHistoricalNew')


class IndicatorProcessorHistoricalNew:
    """
    Simple historical indicator processor for backtesting
    """

    def __init__(self, configuration: MonitorConfiguration) -> None:
        self.config: MonitorConfiguration = configuration
        logger.info(f"IndicatorProcessorHistoricalNew initialized")

    def calculate_indicators(self, aggregators: Dict[str, CandleAggregator]) -> Tuple[
        Dict[str, List[float]],  # indicator_history
        Dict[str, List[float]],  # raw_indicator_history  
        Dict[str, List[float]]  # bar_score_history
    ]:
        """
        Calculate indicators for entire historical timeline

        Args:
            aggregators: Dict of timeframe -> CandleAggregator with historical data

        Returns:
            Tuple of (indicator_history, raw_indicator_history, bar_score_history)
        """
        logger.info("Starting historical indicator calculation...")

        # Get all candle data from aggregators
        all_candle_data = {}
        for timeframe, aggregator in aggregators.items():
            history = aggregator.get_history().copy()
            current = aggregator.get_current_candle()
            if current:
                history.append(current)
            all_candle_data[timeframe] = history
            logger.info(f"{timeframe}: {len(history)} candles")

        # Calculate indicators for each definition
        raw_indicator_history = {}

        for indicator_def in self.config.indicators:
            timeframe = indicator_def.time_increment

            if timeframe not in all_candle_data:
                logger.warning(f"Timeframe {timeframe} not found for indicator {indicator_def.name}")
                continue

            candles = all_candle_data[timeframe]

            try:
                # Calculate indicator for entire history
                result = self._calculate_single_indicator(candles, indicator_def)

                raw_values = result.tolist()
                raw_indicator_history[indicator_def.name] = raw_values
                logger.info(f"Calculated {indicator_def.name}: {len(raw_values)} values")

            except Exception as e:
                logger.error(f"Error calculating {indicator_def.name}: {e}")

        # For now, just return raw values as both raw and processed
        # TODO: Add lookback scoring and bar calculations
        indicator_history = raw_indicator_history.copy()
        bar_score_history = {}

        logger.info(f"Completed indicator calculation")
        return indicator_history, raw_indicator_history, bar_score_history

    def _calculate_single_indicator(self, tick_history: List[TickData], indicator_def) -> np.ndarray:
        """Calculate a single indicator"""
        try:
            if indicator_def.function == 'sma_crossover':
                result = sma_crossover(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'macd_histogram_crossover':
                result = macd_histogram_crossover(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'bol_bands_lower_band_bounce':
                result = bol_bands_lower_band_bounce(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'support_level':
                result = support_level(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'resistance_level':
                result = resistance_level(tick_history, indicator_def.parameters)
            else:
                logger.warning(f"Unknown indicator function: {indicator_def.function}")
                result = np.array([0.0] * len(tick_history))

            return result

        except Exception as e:
            logger.error(f"Error calculating {indicator_def.function}: {e}")
            return np.array([0.0] * len(tick_history))