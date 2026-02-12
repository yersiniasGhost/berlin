"""Relative Strength Index (RSI) indicator with signal generation."""

import math
from typing import List, Tuple, Dict, Any
import numpy as np
import talib as ta

from models.tick_data import TickData
from indicator_triggers.indicator_base import BaseIndicator, ParameterSpec, ParameterType, IndicatorRegistry


class RSIIndicator(BaseIndicator):
    """Relative Strength Index (RSI) indicator with signal generation."""

    @classmethod
    def name(cls) -> str:
        return "RSI"

    @property
    def display_name(self) -> str:
        return "RSI (Relative Strength Index)"

    @property
    def description(self) -> str:
        return "Calculates RSI and generates signals when crossing oversold/overbought thresholds"

    @classmethod
    def get_parameter_specs(cls) -> List[ParameterSpec]:
        return [
            ParameterSpec(
                name="period",
                display_name="RSI Period",
                parameter_type=ParameterType.INTEGER,
                default_value=14,
                min_value=2,
                max_value=50,
                step=1,
                description="Number of periods for RSI calculation",
                ui_group="RSI Settings"
            ),
            ParameterSpec(
                name="oversold_threshold",
                display_name="Oversold Threshold",
                parameter_type=ParameterType.FLOAT,
                default_value=30.0,
                min_value=0.0,
                max_value=50.0,
                step=1.0,
                description="RSI value below which triggers bullish signal",
                ui_group="Signal Settings"
            ),
            ParameterSpec(
                name="overbought_threshold",
                display_name="Overbought Threshold",
                parameter_type=ParameterType.FLOAT,
                default_value=70.0,
                min_value=50.0,
                max_value=100.0,
                step=1.0,
                description="RSI value above which triggers bearish signal",
                ui_group="Signal Settings"
            ),
            ParameterSpec(
                name="trend",
                display_name="Trend Direction",
                parameter_type=ParameterType.CHOICE,
                default_value="bullish",
                choices=["bullish", "bearish"],
                description="Direction of trend to detect (bullish=oversold, bearish=overbought)",
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

    @classmethod
    def get_layout_type(cls) -> str:
        """RSI uses stacked layout - candlesticks on top, RSI oscillator below."""
        return "stacked"

    @classmethod
    def get_chart_config(cls) -> Dict[str, Any]:
        """Return RSI-specific chart configuration for visualization."""
        return {
            "chart_type": "rsi",
            "title_suffix": "RSI Oscillator",
            "components": [
                {"key_suffix": "rsi", "name": "RSI", "color": "#2962FF", "line_width": 2},
            ],
            "y_axis": {"min": 0, "max": 100, "title": "RSI"},
            "reference_lines": [
                {"value": 30, "color": "#26A69A", "dash_style": "Dash", "label": "Oversold (30)"},
                {"value": 70, "color": "#EF5350", "dash_style": "Dash", "label": "Overbought (70)"},
                {"value": 50, "color": "#9E9E9E", "dash_style": "Dot", "label": "Neutral (50)"},
            ]
        }

    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Calculate RSI values and generate signals.

        Returns:
            - Signal array: 1.0 when threshold is crossed, 0.0 otherwise
            - Component data: RSI values and threshold levels for visualization
        """
        period = self.get_parameter("period")
        oversold_threshold = self.get_parameter("oversold_threshold")
        overbought_threshold = self.get_parameter("overbought_threshold")
        trend = self.get_parameter("trend")

        if len(tick_data) < period:
            return np.array([math.nan] * len(tick_data)), {}

        # Calculate RSI
        closes = np.array([tick.close for tick in tick_data])
        rsi = ta.RSI(closes, timeperiod=period)

        # Create mask for valid (non-NaN) RSI values
        valid_mask = ~np.isnan(rsi)

        # Initialize signal array
        signals = np.zeros(len(tick_data))

        if trend == "bullish":
            # Bullish signal: RSI crosses above oversold threshold
            below_threshold = rsi < oversold_threshold
            # Detect when RSI crosses from below to above the oversold threshold
            # Only trigger when BOTH current and previous are valid
            crossover = np.logical_and(~below_threshold[1:], below_threshold[:-1])
            both_valid = np.logical_and(valid_mask[1:], valid_mask[:-1])
            signals[1:] = np.logical_and(crossover, both_valid)
        else:  # bearish
            # Bearish signal: RSI crosses below overbought threshold
            above_threshold = rsi > overbought_threshold
            # Detect when RSI crosses from above to below the overbought threshold
            # Only trigger when BOTH current and previous are valid
            crossover = np.logical_and(~above_threshold[1:], above_threshold[:-1])
            both_valid = np.logical_and(valid_mask[1:], valid_mask[:-1])
            signals[1:] = np.logical_and(crossover, both_valid)

        # Component data for visualization
        component_data = {
            f"{self.name()}_rsi": rsi,
            f"{self.name()}_oversold": np.full(len(tick_data), oversold_threshold),
            f"{self.name()}_overbought": np.full(len(tick_data), overbought_threshold)
        }

        return signals, component_data


IndicatorRegistry().register(RSIIndicator)
