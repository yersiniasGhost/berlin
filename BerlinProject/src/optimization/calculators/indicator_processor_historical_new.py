"""
Complete Historical Indicator Processor - Batch processing for genetic algorithms
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
    Optimized historical indicator processor - calculates all indicators for entire timeline at once
    """

    def __init__(self, configuration: MonitorConfiguration) -> None:
        self.config: MonitorConfiguration = configuration
        logger.info(f"IndicatorProcessorHistoricalNew initialized with {len(self.config.indicators)} indicators")

    def calculate_indicators(self, aggregators: Dict[str, CandleAggregator]) -> Tuple[
        Dict[str, List[float]],  # indicator_history
        Dict[str, List[float]],  # raw_indicator_history
        Dict[str, List[float]]   # bar_score_history
    ]:
        """
        Calculate indicators for entire historical timeline using batch operations

        Returns:
            - indicator_history: {indicator_name: [value_at_tick_0, value_at_tick_1, ...]}
            - raw_indicator_history: {indicator_name: [raw_value_at_tick_0, raw_value_at_tick_1, ...]}
            - bar_score_history: {bar_name: [score_at_tick_0, score_at_tick_1, ...]}
        """
        logger.info("Starting batch historical indicator calculation...")

        # Extract all candle data from aggregators
        all_candle_data = self._extract_all_candle_data(aggregators)
        if not all_candle_data:
            return {}, {}, {}

        max_length = max(len(candles) for candles in all_candle_data.values())
        logger.info(f"Processing timeline of {max_length} data points")

        # Process each indicator
        raw_indicator_history = {}
        indicator_history = {}

        for indicator_def in self.config.indicators:
            # Get the correct aggregator key for this indicator
            aggregator_key = self._get_aggregator_key(indicator_def, aggregators)

            if aggregator_key not in all_candle_data:
                logger.warning(f"No data found for indicator {indicator_def.name} (key: {aggregator_key})")
                continue

            candles = all_candle_data[aggregator_key]

            # Calculate raw indicator values for entire history
            raw_values = self._calculate_indicator_batch(candles, indicator_def)
            raw_indicator_history[indicator_def.name] = raw_values

            # Apply lookback scoring using vectorized operations
            lookback = indicator_def.parameters.get('lookback', 10)
            processed_values = self._apply_lookback_vectorized(raw_values, lookback)
            indicator_history[indicator_def.name] = processed_values

            logger.debug(f"Processed {indicator_def.name}: {len(processed_values)} values")

        # Calculate bar scores for entire timeline
        bar_score_history = self._calculate_bar_scores_batch(indicator_history, max_length)

        logger.info(f"Completed batch indicator calculation")
        return indicator_history, raw_indicator_history, bar_score_history

    def _extract_all_candle_data(self, aggregators: Dict[str, CandleAggregator]) -> Dict[str, List[TickData]]:
        """Extract candle data from all aggregators"""
        all_candle_data = {}

        for aggregator_key, aggregator in aggregators.items():
            history = aggregator.get_history().copy()
            current = aggregator.get_current_candle()
            if current:
                history.append(current)
            all_candle_data[aggregator_key] = history
            logger.debug(f"{aggregator_key}: {len(history)} candles")

        return all_candle_data

    def _get_aggregator_key(self, indicator_def, aggregators: Dict[str, CandleAggregator]) -> str:
        """Get the correct aggregator key for an indicator"""
        timeframe = indicator_def.get_timeframe()
        agg_type = indicator_def.get_aggregator_type()

        # Try the full key first (e.g., "1m-normal", "5m-heiken")
        full_key = f"{timeframe}-{agg_type}"
        if full_key in aggregators:
            return full_key

        # Fallback to just timeframe if full key not found
        if timeframe in aggregators:
            return timeframe

        # Find any matching timeframe
        for key in aggregators.keys():
            if key.startswith(timeframe):
                return key

        # Last resort - return first available
        logger.warning(f"No matching aggregator found for {timeframe}-{agg_type}, using first available")
        return list(aggregators.keys())[0]

    def _calculate_indicator_batch(self, tick_history: List[TickData], indicator_def) -> List[float]:
        """
        Calculate single indicator for entire history using batch processing
        This uses the same indicator functions as the live system
        """
        try:
            if len(tick_history) < 10:
                return [0.0] * len(tick_history)

            # Use the same indicator functions as IndicatorProcessor
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

            # Ensure result is a list of the right length
            if isinstance(result, np.ndarray):
                return result.tolist()
            elif isinstance(result, list):
                return result
            elif isinstance(result, (int, float)):
                # Single value returned - expand to full timeline
                return [float(result)] * len(tick_history)
            else:
                logger.warning(f"Unexpected result type for {indicator_def.function}: {type(result)}")
                return [0.0] * len(tick_history)

        except Exception as e:
            logger.error(f"Error calculating {indicator_def.function}: {e}")
            return [0.0] * len(tick_history)

    def _apply_lookback_vectorized(self, raw_values: List[float], lookback: int) -> List[float]:
        """
        Apply time-based lookback scoring using vectorized operations
        This replicates the same logic as IndicatorProcessor.calculate_time_based_metric
        """
        if not raw_values:
            return []

        # Convert to numpy for faster operations
        raw_array = np.array(raw_values)
        processed_values = np.zeros(len(raw_array))

        # Apply lookback scoring for each time point
        for i in range(len(raw_array)):
            # Get lookback window up to current point
            start_idx = max(0, i + 1 - lookback)
            window = raw_array[start_idx:i+1]

            # Find non-zero indices (triggers)
            non_zero_mask = window != 0
            if not np.any(non_zero_mask):
                processed_values[i] = 0.0
                continue

            # Get most recent trigger
            non_zero_indices = np.where(non_zero_mask)[0]
            last_trigger_idx = non_zero_indices[-1]
            trigger_value = window[last_trigger_idx]

            # Calculate decay based on position from end
            lookback_location = len(window) - last_trigger_idx - 1
            lookback_ratio = lookback_location / float(lookback)

            # Apply same formula as live system
            processed_values[i] = (1.0 - lookback_ratio) * np.sign(trigger_value)

        return processed_values.tolist()

    def _calculate_bar_scores_batch(self, indicator_history: Dict[str, List[float]], max_length: int) -> Dict[str, List[float]]:
        """
        Calculate bar scores for entire timeline using batch processing
        """
        bar_score_history = {}

        # Check if bars are configured
        if not hasattr(self.config, 'bars') or not self.config.bars:
            logger.debug("No bar configurations found")
            return bar_score_history

        # Calculate bar scores for each bar configuration
        for bar_name, bar_config in self.config.bars.items():
            bar_scores = []

            # Get timeline length from indicator history
            timeline_length = max_length
            if indicator_history:
                timeline_length = max(len(values) for values in indicator_history.values() if values)

            # Calculate bar score at each time point
            for i in range(timeline_length):
                # Extract indicator weights from bar config
                if isinstance(bar_config, dict) and 'indicators' in bar_config:
                    weights = bar_config['indicators']
                else:
                    weights = bar_config

                # Calculate weighted sum for this time point
                weighted_sum = 0.0
                total_weight = 0.0

                for indicator_name, weight in weights.items():
                    if indicator_name in indicator_history:
                        indicator_values = indicator_history[indicator_name]
                        if i < len(indicator_values):
                            weighted_sum += indicator_values[i] * weight
                            total_weight += weight

                # Calculate final score
                final_score = weighted_sum / total_weight if total_weight > 0 else 0.0
                bar_scores.append(final_score)

            bar_score_history[bar_name] = bar_scores
            logger.debug(f"Calculated bar scores for {bar_name}: {len(bar_scores)} values")

        return bar_score_history