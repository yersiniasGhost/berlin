"""
Enhanced IndicatorProcessor with extensive debug logging
"""

import logging
from typing import Tuple, Dict
from datetime import datetime

from features.indicators2 import support_level, resistance_level
from models.monitor_configuration import MonitorConfiguration
from features.indicators import *

logger = logging.getLogger('IndicatorProcessor')


class IndicatorProcessor:
    def __init__(self, configuration: MonitorConfiguration):
        self.config: MonitorConfiguration = configuration

        # Store last calculated values with timestamps
        # {indicator_name: {'value': float, 'raw_value': float, 'timestamp': datetime, 'timeframe': str}}
        self.stored_values: Dict[str, Dict] = {}

        # Debug: Print configuration at startup
        print(f"🔧 INIT: IndicatorProcessor with {len(self.config.indicators)} indicators")
        for ind in self.config.indicators:
            print(f"🔧 INIT: - {ind.name} ({getattr(ind, 'time_increment', '1m')}) - {ind.function}")

        if hasattr(self.config, 'bars') and self.config.bars:
            print(f"🔧 INIT: Bars configuration: {list(self.config.bars.keys())}")
            for bar_name, weights in self.config.bars.items():
                print(f"🔧 INIT: - {bar_name}: {weights}")

    def calculate_indicators(self, all_candle_data: Dict[str, List[TickData]],
                             completed_timeframe: str = None) -> Tuple[
        Dict[str, float], Dict[str, float], Dict[str, float]]:
        """
        Calculate indicators using appropriate timeframe data

        Args:
            all_candle_data: {timeframe: [candles]} from all aggregators
            completed_timeframe: Which timeframe just completed (for fresh calculations)
        """
        print(f"🔧 CALCULATE_INDICATORS called with completed_timeframe: {completed_timeframe}")
        print(f"🔧 Available timeframes: {list(all_candle_data.keys())}")
        for tf, candles in all_candle_data.items():
            print(f"🔧 {tf}: {len(candles)} candles available")
            if candles:
                print(f"🔧 {tf} latest: {candles[-1].timestamp} @ ${candles[-1].close:.2f}")

        current_indicators = {}
        current_raw = {}

        # Only recalculate indicators that match the completed timeframe
        if completed_timeframe:
            self._calculate_fresh_indicators(all_candle_data, completed_timeframe)

        # Apply decay to all stored indicators
        current_indicators, current_raw = self._get_current_decayed_values()

        # Calculate bar scores from current indicator values
        bar_scores = self._calculate_bar_scores(current_indicators)

        print(f"🔧 FINAL RESULTS:")
        print(f"🔧 - Indicators: {current_indicators}")
        print(f"🔧 - Raw: {current_raw}")
        print(f"🔧 - Bar Scores: {bar_scores}")

        return current_indicators, current_raw, bar_scores

    def _calculate_fresh_indicators(self, all_candle_data: Dict[str, List[TickData]], completed_timeframe: str) -> None:
        """
        Calculate fresh values for indicators that match the completed timeframe
        """
        print(f"🔧 CALCULATING FRESH INDICATORS for {completed_timeframe}")

        indicators_calculated = 0
        for indicator_def in self.config.indicators:
            indicator_timeframe = getattr(indicator_def, 'time_increment', '1m')
            print(
                f"🔧 Checking indicator: {indicator_def.name} ({indicator_timeframe}) vs completed: {completed_timeframe}")

            # Only calculate if this indicator matches the completed timeframe
            if indicator_timeframe == completed_timeframe:
                print(f"🔧 ✅ TIMEFRAME MATCH! Calculating {indicator_def.name}")

                # Get the appropriate candle data for this timeframe
                if indicator_timeframe in all_candle_data:
                    candle_data = all_candle_data[indicator_timeframe]
                    print(f"🔧 Using {len(candle_data)} {indicator_timeframe} candles for {indicator_def.name}")

                    # Debug: Show recent price data
                    if len(candle_data) >= 5:
                        recent_closes = [c.close for c in candle_data[-5:]]
                        recent_timestamps = [c.timestamp.strftime("%H:%M") for c in candle_data[-5:]]
                        print(f"🔧 Recent 5 closes: {recent_closes}")
                        print(f"🔧 Recent 5 times: {recent_timestamps}")

                    if len(candle_data) >= 20:  # Minimum data required
                        try:
                            # Calculate the indicator
                            print(f"🔧 Calling indicator function: {indicator_def.function}")
                            print(f"🔧 Parameters: {indicator_def.parameters}")

                            result = self._calculate_single_indicator(candle_data, indicator_def)
                            print(
                                f"🔧 Raw result type: {type(result)}, length: {len(result) if hasattr(result, '__len__') else 'N/A'}")

                            if result is not None and isinstance(result, np.ndarray) and len(result) > 0:
                                # Debug: Show recent results
                                recent_results = result[-10:] if len(result) > 10 else result
                                print(f"🔧 Recent indicator values: {recent_results}")

                                current_value = float(result[-1])
                                print(f"🔧 Current raw value: {current_value}")

                                # Look for triggers in the last few periods
                                lookback_periods = min(5, len(result))  # Look back 5 periods
                                recent_values = result[-lookback_periods:]
                                print(f"🔧 Checking last {lookback_periods} values for triggers: {recent_values}")

                                # Check if ANY recent value had a trigger
                                trigger_indices = np.where(recent_values > 0)[0]
                                has_recent_trigger = len(trigger_indices) > 0

                                print(f"🔧 Trigger indices: {trigger_indices}, has_recent_trigger: {has_recent_trigger}")

                                if has_recent_trigger:
                                    # TRIGGER FOUND! Set to 1.0 and reset timestamp
                                    stored_value = 1.0
                                    timestamp = datetime.now()  # Fresh timestamp for new trigger
                                    print(f"🔧 ⚡ RECENT TRIGGER DETECTED! {indicator_def.name} = 1.0")
                                    print(f"🔧 ⚡ Trigger was {len(recent_values) - trigger_indices[-1] - 1} periods ago")
                                else:
                                    # No recent trigger, keep existing value and timestamp for decay
                                    if indicator_def.name in self.stored_values:
                                        # Keep existing value and timestamp to allow proper decay
                                        stored_value = self.stored_values[indicator_def.name]['value']
                                        timestamp = self.stored_values[indicator_def.name]['timestamp']
                                        print(
                                            f"🔧 📉 No recent trigger, keeping existing: {indicator_def.name} = {stored_value}")
                                    else:
                                        # No existing value, set to 0
                                        stored_value = 0.0
                                        timestamp = datetime.now()
                                        print(f"🔧 💤 No trigger, no history: {indicator_def.name} = 0.0")

                                # Store the calculation
                                self.stored_values[indicator_def.name] = {
                                    'value': stored_value,
                                    'raw_value': current_value,
                                    'timestamp': timestamp,
                                    'timeframe': indicator_timeframe
                                }

                                print(f"🔧 ✅ STORED: {indicator_def.name} = {stored_value} (raw: {current_value})")
                                indicators_calculated += 1

                            else:
                                print(f"🔧 ❌ Invalid result for {indicator_def.name}: {result}")

                        except Exception as e:
                            print(f"🔧 ❌ ERROR calculating {indicator_def.name}: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print(f"🔧 ❌ Not enough data for {indicator_def.name}: {len(candle_data)} < 20")
                else:
                    print(f"🔧 ❌ No {indicator_timeframe} data available for {indicator_def.name}")
            else:
                print(
                    f"🔧 ⏭️  SKIP: {indicator_def.name} timeframe mismatch ({indicator_timeframe} != {completed_timeframe})")

        print(f"🔧 FRESH CALCULATION COMPLETE: {indicators_calculated} indicators updated")

    def _apply_decay(self, original_value: float, minutes_elapsed: float, timeframe_minutes: int) -> float:
        """
        CLEAN decay with proper rounding to avoid weird decimals
        """
        if original_value <= 0.0:
            return 0.0

        # Use step-based decay instead of continuous decay
        # This ensures clean values like 1.0, 0.9, 0.8, 0.7, etc.

        # How many decay steps have occurred?
        # For 1m indicators: every 1 minute = 1 step
        # For 5m indicators: every 5 minutes = 1 step
        decay_steps = int(minutes_elapsed / timeframe_minutes)

        # Each step reduces by 0.1
        decayed_value = original_value - (decay_steps * 0.1)

        # Don't go below 0
        decayed_value = max(0.0, decayed_value)

        # Round to 1 decimal place to avoid floating point errors
        decayed_value = round(decayed_value, 1)

        print(
            f"🔧 CLEAN DECAY: {original_value} - ({decay_steps} steps * 0.1) = {decayed_value} (elapsed: {minutes_elapsed:.1f}min)")

        return decayed_value

    def _get_current_decayed_values(self) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Get current indicator values with CLEAN integer-based decay
        """
        print(f"🔧 APPLYING DECAY to {len(self.stored_values)} stored values")

        current_indicators = {}
        current_raw = {}
        now = datetime.now()

        for indicator_name, stored_data in self.stored_values.items():
            # Calculate time since last update
            last_update = stored_data['timestamp']
            time_elapsed = now - last_update
            minutes_elapsed = time_elapsed.total_seconds() / 60

            # Get timeframe for this indicator
            timeframe = stored_data['timeframe']
            timeframe_minutes = self._get_timeframe_minutes(timeframe)

            # Apply CLEAN decay
            original_value = stored_data['value']
            decayed_value = self._apply_decay(original_value, minutes_elapsed, timeframe_minutes)

            current_indicators[indicator_name] = decayed_value
            current_raw[indicator_name] = stored_data['raw_value']

            # Debug output
            print(
                f"🔧 DECAY RESULT: {indicator_name} = {decayed_value:.1f} (was {original_value}, {minutes_elapsed:.1f}min ago)")

        return current_indicators, current_raw

    def _get_timeframe_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes"""
        timeframe_map = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60
        }
        return timeframe_map.get(timeframe, 1)

    def _calculate_single_indicator(self, tick_history: List[TickData], indicator_def) -> np.ndarray:
        """Calculate a single indicator with debug output"""
        try:
            print(f"🔧 CALC: Calculating {indicator_def.function} with {len(tick_history)} candles")

            # Log some data characteristics
            if tick_history:
                closes = [t.close for t in tick_history]
                print(f"🔧 CALC: Price range: ${min(closes):.2f} - ${max(closes):.2f}")
                print(f"🔧 CALC: Recent closes: {closes[-5:]}")

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

            # Debug the result
            if isinstance(result, np.ndarray):
                trigger_count = np.sum(result > 0)
                max_value = np.max(result) if len(result) > 0 else 0
                print(f"🔧 CALC: Result - {len(result)} values, {trigger_count} triggers, max: {max_value}")

                # Show where triggers occurred
                if trigger_count > 0:
                    trigger_indices = np.where(result > 0)[0]
                    print(f"🔧 CALC: Triggers at indices: {trigger_indices[-5:]}")  # Last 5 triggers

            return result

        except Exception as e:
            logger.error(f"Error calculating {indicator_def.function}: {e}")
            print(f"🔧 CALC ERROR: {indicator_def.function} failed: {e}")
            import traceback
            traceback.print_exc()
            return np.array([0.0])

    def _calculate_bar_scores(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """Calculate weighted bar scores with debug output"""
        print(f"🔧 BAR CALC: Calculating bar scores from {len(indicators)} indicators")
        print(f"🔧 BAR CALC: Available indicators: {list(indicators.keys())}")

        bar_scores = {}
        if hasattr(self.config, 'bars') and self.config.bars:
            print(f"🔧 BAR CALC: Processing {len(self.config.bars)} bars")

            for bar_name, bar_weights in self.config.bars.items():
                print(f"🔧 BAR CALC: Processing bar '{bar_name}' with weights: {bar_weights}")

                weighted_sum = 0.0
                total_weight = 0.0
                used_indicators = []

                for indicator_name, weight in bar_weights.items():
                    if indicator_name in indicators:
                        indicator_value = indicators[indicator_name]
                        weighted_sum += indicator_value * weight
                        total_weight += weight
                        used_indicators.append(f"{indicator_name}={indicator_value:.2f}*{weight}")
                        print(
                            f"🔧 BAR CALC: - {indicator_name}: {indicator_value:.3f} * {weight} = {indicator_value * weight:.3f}")
                    else:
                        print(f"🔧 BAR CALC: - {indicator_name}: NOT FOUND")

                final_score = weighted_sum / total_weight if total_weight > 0 else 0.0
                bar_scores[bar_name] = final_score

                print(f"🔧 BAR CALC: {bar_name} = {weighted_sum:.3f} / {total_weight:.3f} = {final_score:.3f}")
                print(f"🔧 BAR CALC: Used: {used_indicators}")
        else:
            print("🔧 BAR CALC: No bars configuration found")

        return bar_scores