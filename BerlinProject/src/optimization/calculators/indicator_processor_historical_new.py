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
            return result, components, processed_values

        except Exception as e:
            logger.error(f"Error calculating {self.indicator.name()}: {e}")
            raise ValueError(f"Cannot calculate: {self.indicator.name()}")

    @staticmethod
    def _apply_lookback_vectorized(raw_values: List[float], lookback: int) -> List[float]:
        """
        Apply time-based lookback scoring using vectorized operations
        This replicates the same logic as IndicatorProcessor.calculate_time_based_metric
        """
        # if not raw_values:
        #     return []

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
        # Store primary timeframe info (calculated once when aggregators are provided)
        self.primary_timeframe_minutes: int = None
        self.primary_timeframe_length: int = None
        # logger.info(f"IndicatorProcessorHistoricalNew initialized with {len(self.config.indicators)} indicators")

    def _create_indicator_objects(self):
        indicators: List[IndicatorCalculator] = []
        try:
            for indicator_def in self.config.indicators:
                indicators.append(IndicatorCalculator(indicator_def))
        except Exception as e:
            print(e)
        return indicators

    def _initialize_primary_timeframe_info(self, aggregators: Dict[str, CandleAggregator]) -> None:
        """Calculate and store primary timeframe information once"""
        if not aggregators:
            self.primary_timeframe_minutes = 1
            self.primary_timeframe_length = 0
            return

        # Find shortest timeframe (primary)
        self.primary_timeframe_minutes = min(agg.get_timeframe_minutes() for agg in aggregators.values())

        # Get length from primary timeframe aggregator
        for agg in aggregators.values():
            if agg.get_timeframe_minutes() == self.primary_timeframe_minutes:
                history = agg.get_history()
                current = agg.get_current_candle()
                self.primary_timeframe_length = len(history) + (1 if current else 0)
                break

    def _align_to_primary_timeframe(
        self,
        values: List[float],
        indicator_timeframe_minutes: int
    ) -> np.ndarray:
        """
        Align indicator values from coarser timeframe to primary timeframe using linear interpolation.

        Args:
            values: Indicator values from coarser timeframe
            indicator_timeframe_minutes: Minutes per candle for this indicator

        Returns:
            Interpolated values aligned to primary timeframe
        """
        if not values or len(values) == 0:
            return np.zeros(self.primary_timeframe_length)

        # If already at primary timeframe, no interpolation needed
        if indicator_timeframe_minutes == self.primary_timeframe_minutes:
            return np.array(values)

        # Calculate the ratio (e.g., 5m/1m = 5)
        ratio = indicator_timeframe_minutes / self.primary_timeframe_minutes

        # Create index mappings
        # Old indices: where each coarse value sits in the primary timeline
        old_indices = np.arange(len(values)) * ratio

        # New indices: all positions in primary timeline
        new_indices = np.arange(self.primary_timeframe_length)

        # Linear interpolation
        values_array = np.array(values)
        interpolated = np.interp(new_indices, old_indices, values_array)

        return interpolated

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
            - component_history: {component_name: [component_value_at_tick_0, ...]}  # Not aligned to min timeframe
        """
        # logger.info("Starting batch historical indicator calculation...")

        # Initialize primary timeframe info once
        self._initialize_primary_timeframe_info(aggregators)

        # Extract all candle data from aggregators
        all_candle_data = self._extract_all_candle_data(aggregators)
        if not all_candle_data:
            return {}, {}, {}, {}

        # logger.info(f"Processing timeline of {self.primary_timeframe_length} data points")

        # Process each indicator
        raw_indicator_history = {}
        indicator_history: Dict[str, List[float]] = {}
        component_history = {}  # NEW: Store component data (MACD, SMA values, etc.)

        for indicator in self.indicator_calculators:
            # Get the correct aggregator key for this indicator
            aggregator_key = indicator.get_aggregator_key()
            candles = all_candle_data[aggregator_key]

            # Calculate raw indicator values (triggers) for entire history
            raw_values, components, processed_values = indicator.calculate_indicator_batch(candles)

            # Get the aggregator's timeframe in minutes
            aggregator = aggregators[aggregator_key]
            indicator_timeframe_minutes = aggregator.get_timeframe_minutes()

            # Align to primary timeframe if needed
            aligned_raw_values = self._align_to_primary_timeframe(raw_values, indicator_timeframe_minutes)
            aligned_processed_values = self._align_to_primary_timeframe(processed_values, indicator_timeframe_minutes)

            raw_indicator_history[indicator.name] = aligned_raw_values.tolist()
            indicator_history[indicator.name] = aligned_processed_values.tolist()

            # Align component values as well
            if components:
                for component_name, component_values in components.items():
                    component_history[f"{indicator.name}_{component_name}"] = component_values.tolist() if isinstance(component_values, np.ndarray) else component_values

            # logger.debug(f"Processed {indicator.name}: {len(aligned_processed_values)} values")

        # Calculate bar scores for entire timeline
        bar_score_history = self._calculate_bar_scores_batch(indicator_history, self.primary_timeframe_length)

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


    def _calculate_bar_scores_batch(self, indicator_history: Dict[str, List[float]], timeline_length: int) -> Dict[str, List[float]]:
        """
        Calculate bar scores for entire timeline using batch processing.
        All indicators are now aligned to primary timeframe, so calculation is simplified.
        """
        bar_score_history = {}

        # Check if bars are configured
        if not hasattr(self.config, 'bars') or not self.config.bars:
            logger.debug("No bar configurations found")
            return bar_score_history

        # Calculate bar scores for each bar configuration
        for bar_name, bar_config in self.config.bars.items():
            bar_scores = []

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
                        # All indicators are now aligned, so direct indexing is safe
                        weighted_sum += indicator_history[indicator_name][i] * weight
                        total_weight += weight

                # Calculate final score
                final_score = weighted_sum / total_weight if total_weight > 0 else 0.0
                bar_scores.append(final_score)

            bar_score_history[bar_name] = bar_scores
            logger.debug(f"Calculated bar scores for {bar_name}: {len(bar_scores)} values")

        return bar_score_history