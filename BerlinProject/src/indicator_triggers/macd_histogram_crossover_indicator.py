"""MACD Histogram Crossover signal indicator."""

import math
from typing import List, Tuple, Dict, Any
import numpy as np
import talib as ta

from models.tick_data import TickData
from indicator_triggers.indicator_base import BaseIndicator, ParameterSpec, ParameterType, IndicatorRegistry


class MACDHistogramCrossoverIndicator(BaseIndicator):
    """MACD Histogram Crossover signal indicator."""

    @classmethod
    def name(cls) -> str:
        return "macd_histogram_crossover"

    @property
    def display_name(self) -> str:
        return "MACD Histogram Crossover"

    @property
    def description(self) -> str:
        return "Generates signals when MACD histogram crosses threshold levels"

    @classmethod
    def get_parameter_specs(cls) -> List[ParameterSpec]:
        return [
            ParameterSpec(
                name="fast",
                display_name="Fast EMA Period",
                parameter_type=ParameterType.INTEGER,
                default_value=12,
                min_value=2,
                max_value=15,
                step=1,
                description="Fast EMA period for MACD calculation",
                ui_group="MACD Settings"
            ),
            ParameterSpec(
                name="slow",
                display_name="Slow EMA Period",
                parameter_type=ParameterType.INTEGER,
                default_value=26,
                min_value=12,
                max_value=30,
                step=1,
                description="Slow EMA period for MACD calculation",
                ui_group="MACD Settings"
            ),
            ParameterSpec(
                name="signal",
                display_name="Signal Period",
                parameter_type=ParameterType.INTEGER,
                default_value=9,
                min_value=2,
                max_value=30,
                step=1,
                description="Signal line EMA period",
                ui_group="MACD Settings"
            ),
            ParameterSpec(
                name="histogram_threshold",
                display_name="Histogram Threshold",
                parameter_type=ParameterType.FLOAT,
                default_value=0.001,
                min_value=0.0,
                max_value=0.5,
                step=0.0001,
                description="Threshold for histogram crossover detection",
                ui_group="Signal Settings"
            ),
            ParameterSpec(
                name="trend",
                display_name="Trend Direction",
                parameter_type=ParameterType.CHOICE,
                default_value="bullish",
                choices=["bullish", "bearish"],
                description="Direction of trend to detect",
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
        """MACD uses stacked layout - candlesticks on top, MACD lines below."""
        return "stacked"

    @classmethod
    def get_chart_config(cls) -> Dict[str, Any]:
        """Return MACD-specific chart configuration for visualization."""
        return {
            "chart_type": "macd",
            "title_suffix": "MACD Analysis",
            "components": [
                {"key_suffix": "macd", "name": "MACD Line", "color": "#2962FF", "line_width": 2},
                {"key_suffix": "signal", "name": "Signal Line", "color": "#FF6D00", "line_width": 2},
                {"key_suffix": "histogram", "name": "Histogram", "color": "#00897B", "type": "column"},
            ],
            "y_axis": {"title": "Value"},
            "reference_lines": [
                {"value": 0, "color": "#9E9E9E", "dash_style": "Dash", "label": "Zero Line"},
            ]
        }

    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, Any]]:
        fast = self.get_parameter("fast")
        slow = self.get_parameter("slow")
        signal = self.get_parameter("signal")
        histogram_threshold = self.get_parameter("histogram_threshold")
        trend = self.get_parameter("trend")

        if len(tick_data) < slow + signal:
            return np.array([math.nan] * len(tick_data)), {}

        closes = np.array([tick.close for tick in tick_data], dtype=np.float64)
        macd, signal_line, histogram = ta.MACD(closes, fastperiod=fast, slowperiod=slow, signalperiod=signal)

        component_data = {
            f"{self.name()}_macd": macd.tolist(),
            f"{self.name()}_signal": signal_line.tolist(),
            f"{self.name()}_histogram": histogram.tolist()
        }
        result = np.zeros(len(tick_data))

        # Create mask for valid (non-NaN) histogram values
        # NaN comparisons return False, which causes false triggers at NaN→valid transitions
        valid_mask = ~np.isnan(histogram)

        if trend == 'bullish':
            above_threshold = histogram > histogram_threshold
            # Only trigger when BOTH current and previous are valid AND crossover occurs
            crossover = np.logical_and(above_threshold[1:], ~above_threshold[:-1])
            both_valid = np.logical_and(valid_mask[1:], valid_mask[:-1])
            result[1:] = np.logical_and(crossover, both_valid)
        else:  # bearish
            below_threshold = histogram < -histogram_threshold
            # Only trigger when BOTH current and previous are valid AND crossover occurs
            crossover = np.logical_and(below_threshold[1:], ~below_threshold[:-1])
            both_valid = np.logical_and(valid_mask[1:], valid_mask[:-1])
            result[1:] = np.logical_and(crossover, both_valid)

        return result, component_data


IndicatorRegistry().register(MACDHistogramCrossoverIndicator)
