"""
Complete Historical Indicator Processor - Batch processing for genetic algorithms
"""

from typing import Tuple

from candle_aggregator.candle_aggregator import CandleAggregator
from models.monitor_configuration import MonitorConfiguration
from features.indicators import *
from indicator_triggers.indicator_base import IndicatorRegistry
from models.indicator_definition import IndicatorDefinition
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("IndicatorProcessorHistoricalNew")


class IndicatorCalculator:
    def __init__(self, config: IndicatorDefinition):
        self.config: IndicatorDefinition = config
        self.aggregator_key = self.get_aggregator_key()
        # Use indicator_class if available, otherwise fall back to name for backwards compatibility
        ind: str = config.indicator_class if config.indicator_class else config.name
        if not ind:
            raise ValueError(f"Indicator '{config.name}': Missing 'indicator_class' or 'name'")

        # DIAGNOSTIC: Log parameters received by indicator
        logger.info(f"📊 Creating indicator '{config.name}' (class: {ind})")
        logger.info(f"   Parameters passed to indicator: {config.parameters}")

        try:
            self.indicator = IndicatorRegistry().get_indicator_class(ind)(self.config)
            logger.info(f"   ✅ Indicator created successfully")
        except ValueError as val_err:
            # Re-raise with indicator name for better error messaging
            raise ValueError(f"Indicator '{config.name}': {str(val_err)}")

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
            trigger_values_with_lookback = result
            lookback = self.config.parameters.get('lookback', None)
            if lookback:
                trigger_values_with_lookback = self._apply_lookback_vectorized(result, lookback)
            return result, components, trigger_values_with_lookback

        except Exception as e:
            import traceback
            logger.error(f"Error calculating {self.indicator.name()}: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            raise ValueError(f"Cannot calculate: {self.indicator.name()}") from e

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
        trigger_values_with_lookback = np.zeros(len(raw_array))

        # Apply lookback scoring for each time point
        for i in range(len(raw_array)):
            # Get lookback window up to current point
            start_idx = max(0, i + 1 - lookback)
            window = raw_array[start_idx:i+1]

            # Find non-zero indices (triggers)
            non_zero_mask = window != 0
            if not np.any(non_zero_mask):
                trigger_values_with_lookback[i] = 0.0
                continue

            # Get most recent trigger
            non_zero_indices = np.where(non_zero_mask)[0]
            last_trigger_idx = non_zero_indices[-1]
            trigger_value = window[last_trigger_idx]

            # Calculate decay based on position from end
            lookback_location = len(window) - last_trigger_idx - 1
            lookback_ratio = lookback_location / float(lookback)

            # Clamp lookback_ratio to [0, 1] range to prevent values going below 0
            lookback_ratio = min(1.0, max(0.0, lookback_ratio))

            # Apply same formula as live system
            trigger_values_with_lookback[i] = (1.0 - lookback_ratio) * np.sign(trigger_value)

        return trigger_values_with_lookback.tolist()


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
        """Create indicator objects and collect validation errors"""
        indicators: List[IndicatorCalculator] = []
        validation_errors = []

        for indicator_def in self.config.indicators:
            try:
                indicators.append(IndicatorCalculator(indicator_def))
            except ValueError as val_err:
                # Capture parameter validation errors with indicator name
                error_msg = str(val_err)
                logger.error(f"❌ Validation error for indicator '{indicator_def.name}': {error_msg}")
                validation_errors.append(error_msg)
            except Exception as e:
                logger.error(f"❌ Error initializing indicator '{indicator_def.name}': {e}")
                validation_errors.append(f"Indicator '{indicator_def.name}' initialization error: {e}")

        # If there are validation errors, raise them all at once
        if validation_errors:
            combined_error = "\n".join(validation_errors)
            raise ValueError(f"Configuration validation failed:\n{combined_error}")

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
        Align indicator values from coarser timeframe to primary timeframe.

        For raw trigger values, uses step interpolation (hold values until next trigger).
        This method should only be used for raw trigger values, not lookback-decayed values.

        Args:
            values: Raw indicator trigger values from coarser timeframe
            indicator_timeframe_minutes: Minutes per candle for this indicator

        Returns:
            Step-interpolated values aligned to primary timeframe
        """
        if values is None or len(values) == 0:
            return np.zeros(self.primary_timeframe_length)

        # If already at primary timeframe, no interpolation needed
        if indicator_timeframe_minutes == self.primary_timeframe_minutes:
            return np.array(values)

        # Calculate the ratio (e.g., 5m/1m = 5)
        ratio = indicator_timeframe_minutes / self.primary_timeframe_minutes

        # Create result array
        aligned_values = np.zeros(self.primary_timeframe_length)

        # For each coarse timeframe value, fill the corresponding primary timeframe positions
        for coarse_idx, value in enumerate(values):
            # Calculate the range of primary indices this coarse value covers
            start_primary_idx = int(coarse_idx * ratio)
            end_primary_idx = min(int((coarse_idx + 1) * ratio), self.primary_timeframe_length)

            # Fill all primary positions with this value (step interpolation)
            aligned_values[start_primary_idx:end_primary_idx] = value

        return aligned_values

    def _apply_lookback_at_primary_timeframe(
        self,
        aligned_raw_values: np.ndarray,
        lookback_periods: int,
        indicator_timeframe_minutes: int
    ) -> np.ndarray:
        """
        Apply lookback decay at the primary (finest) timeframe resolution.

        This calculates decay based on the number of primary timeframe periods since the last trigger,
        not the number of indicator timeframe periods. For example, with a 5-minute indicator on a
        1-minute primary timeframe and lookback=10 (10 * 5min = 50min total):
        - If a trigger happens at 5-minute mark 0, it decays over the next 50 one-minute periods
        - The decay is smooth: 1.0, 0.98, 0.96, ... 0.02, 0.0 over 50 periods

        Args:
            aligned_raw_values: Raw trigger values aligned to primary timeframe
            lookback_periods: Number of indicator timeframe periods to look back
            indicator_timeframe_minutes: Minutes per indicator candle

        Returns:
            Lookback-decayed values at primary timeframe resolution
        """
        if lookback_periods is None or lookback_periods == 0:
            return aligned_raw_values

        # Convert lookback from indicator periods to primary periods
        # e.g., 10 periods * 5 minutes / 1 minute = 50 primary periods
        lookback_in_primary_periods = int(
            lookback_periods * indicator_timeframe_minutes / self.primary_timeframe_minutes
        )

        trigger_values_with_lookback = np.zeros(len(aligned_raw_values))

        # Apply lookback scoring for each time point at primary resolution
        for i in range(len(aligned_raw_values)):
            # Get lookback window up to current point (in primary timeframe)
            start_idx = max(0, i + 1 - lookback_in_primary_periods)
            window = aligned_raw_values[start_idx:i+1]

            # Find non-zero indices (triggers)
            non_zero_mask = window != 0
            if not np.any(non_zero_mask):
                trigger_values_with_lookback[i] = 0.0
                continue

            # Get most recent trigger
            non_zero_indices = np.where(non_zero_mask)[0]
            last_trigger_idx = non_zero_indices[-1]
            trigger_value = window[last_trigger_idx]

            # Calculate decay based on PRIMARY timeframe distance from trigger
            # This is the key change: decay happens at 1-minute resolution, not 5-minute
            lookback_location = len(window) - last_trigger_idx - 1
            lookback_ratio = lookback_location / float(lookback_in_primary_periods)

            # Clamp lookback_ratio to [0, 1] range
            lookback_ratio = min(1.0, max(0.0, lookback_ratio))

            # Apply decay formula
            trigger_values_with_lookback[i] = (1.0 - lookback_ratio) * np.sign(trigger_value)

        return trigger_values_with_lookback

    def _align_to_primary_timeframe_debug(
        self,
        values: List[float],
        indicator_timeframe_minutes: int,
        indicator_name: str,
        aggregator: CandleAggregator
    ) -> np.ndarray:
        """
        Debug version with timestamp and value output.
        """
        if values is None or len(values) == 0:
            return np.zeros(self.primary_timeframe_length)

        # If already at primary timeframe, no interpolation needed
        if indicator_timeframe_minutes == self.primary_timeframe_minutes:
            logger.info(f"[ALIGN DEBUG] {indicator_name}: No alignment needed (already at {self.primary_timeframe_minutes}m)")
            return np.array(values)

        # Calculate the ratio (e.g., 5m/1m = 5)
        ratio = indicator_timeframe_minutes / self.primary_timeframe_minutes

        # Create index mappings
        old_indices = np.arange(len(values)) * ratio
        new_indices = np.arange(self.primary_timeframe_length)

        # Linear interpolation
        values_array = np.array(values)
        interpolated = np.interp(new_indices, old_indices, values_array)

        return interpolated

    def calculate_indicators(self, aggregators: Dict[str, CandleAggregator]) -> Tuple[
        Dict[str, List[float]],  # indicator_history (time-decayed)
        Dict[str, List[float]],  # raw_indicator_history (trigger values)
        Dict[str, List[float]],  # bar_score_history
        Dict[str, List[float]],  # component_history (MACD components, SMA values, etc.)
        Dict[str, str]           # indicator_agg_mapping: indicator_name -> agg_config
    ]:
        """
        Calculate indicators for entire historical timeline using batch operations

        Returns:
            - indicator_history: {indicator_name: [time_decayed_value_at_tick_0, ...]}
            - raw_indicator_history: {indicator_name: [trigger_value_at_tick_0, ...]}
            - bar_score_history: {bar_name: [score_at_tick_0, score_at_tick_1, ...]}
            - component_history: {component_name: [component_value_at_tick_0, ...]}  # At native timeframe resolution
            - indicator_agg_mapping: {indicator_name: agg_config}  # Maps indicators to their aggregator
        """
        # logger.info("Starting batch historical indicator calculation...")

        # Initialize primary timeframe info once
        self._initialize_primary_timeframe_info(aggregators)

        # Extract all candle data from aggregators
        all_candle_data = self._extract_all_candle_data(aggregators)
        if not all_candle_data:
            return {}, {}, {}, {}, {}

        # logger.info(f"Processing timeline of {self.primary_timeframe_length} data points")

        # Process each indicator
        raw_indicator_history = {}
        indicator_history: Dict[str, List[float]] = {}
        component_history = {}  # Store component data (MACD, SMA values, etc.) at native resolution
        indicator_agg_mapping = {}  # Maps indicator_name -> agg_config for timestamp lookup

        for indicator in self.indicator_calculators:
            # Get the correct aggregator key for this indicator
            aggregator_key = indicator.get_aggregator_key()
            candles = all_candle_data[aggregator_key]

            # Calculate raw indicator values (triggers) for entire history
            # NOTE: We now ignore the pre-calculated lookback values from calculate_indicator_batch
            # because we'll recalculate decay at the primary timeframe resolution
            raw_values, components, _ = indicator.calculate_indicator_batch(candles)

            # Get the aggregator's timeframe in minutes
            aggregator = aggregators[aggregator_key]
            indicator_timeframe_minutes = aggregator.get_timeframe_minutes()

            # DEBUG: Log alignment info
            # print(f"[ALIGN] {indicator.name}: {indicator_timeframe_minutes}m -> {self.primary_timeframe_minutes}m | "
            #            f"Before: {len(raw_values)} values | After: {self.primary_timeframe_length} values")

            # Step 1: Align raw trigger values to primary timeframe
            aligned_raw_values = self._align_to_primary_timeframe(raw_values, indicator_timeframe_minutes)

            # Step 2: Apply lookback decay at primary timeframe resolution
            lookback_periods = indicator.config.parameters.get('lookback', None)
            aligned_trigger_values_with_lookback = self._apply_lookback_at_primary_timeframe(
                aligned_raw_values,
                lookback_periods,
                indicator_timeframe_minutes
            )

            # DEBUG: Verify alignment worked
            # print(f"[VERIFY] {indicator.name}: aligned_raw_values length = {len(aligned_raw_values)}, "
            #            f"aligned_trigger_values_with_lookback length = {len(aligned_trigger_values_with_lookback)}, "
            #            f"expected = {self.primary_timeframe_length}")

            raw_indicator_history[indicator.name] = aligned_raw_values.tolist()
            indicator_history[indicator.name] = aligned_trigger_values_with_lookback.tolist()

            # Store indicator -> aggregator mapping for timestamp lookup
            indicator_agg_mapping[indicator.name] = aggregator_key

            # Store component values at native resolution (NOT aligned to primary timeframe)
            if components:
                for component_name, component_values in components.items():
                    key = f"{indicator.name}_{component_name}"
                    component_history[key] = component_values.tolist() if isinstance(component_values, np.ndarray) else component_values

        # Calculate bar scores for entire timeline
        bar_score_history = self._calculate_bar_scores_batch(indicator_history, self.primary_timeframe_length)
        return indicator_history, raw_indicator_history, bar_score_history, component_history, indicator_agg_mapping


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

            # Extract indicator weights from bar config
            if isinstance(bar_config, dict) and 'indicators' in bar_config:
                weights = bar_config['indicators']
            else:
                weights = bar_config

            # Calculate bar score at each time point
            for i in range(timeline_length):
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