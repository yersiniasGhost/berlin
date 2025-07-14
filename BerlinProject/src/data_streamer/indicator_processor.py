"""
Enhanced IndicatorProcessor with proper history tracking - CLEAN VERSION
"""

import logging
from typing import Tuple
from datetime import datetime

from candle_aggregator.candle_aggregator import CandleAggregator
from candle_aggregator.candle_aggregator_normal import CANormal
from candle_aggregator.candle_aggregator_heiken import CAHeiken
from features.indicators2 import support_level, resistance_level
from models.monitor_configuration import MonitorConfiguration
from features.indicators import *
from models.tick_data import TickData

logger = logging.getLogger('IndicatorProcessor')


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

        self.indicator_trigger_history: Dict[str, List[float]] = {}
        for indicator in self.config.indicators:
            self.indicator_trigger_history[indicator.name] = []

        self.first_pass = True

        logger.info(f"IndicatorProcessor initialized with {len(self.config.indicators)} indicators")

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

            # Determine if we should calculate (on PIP or when candle completes)
            calc_on_pip = indicator_def.calc_on_pip or self.first_pass
            should_calculate = calc_on_pip or aggregator.completed_candle

            if should_calculate:
                try:
                    # Calculate the indicator
                    result = self._calculate_single_indicator(all_candles, indicator_def)

                    if result is not None and len(result) > 0:
                        raw_value = float(result[-1])

                        # Store raw value (user-facing indicator name)
                        self.raw_indicators[indicator_def.name] = raw_value

                        # Store in history using unique key (internal tracking)
                        self.indicator_trigger_history[indicator_key].append(raw_value)

                        # Calculate time-based decay
                        lookback = indicator_def.parameters.get('lookback', 10)
                        trigger_history = np.array(self.indicator_trigger_history[indicator_key])
                        decay_value = self.calculate_time_based_metric(trigger_history, lookback)

                        # Store decayed value (user-facing indicator name)
                        self.indicators[indicator_def.name] = decay_value

                        logger.debug(f"Calculated {indicator_def.name}: raw={raw_value:.4f}, decay={decay_value:.4f}")

                except Exception as e:
                    logger.error(f"Error calculating indicator '{indicator_def.name}': {e}")
                    import traceback
                    traceback.print_exc()

        # Mark first pass as complete
        self.first_pass = False

        # Calculate bar scores from current indicator values
        bar_scores: Dict[str, float] = self._calculate_bar_scores(self.indicators)

        # Log summary
        active_indicators = len([v for v in self.indicators.values() if v > 0])
        logger.info(f"Calculated {len(self.indicators)} indicators, {active_indicators} active")

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
                                    indicator_def) -> np.ndarray:
        """
        Calculate a single indicator with enhanced debugging
        """
        try:
            # DEBUG: Show calculation attempt
            logger.info(f"    _calculate_single_indicator: {indicator_def.function}")
            logger.info(f"    Data points: {len(tick_history)}")

            if len(tick_history) < 10:  # Need minimum data
                logger.warning(f"    ❌ Insufficient data: {len(tick_history)} < 10 candles")
                return np.array([0.0])

            # Show sample data for debugging
            if len(tick_history) > 0:
                first_candle = tick_history[0]
                last_candle = tick_history[-1]
                logger.info(f"    First candle: {first_candle.timestamp} - Close: {first_candle.close}")
                logger.info(f"    Last candle: {last_candle.timestamp} - Close: {last_candle.close}")

            # Calculate based on function type
            result = None

            if indicator_def.function == 'sma_crossover':
                logger.info(f"    Calling sma_crossover with params: {indicator_def.parameters}")
                result = sma_crossover(tick_history, indicator_def.parameters)

            elif indicator_def.function == 'macd_histogram_crossover':
                logger.info(f"    Calling macd_histogram_crossover with params: {indicator_def.parameters}")

                # TEMP DEBUG: Let's manually check what MACD values look like
                from features.indicators import macd_calculation
                macd, signal, histogram = macd_calculation(tick_history,
                                                           indicator_def.parameters['fast'],
                                                           indicator_def.parameters['slow'],
                                                           indicator_def.parameters['signal'])

                # Show histogram statistics
                valid_hist = histogram[~np.isnan(histogram)]
                if len(valid_hist) > 0:
                    logger.info(f"    HISTOGRAM STATS:")
                    logger.info(f"      Min: {np.min(valid_hist):.6f}")
                    logger.info(f"      Max: {np.max(valid_hist):.6f}")
                    logger.info(f"      Mean: {np.mean(valid_hist):.6f}")
                    logger.info(f"      Last 10 values: {valid_hist[-10:]}")
                    logger.info(f"      Threshold: {indicator_def.parameters['histogram_threshold']:.6f}")

                    # Check how many values exceed threshold
                    if indicator_def.parameters['trend'] == 'bullish':
                        exceeds = np.sum(valid_hist > indicator_def.parameters['histogram_threshold'])
                        logger.info(f"      Values > threshold: {exceeds}/{len(valid_hist)}")
                    else:
                        exceeds = np.sum(valid_hist < -indicator_def.parameters['histogram_threshold'])
                        logger.info(f"      Values < -threshold: {exceeds}/{len(valid_hist)}")

                result = macd_histogram_crossover(tick_history, indicator_def.parameters)

                # DEBUG: Check what the crossover detection actually produces
                non_zero_indices = np.where(result != 0)[0]
                total_crossovers = np.sum(result)
                logger.info(f"    CROSSOVER DETECTION:")
                logger.info(f"      Total crossovers found: {len(non_zero_indices)} (sum: {total_crossovers})")
                logger.info(f"      Last 20 result values: {result[-20:]}")

                if len(non_zero_indices) > 0:
                    logger.info(f"      First few crossover indices: {non_zero_indices[:5]}")
                    logger.info(f"      Last few crossover indices: {non_zero_indices[-5:]}")
                    logger.info(
                        f"      Most recent crossover was at index: {non_zero_indices[-1]} (from end: {len(result) - non_zero_indices[-1] - 1})")
                else:
                    logger.info(f"      NO CROSSOVERS DETECTED!")

            elif indicator_def.function == 'bol_bands_lower_band_bounce':
                logger.info(f"    Calling bol_bands_lower_band_bounce with params: {indicator_def.parameters}")
                result = bol_bands_lower_band_bounce(tick_history, indicator_def.parameters)

            elif indicator_def.function == 'support_level':
                logger.info(f"    Calling support_level with params: {indicator_def.parameters}")
                result = support_level(tick_history, indicator_def.parameters)

            elif indicator_def.function == 'resistance_level':
                logger.info(f"    Calling resistance_level with params: {indicator_def.parameters}")
                result = resistance_level(tick_history, indicator_def.parameters)

            else:
                logger.warning(f"    ❌ Unknown indicator function: {indicator_def.function}")
                result = np.array([0.0])

            # DEBUG: Show result details
            if result is not None:
                logger.info(f"    ✅ Function returned: type={type(result)}, length={len(result)}")
                if hasattr(result, '__len__') and len(result) > 0:
                    logger.info(f"    Last value: {result[-1]}")
                    # Show some sample values
                    if len(result) > 5:
                        logger.info(f"    Last 5 values: {result[-5:]}")

                    # Convert to numpy array if it isn't already
                    if not isinstance(result, np.ndarray):
                        logger.info(f"    Converting {type(result)} to numpy array")
                        result = np.array(result)
                else:
                    logger.warning(f"    ❌ Result array is empty")
                    result = np.array([0.0])
            else:
                logger.warning(f"    ❌ Function returned None")
                result = np.array([0.0])

            return result

        except Exception as e:
            logger.error(f"    ❌ Exception in _calculate_single_indicator: {e}")
            import traceback
            traceback.print_exc()
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
        """Calculate weighted bar scores from indicator values"""
        bar_scores: Dict[str, float] = {}

        if not hasattr(self.config, 'bars') or not self.config.bars:
            return bar_scores

        for bar_name, bar_config in self.config.bars.items():
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