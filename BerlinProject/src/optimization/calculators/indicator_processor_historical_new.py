"""
Historical Indicator Processor - Uses same methods as IndicatorProcessor but for all data at once
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
    Historical indicator processor - same logic as IndicatorProcessor but for entire dataset
    """

    def __init__(self, configuration: MonitorConfiguration) -> None:
        self.config: MonitorConfiguration = configuration
        logger.info(f"IndicatorProcessorHistoricalNew initialized")

    def calculate_indicators(self, aggregators: Dict[str, CandleAggregator]) -> Tuple[
        Dict[str, List[float]],  # indicator_history
        Dict[str, List[float]],  # raw_indicator_history
        Dict[str, List[float]]   # bar_score_history
    ]:
        """
        Calculate indicators for entire historical timeline using same methods as IndicatorProcessor
        """
        logger.info("Starting historical indicator calculation...")

        # Get all candle data from aggregators (same as live system)
        all_candle_data = {}
        max_length = 0

        for timeframe, aggregator in aggregators.items():
            history = aggregator.get_history().copy()
            current = aggregator.get_current_candle()
            if current:
                history.append(current)
            all_candle_data[timeframe] = history
            max_length = max(max_length, len(history))
            logger.info(f"{timeframe}: {len(history)} candles")

        # Process each indicator through the historical data
        raw_indicator_history = {}
        indicator_history = {}

        for indicator_def in self.config.indicators:
            timeframe = indicator_def.get_timeframe()
            agg_type = indicator_def.get_aggregator_type()

            if timeframe not in all_candle_data:
                logger.warning(f"Timeframe {timeframe} not found for indicator {indicator_def.name}")
                continue

            candles = all_candle_data[timeframe]

            # Calculate raw indicator values for entire history
            raw_values = self._calculate_indicator_history(candles, indicator_def)
            raw_indicator_history[indicator_def.name] = raw_values

            # Apply lookback scoring to get processed values
            lookback = indicator_def.parameters.get('lookback', 10)
            processed_values = self._apply_lookback_to_history(raw_values, lookback)
            indicator_history[indicator_def.name] = processed_values

            logger.info(f"Processed {indicator_def.name}: {len(processed_values)} values")

        # Calculate bar scores using same method as live system
        bar_score_history = self._calculate_bar_scores_history(indicator_history, max_length)

        logger.info(f"Completed indicator calculation")
        return indicator_history, raw_indicator_history, bar_score_history

    def _calculate_indicator_history(self, tick_history: List[TickData], indicator_def) -> List[float]:
        """
        Calculate single indicator for entire history - same _calculate_single_indicator logic
        """
        try:
            if len(tick_history) < 10:
                return [0.0] * len(tick_history)

            # Same indicator calculation as IndicatorProcessor._calculate_single_indicator
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

            return result.tolist()

        except Exception as e:
            logger.error(f"Error calculating {indicator_def.function}: {e}")
            return [0.0] * len(tick_history)

    def _apply_lookback_to_history(self, raw_values: List[float], lookback: int) -> List[float]:
        """
        Apply time-based lookback scoring to entire history - simulates the live system
        """
        processed_values = []

        # Simulate the trigger history building up over time
        for i in range(len(raw_values)):
            # Get the trigger history up to this point
            trigger_history = raw_values[:i+1]

            # Apply same calculate_time_based_metric as live system
            metric = self.calculate_time_based_metric(np.array(trigger_history), lookback)
            processed_values.append(metric)

        return processed_values

    def calculate_time_based_metric(self, indicator_data: np.ndarray, lookback: int) -> float:
        """
        EXACT SAME METHOD as IndicatorProcessor.calculate_time_based_metric
        """
        if len(indicator_data) == 0:
            return 0.0

        # Always use fixed lookback window, pad with zeros if we don't have enough data
        if len(indicator_data) < lookback:
            padded_data = np.zeros(lookback)
            padded_data[-len(indicator_data):] = indicator_data
            search = padded_data
        else:
            search = indicator_data[-lookback:]

        non_zero_indices = np.nonzero(search)[0]
        if non_zero_indices.size == 0:
            return 0.0

        # Get the most recent trigger
        last_trigger_index = non_zero_indices[-1]
        trigger_value = search[last_trigger_index]

        # Calculate position from the end (0 = most recent position)
        lookback_location = len(search) - last_trigger_index - 1
        lookback_ratio = lookback_location / float(lookback)  # Use fixed lookback, not window size

        metric = (1.0 - lookback_ratio) * np.sign(trigger_value)
        return metric

    def _calculate_bar_scores_history(self, indicator_history: Dict[str, List[float]], max_length: int) -> Dict[str, List[float]]:
        """
        Calculate bar scores for entire history using same _calculate_bar_scores logic
        """
        bar_score_history = {}

        if not hasattr(self.config, 'bars') or not self.config.bars:
            return bar_score_history

        # For each time point, calculate bar scores using same logic as live system
        for bar_name, bar_config in self.config.bars.items():
            bar_scores = []

            # Get timeline length
            timeline_length = max_length
            if indicator_history:
                timeline_length = max(len(values) for values in indicator_history.values())

            # Calculate bar score at each time point
            for i in range(timeline_length):
                # Get indicator values at time i
                indicators_at_time_i = {}
                for indicator_name, values in indicator_history.items():
                    if i < len(values):
                        indicators_at_time_i[indicator_name] = values[i]
                    else:
                        indicators_at_time_i[indicator_name] = 0.0

                # Apply same _calculate_bar_scores logic
                bar_score = self._calculate_bar_scores(indicators_at_time_i, {bar_name: bar_config})
                bar_scores.append(bar_score.get(bar_name, 0.0))

            bar_score_history[bar_name] = bar_scores

        return bar_score_history

    def _calculate_bar_scores(self, indicators: Dict[str, float], bars_config: Dict[str, any]) -> Dict[str, float]:
        """
        EXACT SAME METHOD as IndicatorProcessor._calculate_bar_scores
        """
        bar_scores: Dict[str, float] = {}

        for bar_name, bar_config in bars_config.items():
            # Extract indicator weights from nested structure
            if isinstance(bar_config, dict) and 'indicators' in bar_config:
                weights: Dict[str, float] = bar_config['indicators']
            else:
                weights = bar_config

            weighted_sum: float = 0.0
            total_weight: float = 0.0

            for indicator_name, weight in weights.items():
                if indicator_name in indicators:
                    weighted_sum += indicators[indicator_name] * weight
                    total_weight += weight

            final_score: float = weighted_sum / total_weight if total_weight > 0 else 0.0
            bar_scores[bar_name] = final_score

        return bar_scores