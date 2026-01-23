"""
Enhanced IndicatorProcessor with proper history tracking - Refactored to use IndicatorRegistry
"""

from typing import Tuple, Dict, List
from datetime import datetime
import numpy as np

from candle_aggregator.candle_aggregator import CandleAggregator
from models.monitor_configuration import MonitorConfiguration
from models.tick_data import TickData
from indicator_triggers.indicator_base import IndicatorRegistry, IndicatorType
from features.indicators import *
# Import refactored indicators to ensure they are registered
import indicator_triggers.refactored_indicators
# Import trend indicators to ensure they are registered
import indicator_triggers.trend_indicators
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("IndicatorProcessor")


class IndicatorProcessor:
    """
    Processes indicators for completed candles with time-based decay and history tracking
    """

    def __init__(self, configuration: MonitorConfiguration) -> None:
        self.config: MonitorConfiguration = configuration
        self.stored_values: Dict[str, Dict[str, any]] = {}

        # Add history tracking
        self.indicator_history: Dict[str, List[float]] = {}
        self.bar_history: Dict[str, List[float]] = {}
        self.timestamp_history: List[datetime] = []
        self.max_history_length: int = 100  # Keep last 100 data points
        self.indicators: Dict[str, float] = {}
        self.raw_indicators: Dict[str, float] = {}
        self.component_data: Dict[str, float] = {}  # Store component data (MACD, SMA values, etc.)

        # Data status tracking for insufficient data warnings
        self.data_status: Dict[str, any] = {
            'has_sufficient_data': False,
            'warnings': [],
            'tick_counts': {},  # aggregator_key -> tick_count
            'required_ticks': 0  # max required across all indicators
        }

        self.indicator_trigger_history: Dict[str, List[float]] = {}
        for indicator in self.config.indicators:
            self.indicator_trigger_history[indicator.name] = []

        # Create indicator objects using IndicatorRegistry
        self.indicator_objects: Dict[str, any] = {}
        self._initialize_indicators()

        # Calculate required ticks based on indicator parameters
        self._calculate_required_ticks()

        self.first_pass = True

        logger.info(f"IndicatorProcessor initialized with {len(self.config.indicators)} indicators")

    def _calculate_required_ticks(self) -> None:
        """Calculate the minimum required ticks based on indicator parameters"""
        max_required = 10  # Default minimum

        for indicator_def in self.config.indicators:
            params = indicator_def.parameters or {}
            # Check common period-related parameters
            period = params.get('period', 0)
            fast_period = params.get('fast_period', 0)
            slow_period = params.get('slow_period', 0)
            signal_period = params.get('signal_period', 0)
            lookback = params.get('lookback', 0)

            # The indicator needs at least the largest period + some buffer
            indicator_required = max(period, fast_period, slow_period, signal_period, lookback)
            if indicator_required > 0:
                # Add buffer for calculation (indicator needs period + 1 at minimum)
                indicator_required += 5
                max_required = max(max_required, indicator_required)

        self.data_status['required_ticks'] = max_required
        logger.info(f"Required ticks for indicators: {max_required}")

    def _initialize_indicators(self) -> None:
        """Initialize indicator objects using IndicatorRegistry"""
        for indicator_def in self.config.indicators:
            try:
                ind_class_name = indicator_def.indicator_class

                # Get indicator class from registry
                indicator_class = IndicatorRegistry().get_indicator_class(ind_class_name)

                # Instantiate the indicator with config
                indicator_instance = indicator_class(indicator_def)
                self.indicator_objects[indicator_def.name] = indicator_instance

                logger.debug(f"Initialized indicator: {indicator_def.name} using {ind_class_name}")

            except Exception as e:
                logger.error(f"Failed to initialize indicator '{indicator_def.name}': {e}")
                import traceback
                logger.error(traceback.format_exc())

    def _update_data_status(self, aggregators: Dict[str, 'CandleAggregator']) -> None:
        """Update data status with tick counts and warnings for insufficient data"""
        warnings = []
        tick_counts = {}
        min_tick_count = 0

        if aggregators:
            counts = []
            for agg_key, aggregator in aggregators.items():
                # Count total candles (history + current)
                count = len(aggregator.get_history())
                if aggregator.get_current_candle():
                    count += 1
                tick_counts[agg_key] = count
                counts.append(count)
            min_tick_count = min(counts) if counts else 0

        required = self.data_status['required_ticks']
        has_sufficient = min_tick_count >= required

        # Generate warning message if insufficient data
        if not has_sufficient:
            warnings.append(f"Requires {required} ticks, have {min_tick_count}")

        self.data_status['tick_counts'] = tick_counts
        self.data_status['has_sufficient_data'] = has_sufficient
        self.data_status['warnings'] = warnings
        self.data_status['min_tick_count'] = min_tick_count

    def get_data_status(self) -> Dict[str, any]:
        """Get current data status including warnings for UI display"""
        return self.data_status.copy()

    # def calculate_indicators_new(self, aggregators: Dict[str, 'CandleAggregator']) -> Tuple[
    #     Dict[str, float], Dict[str, float], Dict[str, float]]:
    #
    #     for indicator_def in self.config.indicators:
    #         timeframe = indicator_def.time_increment
    #
    #         # add aggregatopr type
    #
    #         if timeframe not in aggregators:
    #             continue
    #
    #         aggregator = aggregators[timeframe]
    #         all_candles = aggregator.get_history().copy()
    #
    #         if aggregator.get_current_candle():
    #             all_candles.append(aggregator.get_current_candle())
    #
    #         calc_on_pip = indicator_def.calc_on_pip or self.first_pass
    #         if calc_on_pip or aggregator.completed_candle:
    #             try:
    #                 result = self._calculate_single_indicator(all_candles, indicator_def)
    #                 if result is not None and len(result) > 0:
    #                     value = float(result[-1])
    #
    #                     self.raw_indicators[indicator_def.name] = value
    #                     self.indicator_trigger_history[indicator_def.name].append(value)
    #
    #                     lookback = indicator_def.parameters.get('lookback')
    #                     trigger_history = np.array(self.indicator_trigger_history[indicator_def.name])
    #                     decay_value = self.calculate_time_based_metric(trigger_history, lookback)
    #                     self.indicators[indicator_def.name] = decay_value
    #             except Exception as e:
    #                 logger.error(f"Error calculating indicator '{indicator_def.name}': {e}")
    #
    #     self.first_pass = False
    #     bar_scores: Dict[str, float] = self._calculate_bar_scores(self.indicators)
    #
    #     return self.indicators, self.raw_indicators, bar_scores

    def calculate_indicators_new(self, aggregators: Dict[str, 'CandleAggregator']) -> Tuple[
        Dict[str, float], Dict[str, float], Dict[str, float]]:
        """
        Calculate indicators using the new agg_config system with proper aggregator key matching

        Args:
            aggregators: Dict of aggregator_key -> CandleAggregator (e.g., "1m-heiken" -> aggregator)

        Returns:
            Tuple of (indicators, raw_indicators, bar_scores)
        """
        # Update tick counts and data status
        self._update_data_status(aggregators)

        logger.info(f"calculate_indicators_new: first_pass={self.first_pass}, "
                   f"aggregators={list(aggregators.keys())}, "
                   f"indicators_to_calc={len(self.config.indicators)}")

        for indicator_def in self.config.indicators:
            # FIXED: Create the full aggregator key that matches how aggregators are stored
            timeframe = indicator_def.get_timeframe()
            agg_type = indicator_def.get_aggregator_type()
            agg_key = f"{timeframe}-{agg_type}"  # e.g., "1m-heiken", "5m-normal"

            # FIXED: Look for the full aggregator key instead of just timeframe
            if agg_key not in aggregators:
                logger.warning(f"Aggregator not found for {indicator_def.name}: {agg_key}")
                logger.debug(f"Available aggregators: {list(aggregators.keys())}")
                continue

            aggregator = aggregators[agg_key]

            # Verify aggregator type matches (optional validation)
            if aggregator._get_aggregator_type() != agg_type:
                logger.warning(f"Aggregator type mismatch for {indicator_def.name}: "
                               f"expected {agg_type}, got {aggregator._get_aggregator_type()}")

            # Create unique key for internal storage (to handle multiple indicators per aggregator)
            indicator_key = f"{agg_key}_{indicator_def.name}"

            # Initialize tracking for this indicator if needed
            if indicator_key not in self.indicator_trigger_history:
                self.indicator_trigger_history[indicator_key] = []

            # Get all candles from this aggregator (history + current)
            all_candles = aggregator.get_history().copy()
            if aggregator.get_current_candle():
                all_candles.append(aggregator.get_current_candle())

            # Skip debug output for performance

            # Determine if we should calculate (on PIP or when candle completes)
            calc_on_pip = indicator_def.calc_on_pip or self.first_pass
            should_calculate = calc_on_pip or aggregator.completed_candle

            if should_calculate:
                try:
                    # Calculate the indicator (now returns tuple of result and components)
                    result, components = self._calculate_single_indicator(all_candles, indicator_def)

                    if result is not None and len(result) > 0:
                        raw_value = float(result[-1])

                        # Store raw value (user-facing indicator name)
                        self.raw_indicators[indicator_def.name] = raw_value

                        # Check if this is a TREND indicator (no decay) or SIGNAL indicator (with decay)
                        indicator_obj = self.indicator_objects.get(indicator_def.name)
                        is_trend_indicator = (indicator_obj and
                                              hasattr(indicator_obj, 'get_indicator_type') and
                                              indicator_obj.get_indicator_type() == IndicatorType.TREND)

                        if is_trend_indicator:
                            # TREND indicators: use raw value directly (no decay)
                            self.indicators[indicator_def.name] = raw_value
                        else:
                            # SIGNAL indicators: apply time-based decay
                            self.indicator_trigger_history[indicator_key].append(raw_value)
                            lookback = indicator_def.parameters.get('lookback', 10)
                            trigger_history = np.array(self.indicator_trigger_history[indicator_key])
                            decay_value = self.calculate_time_based_metric(trigger_history, lookback)
                            self.indicators[indicator_def.name] = decay_value

                        # Store component data (latest values only for real-time)
                        if components:
                            for component_name, component_values in components.items():
                                # Store the latest component value
                                if isinstance(component_values, (list, np.ndarray)) and len(component_values) > 0:
                                    latest_value = float(component_values[-1]) if not np.isnan(component_values[-1]) else 0.0
                                    self.component_data[f"{indicator_def.name}_{component_name}"] = latest_value

                        # Debug: Print when candlestick patterns trigger
                        if "CDLPatternIndicator" in str(indicator_def.indicator_class) and raw_value > 0:
                            print(f"  📊 Indicator '{indicator_def.name}': raw={raw_value:.4f}, decay={decay_value:.4f}")

                        logger.debug(f"Calculated {indicator_def.name}: raw={raw_value:.4f}, decay={decay_value:.4f}")

                except Exception as e:
                    logger.error(f"Error calculating indicator '{indicator_def.name}': {e}")
                    import traceback
                    traceback.print_exc()

        # Mark first pass as complete
        self.first_pass = False

        # Calculate bar scores from current indicator values
        bar_scores: Dict[str, float] = self._calculate_bar_scores(self.indicators)

        # Debug: Print bar scores when patterns are active
        if any("CDLPatternIndicator" in str(ind.indicator_class) for ind in self.config.indicators):
            active_patterns = [name for name, val in self.indicators.items() if val > 0 and any(name == ind.name for ind in self.config.indicators if "CDLPatternIndicator" in str(ind.indicator_class))]
            if active_patterns:
                print(f"  📈 Bar Scores: {bar_scores}")

        # Log summary
        active_indicators = len([v for v in self.indicators.values() if v > 0])
        # logger.info(f"Calculated {len(self.indicators)} indicators, {active_indicators} active")

        return self.indicators, self.raw_indicators, bar_scores

    # def calculate_time_based_metric(self, indicator_data: np.ndarray, lookback: int) -> float:
    #     if len(indicator_data) == 0:
    #         return 0.0
    #
    #     search = indicator_data[-lookback:] if len(indicator_data) >= lookback else indicator_data
    #     non_zero_indices = np.nonzero(search)[0]
    #     if non_zero_indices.size == 0:
    #         return 0.0
    #     c = search[non_zero_indices[-1]]
    #     lookback_location = len(search) - non_zero_indices[-1] - 1
    #     lookback_ratio = lookback_location / float(len(search))
    #     metric = (1.0 - lookback_ratio) * np.sign(c)
    #
    #     return metric
    def calculate_time_based_metric(self, indicator_data: np.ndarray, lookback: int) -> float:
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


    def _calculate_single_indicator(self,
                                    tick_history: List[TickData],
                                    indicator_def) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """
        Calculate a single indicator using IndicatorRegistry system

        Returns:
            Tuple of (trigger_values, component_data)
            - trigger_values: Array of indicator trigger signals
            - component_data: Dict of component values (e.g., MACD components, SMA values)
        """
        try:
            if len(tick_history) < 10:  # Need minimum data
                return np.array([0.0]), {}

            # Get the indicator object
            if indicator_def.name not in self.indicator_objects:
                logger.warning(f"Indicator object not found: {indicator_def.name}")
                return np.array([0.0]), {}

            indicator = self.indicator_objects[indicator_def.name]

            # Calculate using the indicator's calculate method
            result, components = indicator.calculate(tick_history)

            # Ensure we return valid numpy arrays
            if result is not None and hasattr(result, '__len__') and len(result) > 0:
                if not isinstance(result, np.ndarray):
                    result = np.array(result)
            else:
                result = np.array([0.0])

            return result, components

        except Exception as e:
            logger.error(f"Error calculating indicator '{indicator_def.name}': {e}")
            import traceback
            logger.error(traceback.format_exc())
            return np.array([0.0]), {}


    def _calculate_single_indicator_orig(self,
                                    tick_history: List[TickData],
                                    indicator_def) -> np.ndarray:
        """
        Calculate a single indicator - CLEAN VERSION (no debug logging)
        """
        try:
            if len(tick_history) < 10:  # Need minimum data
                return np.array([0.0])

            # Calculate based on function type
            result = None

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
                result = np.array([0.0])

            # Ensure we return a valid numpy array
            if result is not None and hasattr(result, '__len__') and len(result) > 0:
                if not isinstance(result, np.ndarray):
                    result = np.array(result)
            else:
                result = np.array([0.0])

            return result

        except Exception as e:
            logger.error(f"Error calculating indicator '{indicator_def.function}': {e}")
            return np.array([0.0])

    def calculate_indicators(self,
                           all_candle_data: Dict[str, List[TickData]],
                           completed_timeframe: str = None) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
        """
        Calculate indicators using appropriate timeframe data
        """
        if completed_timeframe:
            self._calculate_fresh_indicators(all_candle_data, completed_timeframe)

        current_indicators, current_raw = self._get_current_decayed_values()
        bar_scores = self._calculate_bar_scores(current_indicators)

        # Store in history when we have completed timeframe
        if completed_timeframe:
            self._store_history_snapshot(current_indicators, bar_scores)

        return current_indicators, current_raw, bar_scores

    def _get_current_decayed_values(self) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Get current indicator values with time-based decay
        """
        current_indicators: Dict[str, float] = {}
        current_raw: Dict[str, float] = {}
        now: datetime = datetime.now()

        for indicator_name, stored_data in self.stored_values.items():
            last_update: datetime = stored_data['timestamp']
            time_elapsed = now - last_update
            minutes_elapsed: float = time_elapsed.total_seconds() / 60

            timeframe: str = stored_data['timeframe']
            timeframe_minutes: int = self._get_timeframe_minutes(timeframe)

            original_value: float = stored_data['value']
            decayed_value: float = self._apply_decay(original_value, minutes_elapsed, timeframe_minutes)

            current_indicators[indicator_name] = decayed_value
            current_raw[indicator_name] = stored_data['raw_value']

        return current_indicators, current_raw

    def _apply_decay(self, original_value: float, minutes_elapsed: float, timeframe_minutes: int) -> float:
        """Apply time-based decay to indicator values"""
        if original_value <= 0.0:
            return 0.0

        # Continuous decay instead of step-based
        decay_rate = 0.1 / timeframe_minutes  # 0.1 per timeframe period
        decayed_value = original_value - (minutes_elapsed * decay_rate)
        decayed_value = max(0.0, decayed_value)

        return round(decayed_value, 1)

    def _get_timeframe_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes"""
        timeframe_map: Dict[str, int] = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60
        }
        return timeframe_map.get(timeframe, 1)

    def _calculate_bar_scores(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """Calculate weighted bar scores from indicator values with trend gating.

        Trend gating allows trend indicators to filter/gate signal indicators:
        - If trend indicators are configured, they act as multipliers on signal scores
        - If no trend indicators are configured, bar score is calculated normally
        - Trend gate is calculated based on bar type (bull/bear) and trend logic (AND/OR/AVG)

        Bar config structure:
        {
            "bar_name": {
                "type": "bull" or "bear",
                "indicators": {"signal1": weight1, "signal2": weight2},
                "trend_indicators": {
                    "trend1": {"weight": 1.0, "mode": "soft"},
                    "trend2": {"weight": 0.5, "mode": "hard"}
                },
                "trend_logic": "AND" | "OR" | "AVG",
                "trend_threshold": 0.0
            }
        }
        """
        bar_scores: Dict[str, float] = {}

        if not hasattr(self.config, 'bars') or not self.config.bars:
            return bar_scores

        for bar_name, bar_config in self.config.bars.items():
            # Get bar type (bull/bear) - defaults to bull for backward compatibility
            bar_type = bar_config.get('type', 'bull') if isinstance(bar_config, dict) else 'bull'

            # Extract signal indicator weights
            if isinstance(bar_config, dict) and 'indicators' in bar_config:
                signal_weights: Dict[str, float] = bar_config['indicators']
            else:
                signal_weights = bar_config if isinstance(bar_config, dict) else {}

            # Calculate signal score (existing weighted average logic)
            signal_score = self._calculate_weighted_signal_score(indicators, signal_weights)

            # Extract trend indicator configuration (NEW)
            trend_config = bar_config.get('trend_indicators', {}) if isinstance(bar_config, dict) else {}
            trend_logic = bar_config.get('trend_logic', 'AND') if isinstance(bar_config, dict) else 'AND'
            trend_threshold = bar_config.get('trend_threshold', 0.0) if isinstance(bar_config, dict) else 0.0

            # Calculate trend gate (NEW)
            trend_gate = self._calculate_trend_gate(
                indicators, trend_config, bar_type, trend_logic, trend_threshold
            )

            # Apply trend gate to signal score
            final_score = signal_score * trend_gate
            bar_scores[bar_name] = final_score

            # Debug logging for trend gating
            if trend_config and logger.isEnabledFor(10):  # DEBUG level
                logger.debug(f"Bar '{bar_name}': signal={signal_score:.3f}, "
                           f"trend_gate={trend_gate:.3f}, final={final_score:.3f}")

        return bar_scores

    def _calculate_weighted_signal_score(self, indicators: Dict[str, float],
                                         weights: Dict[str, float]) -> float:
        """Calculate weighted average of signal indicator values.

        Args:
            indicators: Dict of indicator_name -> current value
            weights: Dict of indicator_name -> weight

        Returns:
            Weighted average score (0.0 to 1.0 typically)
        """
        weighted_sum: float = 0.0
        total_weight: float = 0.0

        for indicator_name, weight in weights.items():
            if indicator_name in indicators:
                weighted_sum += indicators[indicator_name] * weight
                total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _calculate_trend_gate(self, indicators: Dict[str, float],
                              trend_config: Dict[str, Dict],
                              bar_type: str, trend_logic: str,
                              trend_threshold: float) -> float:
        """Calculate trend gate multiplier for bar scores.

        Trend indicators output values from -1.0 (bearish) to +1.0 (bullish).
        The gate is calculated based on alignment with bar direction.

        Args:
            indicators: Dict of indicator_name -> current value (includes trend indicators)
            trend_config: Dict of trend_indicator_name -> {weight, mode}
                         mode: "hard" = binary 0/1, "soft" = continuous 0.0-1.0
            bar_type: "bull" or "bear" - determines expected trend direction
            trend_logic: "AND" (min), "OR" (max), or "AVG" (weighted average)
            trend_threshold: Minimum gate value required (below this -> 0.0)

        Returns:
            Trend gate multiplier (0.0 to 1.0)
            - 1.0 = full pass-through (no trend indicators OR strong confirmation)
            - 0.0 = blocked (trend indicates opposite direction)
            - 0.0-1.0 = partial gating based on trend strength
        """
        if not trend_config:
            # No trend indicators configured - pass through
            return 1.0

        trend_values = []

        for trend_name, config in trend_config.items():
            if trend_name not in indicators:
                logger.warning(f"Trend indicator '{trend_name}' not found in indicators")
                continue

            # Get trend indicator value (-1.0 to +1.0)
            trend_value = indicators[trend_name]

            # Get config options
            if isinstance(config, dict):
                weight = config.get('weight', 1.0)
                mode = config.get('mode', 'soft')
            else:
                # Simple weight value (backward compatibility)
                weight = float(config)
                mode = 'soft'

            # Align direction with bar type
            # For BULL bars: positive trend = good, negative = bad
            # For BEAR bars: negative trend = good, positive = bad
            if bar_type.lower() == 'bear':
                # Invert: bearish trend (negative) should give positive gate
                trend_value = -trend_value

            # Apply gating mode
            if mode == 'hard':
                # Binary gate: 1.0 if trend confirms, 0.0 otherwise
                gated_value = 1.0 if trend_value > 0 else 0.0
            else:  # 'soft'
                # Continuous gate: use the positive portion of trend value
                # Values <= 0 give gate of 0, positive values give proportional gate
                gated_value = max(0.0, min(1.0, trend_value))

            trend_values.append((gated_value, weight))

        if not trend_values:
            # No valid trend indicators found - pass through
            return 1.0

        # Combine trend values based on logic
        if trend_logic.upper() == 'AND':
            # AND: All trends must confirm - use minimum
            gate = min(v for v, w in trend_values)
        elif trend_logic.upper() == 'OR':
            # OR: Any trend confirms - use maximum
            gate = max(v for v, w in trend_values)
        else:  # 'AVG' or default
            # AVG: Weighted average of trend gates
            total_weight = sum(w for v, w in trend_values)
            if total_weight > 0:
                gate = sum(v * w for v, w in trend_values) / total_weight
            else:
                gate = 1.0

        # Apply threshold - gate must exceed threshold or it's blocked
        if gate < trend_threshold:
            return 0.0

        return gate

    def _store_history_snapshot(self, indicators: Dict[str, float], bar_scores: Dict[str, float]) -> None:
        """Store current indicator and bar values in history"""
        current_time = datetime.now()

        # Add timestamp to history
        self.timestamp_history.append(current_time)

        # Store indicator values
        for indicator_name, value in indicators.items():
            if indicator_name not in self.indicator_history:
                self.indicator_history[indicator_name] = []
            self.indicator_history[indicator_name].append(value)

        # Store bar scores
        for bar_name, value in bar_scores.items():
            if bar_name not in self.bar_history:
                self.bar_history[bar_name] = []
            self.bar_history[bar_name].append(value)

        # Trim history to max length
        if len(self.timestamp_history) > self.max_history_length:
            # Remove oldest entries
            excess = len(self.timestamp_history) - self.max_history_length
            self.timestamp_history = self.timestamp_history[excess:]

            for indicator_name in self.indicator_history:
                self.indicator_history[indicator_name] = self.indicator_history[indicator_name][excess:]

            for bar_name in self.bar_history:
                self.bar_history[bar_name] = self.bar_history[bar_name][excess:]

    def get_history_data(self) -> Dict:
        """Get formatted history data for UI"""
        if not self.timestamp_history:
            return {
                'timestamps': [],
                'indicators': {},
                'bar_scores': {},
                'periods': 0
            }

        return {
            'timestamps': [ts.isoformat() for ts in self.timestamp_history],
            'indicators': self.indicator_history.copy(),
            'bar_scores': self.bar_history.copy(),
            'periods': len(self.timestamp_history)
        }