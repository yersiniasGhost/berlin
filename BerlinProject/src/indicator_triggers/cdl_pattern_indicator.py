"""Candlestick Pattern Recognition using TA-Lib patterns."""

from typing import List, Tuple, Dict, Any
import numpy as np
import talib as ta

from models.tick_data import TickData
from indicator_triggers.indicator_base import BaseIndicator, ParameterSpec, ParameterType, IndicatorRegistry


class CDLPatternIndicator(BaseIndicator):
    """Candlestick Pattern Recognition using TA-Lib patterns."""

    @classmethod
    def name(cls) -> str:
        return "cdl_pattern"

    @property
    def display_name(self) -> str:
        return "Candlestick Pattern"

    @property
    def description(self) -> str:
        return "Detects candlestick patterns from a list of TA-Lib patterns. Returns 1 when any pattern is triggered."

    @classmethod
    def get_parameter_specs(cls) -> List[ParameterSpec]:
        return [
            ParameterSpec(
                name="patterns",
                display_name="Pattern List",
                parameter_type=ParameterType.LIST,
                default_value=[],
                description="List of TA-Lib candlestick pattern names to detect",
                ui_group="Pattern Settings"
            ),
            ParameterSpec(
                name="trend",
                display_name="Trend Direction",
                parameter_type=ParameterType.CHOICE,
                default_value="bullish",
                choices=["bullish", "bearish"],
                description="Direction of trend to detect (bullish or bearish patterns)",
                ui_group="Signal Settings"
            ),
            ParameterSpec(
                name="lookback",
                display_name="Lookback Period",
                parameter_type=ParameterType.INTEGER,
                default_value=2,
                min_value=1,
                max_value=20,
                step=1,
                description="Number of candles for trigger decay (1.0 → 0.0)",
                ui_group="Signal Settings"
            )
        ]

    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Calculate candlestick pattern signals.

        Returns 1.0 when any pattern in the list is detected, 0.0 otherwise.
        The trend parameter controls which pattern types to detect (bullish or bearish).
        Bar weights determine how the signal affects the final bar score.
        """
        patterns = self.get_parameter("patterns")

        # Ensure patterns is a list (handle if it comes as string or other type)
        if isinstance(patterns, str):
            # If it's a comma-separated string, split it
            patterns = [p.strip() for p in patterns.split(',')]
        elif not isinstance(patterns, list):
            patterns = []

        trend = self.get_parameter("trend")

        if len(tick_data) < 5:  # Most patterns need at least 5 candles
            return np.array([0.0] * len(tick_data)), {}

        # Extract OHLC data
        opens = np.array([tick.open for tick in tick_data])
        highs = np.array([tick.high for tick in tick_data])
        lows = np.array([tick.low for tick in tick_data])
        closes = np.array([tick.close for tick in tick_data])

        # Initialize result array
        result = np.zeros(len(tick_data))

        # Check each pattern in the list
        for pattern_name in patterns:
            pattern_name = pattern_name.upper().strip()

            # Get the TA-Lib function for this pattern
            if hasattr(ta, pattern_name):
                pattern_func = getattr(ta, pattern_name)
                try:
                    pattern_values = pattern_func(opens, highs, lows, closes)

                    # Pattern detected: TA-Lib returns non-zero values
                    # Positive values = bullish, negative = bearish
                    # Always return positive 1.0 when pattern detected
                    if trend == "bullish":
                        # Detect bullish patterns (positive TA-Lib values)
                        pattern_detected = (pattern_values > 0).astype(float)
                        result = np.maximum(result, pattern_detected)
                    else:  # bearish
                        # Detect bearish patterns (negative TA-Lib values)
                        # Convert to positive 1.0 for consistent bar weighting
                        pattern_detected = (pattern_values < 0).astype(float)
                        if len(pattern_detected) > 0 and pattern_detected[-1] == 1.0:
                            print(f"[CDL PATTERN DETECTED] {pattern_name} (bearish) on latest candle!")
                        result = np.maximum(result, pattern_detected)

                except Exception as e:
                    # If pattern function fails, skip it
                    continue

        # Return raw pattern detection (always positive: 1 when detected, 0 otherwise)
        # Bar weights control directional impact on bar scores
        components = {
            "pattern_raw": result
        }

        return result, components


IndicatorRegistry().register(CDLPatternIndicator)
