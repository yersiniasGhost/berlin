
"""
Simple indicator processor that manages timeframe-specific indicators with decay
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

    def calculate_indicators(self, all_candle_data: Dict[str, List[TickData]],
                             completed_timeframe: str = None) -> Tuple[
        Dict[str, float], Dict[str, float], Dict[str, float]]:
        """
        Calculate indicators using appropriate timeframe data

        Args:
            all_candle_data: {timeframe: [candles]} from all aggregators
            completed_timeframe: Which timeframe just completed (for fresh calculations)
        """
        current_indicators = {}
        current_raw = {}

        # Only recalculate indicators that match the completed timeframe
        if completed_timeframe:
            self._calculate_fresh_indicators(all_candle_data, completed_timeframe)

        # Apply decay to all stored indicators
        current_indicators, current_raw = self._get_current_decayed_values()

        # Calculate bar scores from current indicator values
        bar_scores = self._calculate_bar_scores(current_indicators)

        return current_indicators, current_raw, bar_scores

    def _calculate_fresh_indicators(self, all_candle_data: Dict[str, List[TickData]], completed_timeframe: str) -> None:
        """
        Calculate fresh values for indicators that match the completed timeframe
        """
        print(f"🔧 CALCULATING FRESH INDICATORS for {completed_timeframe}")  # DEBUG

        for indicator_def in self.config.indicators:
            indicator_timeframe = getattr(indicator_def, 'time_increment', '1m')
            print(
                f"🔧 Checking indicator: {indicator_def.name} ({indicator_timeframe}) vs completed: {completed_timeframe}")  # DEBUG

            # Only calculate if this indicator matches the completed timeframe
            if indicator_timeframe == completed_timeframe:
                print(f"🔧 ✅ TIMEFRAME MATCH! Calculating {indicator_def.name}")  # DEBUG

                # Get the appropriate candle data for this timeframe
                if indicator_timeframe in all_candle_data:
                    candle_data = all_candle_data[indicator_timeframe]
                    print(f"🔧 Using {len(candle_data)} {indicator_timeframe} candles for {indicator_def.name}")  # DEBUG

                    if len(candle_data) >= 20:  # Minimum data required
                        try:
                            # Calculate the indicator
                            result = self._calculate_single_indicator(candle_data, indicator_def)

                            if result is not None and isinstance(result, np.ndarray) and len(result) > 0:
                                # NEW LOGIC: Look for ANY trigger in the recent periods, not just current
                                current_value = float(result[-1])

                                # Look for triggers in the last few periods
                                lookback_periods = min(3, len(result))  # Look back 3 periods
                                recent_values = result[-lookback_periods:]

                                # Check if ANY recent value had a trigger
                                has_recent_trigger = np.any(recent_values > 0)

                                if has_recent_trigger:
                                    # TRIGGER FOUND! Set to 1.0 and reset timestamp
                                    stored_value = 1.0
                                    timestamp = datetime.now()  # Fresh timestamp for new trigger
                                    print(
                                        f"🔧 ⚡ RECENT TRIGGER! {indicator_def.name} = 1.0 (recent values: {recent_values})")  # DEBUG
                                else:
                                    # No recent trigger, keep existing value and timestamp for decay
                                    if indicator_def.name in self.stored_values:
                                        # Keep existing value and timestamp to allow proper decay
                                        stored_value = self.stored_values[indicator_def.name]['value']
                                        timestamp = self.stored_values[indicator_def.name]['timestamp']
                                        print(
                                            f"🔧 📉 No recent trigger, keeping: {indicator_def.name} = {stored_value}")  # DEBUG
                                    else:
                                        # No existing value, set to 0
                                        stored_value = 0.0
                                        timestamp = datetime.now()
                                        print(f"🔧 💤 No trigger, no history: {indicator_def.name} = 0.0")  # DEBUG

                                # Store the calculation
                                self.stored_values[indicator_def.name] = {
                                    'value': stored_value,
                                    'raw_value': current_value,
                                    'timestamp': timestamp,  # Use appropriate timestamp
                                    'timeframe': indicator_timeframe
                                }

                            else:
                                print(f"🔧 ❌ Invalid result for {indicator_def.name}: {result}")  # DEBUG

                        except Exception as e:
                            print(f"🔧 ❌ ERROR calculating {indicator_def.name}: {e}")  # DEBUG
                    else:
                        print(f"🔧 ❌ Not enough data for {indicator_def.name}: {len(candle_data)} < 20")  # DEBUG
                else:
                    print(f"🔧 ❌ No {indicator_timeframe} data available for {indicator_def.name}")  # DEBUG
            else:
                print(f"🔧 ⏭️  SKIP: {indicator_def.name} timeframe mismatch")  # DEBUG

    def _apply_decay(self, original_value: float, minutes_elapsed: float, timeframe_minutes: int) -> float:
        """
        CLEAN decay: 1.0 → 0.9 → 0.8 → 0.7 → ... → 0.0
        Uses INTEGER periods only
        """
        if original_value <= 0.0:
            return 0.0

        # How many COMPLETE periods have passed?
        periods_elapsed = int(minutes_elapsed // timeframe_minutes)  # INTEGER periods only!

        # Simple decay: subtract 0.1 per COMPLETE period
        decayed_value = original_value - (periods_elapsed * 0.1)

        # Don't go below 0
        decayed_value = max(0.0, decayed_value)

        return decayed_value

    def _get_current_decayed_values(self) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Get current indicator values with CLEAN integer-based decay
        """
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

            # Debug output - only show if value > 0
            if decayed_value > 0:
                complete_periods = int(minutes_elapsed // timeframe_minutes)
                print(f"🔧 DECAY: {indicator_name} = {decayed_value:.1f} (complete periods: {complete_periods})")

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
        """Calculate a single indicator"""
        try:
            if indicator_def.function == 'sma_crossover':
                return sma_crossover(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'macd_histogram_crossover':
                return macd_histogram_crossover(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'bol_bands_lower_band_bounce':
                return bol_bands_lower_band_bounce(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'support_level':
                return support_level(tick_history, indicator_def.parameters)
            elif indicator_def.function == 'resistance_level':
                return resistance_level(tick_history, indicator_def.parameters)
            else:
                logger.warning(f"Unknown indicator function: {indicator_def.function}")
                return np.array([0.0])
        except Exception as e:
            logger.error(f"Error calculating {indicator_def.function}: {e}")
            return np.array([0.0])

    def _calculate_bar_scores(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """Calculate weighted bar scores"""
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