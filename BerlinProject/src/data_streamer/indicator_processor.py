
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
        for indicator_def in self.config.indicators:
            indicator_timeframe = getattr(indicator_def, 'time_increment', '1m')

            # Only calculate if this indicator matches the completed timeframe
            if indicator_timeframe == completed_timeframe:

                # Get the appropriate candle data for this timeframe
                if indicator_timeframe in all_candle_data:
                    candle_data = all_candle_data[indicator_timeframe]

                    if len(candle_data) >= 20:  # Minimum data required
                        try:
                            # Calculate the indicator
                            result = self._calculate_single_indicator(candle_data, indicator_def)

                            if result is not None and isinstance(result, np.ndarray) and len(result) > 0:
                                raw_value = float(result[-1])

                                # Store the fresh calculation
                                self.stored_values[indicator_def.name] = {
                                    'value': raw_value,
                                    'raw_value': raw_value,
                                    'timestamp': datetime.now(),
                                    'timeframe': indicator_timeframe
                                }

                                logger.debug(f"Fresh calculation: {indicator_def.name} = {raw_value}")

                        except Exception as e:
                            logger.error(f"Error calculating {indicator_def.name}: {e}")

    def _get_current_decayed_values(self) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Get current indicator values with time-based decay applied
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

            # Apply decay
            original_value = stored_data['value']
            decayed_value = self._apply_decay(original_value, minutes_elapsed, timeframe_minutes)

            current_indicators[indicator_name] = decayed_value
            current_raw[indicator_name] = stored_data['raw_value']

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

    def _apply_decay(self, original_value: float, minutes_elapsed: float, timeframe_minutes: int) -> float:
        """
        Apply time-based decay to indicator values

        Decay model:
        - Value decreases by 0.1 per timeframe period
        - Dies completely after 10 periods
        """
        if original_value == 0.0:
            return 0.0

        # Calculate periods elapsed
        periods_elapsed = minutes_elapsed / timeframe_minutes

        # Die after 10 periods
        if periods_elapsed >= 10:
            return 0.0

        # Linear decay: 0.1 per period
        decay_factor = 1.0 - (periods_elapsed * 0.1)
        decay_factor = max(0.0, decay_factor)

        return original_value * decay_factor

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