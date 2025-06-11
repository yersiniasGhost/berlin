"""
Simplified IndicatorProcessor with proper typing and clean bar score calculation
"""

import logging
from typing import Tuple, Dict, List
from datetime import datetime
import numpy as np

from features.indicators2 import support_level, resistance_level
from models.monitor_configuration import MonitorConfiguration
from features.indicators import *
from environments.tick_data import TickData

logger = logging.getLogger('IndicatorProcessor')


class IndicatorProcessor:
    """
    Processes indicators for completed candles with time-based decay
    """

    def __init__(self, configuration: MonitorConfiguration) -> None:
        self.config: MonitorConfiguration = configuration
        self.stored_values: Dict[str, Dict[str, any]] = {}

        logger.info(f"IndicatorProcessor initialized with {len(self.config.indicators)} indicators")

    def calculate_indicators(self,
                           all_candle_data: Dict[str, List[TickData]],
                           completed_timeframe: str = None) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
        """
        Calculate indicators using appropriate timeframe data

        Args:
            all_candle_data: Dictionary mapping timeframe to candle list
            completed_timeframe: Which timeframe just completed

        Returns:
            Tuple of (indicators, raw_indicators, bar_scores)
        """
        if completed_timeframe:
            self._calculate_fresh_indicators(all_candle_data, completed_timeframe)

        current_indicators, current_raw = self._get_current_decayed_values()
        bar_scores = self._calculate_bar_scores(current_indicators)

        return current_indicators, current_raw, bar_scores

    def _calculate_fresh_indicators(self,
                                  all_candle_data: Dict[str, List[TickData]],
                                  completed_timeframe: str) -> None:
        """
        Calculate fresh values for indicators that match the completed timeframe
        """
        for indicator_def in self.config.indicators:
            indicator_timeframe: str = getattr(indicator_def, 'time_increment', '1m')

            if indicator_timeframe != completed_timeframe:
                continue

            if indicator_timeframe not in all_candle_data:
                continue

            candle_data: List[TickData] = all_candle_data[indicator_timeframe]

            if len(candle_data) < 20:
                continue

            try:
                result: np.ndarray = self._calculate_single_indicator(candle_data, indicator_def)

                if result is not None and isinstance(result, np.ndarray) and len(result) > 0:
                    current_value: float = float(result[-1])

                    lookback_periods: int = min(5, len(result))
                    recent_values: np.ndarray = result[-lookback_periods:]

                    trigger_indices: np.ndarray = np.where(recent_values > 0)[0]
                    has_recent_trigger: bool = len(trigger_indices) > 0

                    if has_recent_trigger:
                        stored_value: float = 1.0
                        timestamp: datetime = datetime.now()
                    else:
                        if indicator_def.name in self.stored_values:
                            stored_value = self.stored_values[indicator_def.name]['value']
                            timestamp = self.stored_values[indicator_def.name]['timestamp']
                        else:
                            stored_value = 0.0
                            timestamp = datetime.now()

                    self.stored_values[indicator_def.name] = {
                        'value': stored_value,
                        'raw_value': current_value,
                        'timestamp': timestamp,
                        'timeframe': indicator_timeframe
                    }

            except Exception as e:
                logger.error(f"Error calculating {indicator_def.name}: {e}")

    def _calculate_single_indicator(self,
                                  tick_history: List[TickData],
                                  indicator_def) -> np.ndarray:
        """
        Calculate a single indicator
        """
        try:
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

            return result

        except Exception as e:
            logger.error(f"Error calculating {indicator_def.function}: {e}")
            return np.array([0.0])

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
        if original_value <= 0.0:
            return 0.0

        # Continuous decay instead of step-based
        decay_rate = 0.1 / timeframe_minutes  # 0.1 per timeframe period
        decayed_value = original_value - (minutes_elapsed * decay_rate)
        decayed_value = max(0.0, decayed_value)

        return round(decayed_value, 1)

    def _get_timeframe_minutes(self, timeframe: str) -> int:
        """
        Convert timeframe string to minutes
        """
        timeframe_map: Dict[str, int] = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60
        }
        return timeframe_map.get(timeframe, 1)

    def _calculate_bar_scores(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate weighted bar scores from indicator values
        """
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