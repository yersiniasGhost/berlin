"""
Complete Historical Indicator Processor - Batch processing for genetic algorithms
"""

import logging
from typing import Tuple

from candle_aggregator.candle_aggregator import CandleAggregator
from models.monitor_configuration import MonitorConfiguration
from features.indicators import *
from indicator_triggers.indicator_base import IndicatorRegistry
from models.indicator_definition import IndicatorDefinition
logger = logging.getLogger('IndicatorProcessorHistoricalNew')


class IndicatorCalculator:
    def __init__(self, config: IndicatorDefinition):
        self.config: IndicatorDefinition = config
        self.aggregator_key = self.get_aggregator_key()
        ind: str = config.indicator
        if not ind:
            raise ValueError("Invalid indicator configuration.  Missing 'indicator' name/type")
        self.indicator = IndicatorRegistry().get_indicator_class(ind)(self.config)

    @property
    def name(self) -> str:
        return self.config.name

    def calculate_indicator_batch(self, tick_history: List[TickData]) -> Tuple[np.ndarray, Dict[str, np.ndarray], List[float]]:
        """
        Calculate single indicator for entire history using batch processing
        This uses the same indicator functions as the live system
        """
        try:
            if len(tick_history) < 10:
                return [0.0] * len(tick_history), {}, []
            result, components = self.indicator.calculate(tick_history)
            # Apply lookback scoring using vectorized operations
            processed_values = result
            lookback = self.config.parameters.get('lookback', None)
            if lookback:
                processed_values = self._apply_lookback_vectorized(result, lookback)
            return result, components, processed_values.tolist()

        except Exception as e:
            logger.error(f"Error calculating {self.indicator.name()}: {e}")
            raise ValueError(f"Cannot calculate: {self.indicator.name()}")

    @staticmethod
    def _apply_lookback_vectorized(raw_values: List[float], lookback: int) -> List[float]:
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


    def get_aggregator_key(self) -> str:
        """Get the correct aggregator key for an indicator"""
        timeframe = self.config.get_timeframe()
        agg_type = self.config.get_aggregator_type()

        # Try the full key first (e.g., "1m-normal", "5m-heiken")
        full_key = f"{timeframe}-{agg_type}"
        return full_key


class IndicatorProcessorHistoricalNew:
    """
    Optimized historical indicator processor - calculates all indicators for entire timeline at once
    """

    def __init__(self, configuration: MonitorConfiguration) -> None:
        self.config: MonitorConfiguration = configuration
        self.indicator_calculators: List[IndicatorCalculator] = self._create_indicator_objects()
        # logger.info(f"IndicatorProcessorHistoricalNew initialized with {len(self.config.indicators)} indicators")

    def _create_indicator_objects(self):
        indicators: List[IndicatorCalculator] = []
        try:
            for indicator_def in self.config.indicators:
                indicators.append(IndicatorCalculator(indicator_def))
        except Exception as e:
            print(e)
        return indicators

    def calculate_indicators(self, aggregators: Dict[str, CandleAggregator]) -> Tuple[
        Dict[str, List[float]],  # indicator_history (time-decayed)
        Dict[str, List[float]],  # raw_indicator_history (trigger values)
        Dict[str, List[float]],  # bar_score_history
        Dict[str, List[float]]   # component_history (MACD components, SMA values, etc.)
    ]:
        """
        Calculate indicators for entire historical timeline using batch operations

        Returns:
            - indicator_history: {indicator_name: [time_decayed_value_at_tick_0, ...]}
            - raw_indicator_history: {indicator_name: [trigger_value_at_tick_0, ...]}  
            - bar_score_history: {bar_name: [score_at_tick_0, score_at_tick_1, ...]}
            - component_history: {component_name: [component_value_at_tick_0, ...]}  # NEW
        """
        # logger.info("Starting batch historical indicator calculation...")

        # Extract all candle data from aggregators
        all_candle_data = self._extract_all_candle_data(aggregators)
        if not all_candle_data:
            return {}, {}, {}, {}

        max_length = max(len(candles) for candles in all_candle_data.values())
        # logger.info(f"Processing timeline of {max_length} data points")

        # Process each indicator
        raw_indicator_history = {}
        indicator_history: Dict[str, List[float]] = {}
        component_history = {}  # NEW: Store component data (MACD, SMA values, etc.)

        for indicator in self.indicator_calculators:
            # Get the correct aggregator key for this indicator
            aggregator_key = indicator.get_aggregator_key()

            candles = all_candle_data[aggregator_key]

            # Calculate raw indicator values (triggers) for entire history
            raw_values, component_history, processed_values = indicator.calculate_indicator_batch(candles)
            raw_indicator_history[indicator.name] = raw_values
            indicator_history[indicator.name] = processed_values

            # logger.debug(f"Processed {indicator_def.name}: {len(processed_values)} values")

        # Calculate bar scores for entire timeline
        bar_score_history = self._calculate_bar_scores_batch(indicator_history, max_length)

        # logger.info(f"Completed batch indicator calculation")
        return indicator_history, raw_indicator_history, bar_score_history, component_history


    @staticmethod
    def _extract_all_candle_data(aggregators: Dict[str, CandleAggregator]) -> Dict[str, List[TickData]]:
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