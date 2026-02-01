"""
Trend indicators for trend-gated bar calculations.

These indicators provide trend direction and strength information that can be used
to gate signal indicators. When trend indicators are configured for a bar:
- Positive values indicate bullish trend (passes bull bar gates)
- Negative values indicate bearish trend (passes bear bar gates)
- Values near zero indicate no clear trend

Output range: -1.0 to +1.0 (direction-encoded strength)
"""

import math
from typing import List, Tuple, Dict, Any
import numpy as np
import talib as ta

from models.tick_data import TickData
from indicator_triggers.indicator_base import (
    BaseIndicator, ParameterSpec, ParameterType, IndicatorType, IndicatorRegistry
)
from typing import Any


class ADXTrendIndicator(BaseIndicator):
    """ADX-based trend strength and direction indicator.

    Uses the Average Directional Index (ADX) combined with +DI/-DI to determine
    both trend strength and direction:
    - ADX measures trend strength (0-100, higher = stronger trend)
    - +DI > -DI indicates bullish direction
    - -DI > +DI indicates bearish direction

    The direction_filter parameter allows filtering signals:
    - "Both": Output all trend signals (default behavior)
    - "Bull": Only output bullish trends (positive values), zero out bearish
    - "Bear": Only output bearish trends (negative values), zero out bullish

    Output:
    - Positive values (0.0 to 1.0): Bullish trend with strength
    - Negative values (-1.0 to 0.0): Bearish trend with strength
    - Values near 0: No clear trend (ADX below threshold or filtered out)
    """

    @classmethod
    def name(cls) -> str:
        return "adx_trend"

    @property
    def display_name(self) -> str:
        return "ADX Trend Strength"

    @property
    def description(self) -> str:
        return "ADX-based trend indicator combining direction (+DI/-DI) and strength (ADX value)"

    @classmethod
    def get_indicator_type(cls) -> IndicatorType:
        return IndicatorType.TREND

    @classmethod
    def get_layout_type(cls) -> str:
        return "stacked"  # ADX displayed in separate panel

    @classmethod
    def get_chart_config(cls) -> Dict[str, Any]:
        """Return ADX-specific chart configuration for visualization."""
        return {
            "chart_type": "adx",
            "title_suffix": "ADX Trend Analysis",
            "components": [
                {"key_suffix": "adx", "name": "ADX", "color": "#2962FF", "line_width": 2.5},
                {"key_suffix": "plus_di", "name": "+DI", "color": "#26A69A", "line_width": 1.5, "dash_style": "ShortDash"},
                {"key_suffix": "minus_di", "name": "-DI", "color": "#EF5350", "line_width": 1.5, "dash_style": "ShortDash"},
            ],
            "y_axis": {"min": 0, "max": 100, "title": "Value"},
            "reference_lines": [
                {"value": 20, "color": "#9E9E9E", "dash_style": "Dot", "label": "Weak Trend (20)"},
                {"value": 25, "color": "#FFA726", "dash_style": "Dash", "label": "Trend Threshold (25)"},
                {"value": 40, "color": "#66BB6A", "dash_style": "Dash", "label": "Strong Trend (40)"},
            ]
        }

    @classmethod
    def get_parameter_specs(cls) -> List[ParameterSpec]:
        return [
            ParameterSpec(
                name="period",
                display_name="ADX Period",
                parameter_type=ParameterType.INTEGER,
                default_value=14,
                min_value=5,
                max_value=50,
                step=1,
                description="Period for ADX and DI calculations",
                ui_group="ADX Settings"
            ),
            ParameterSpec(
                name="trend_threshold",
                display_name="Trend Threshold",
                parameter_type=ParameterType.FLOAT,
                default_value=25.0,
                min_value=10.0,
                max_value=50.0,
                step=1.0,
                description="ADX value above which market is considered trending",
                ui_group="ADX Settings"
            ),
            ParameterSpec(
                name="strong_trend_threshold",
                display_name="Strong Trend Threshold",
                parameter_type=ParameterType.FLOAT,
                default_value=40.0,
                min_value=25.0,
                max_value=70.0,
                step=1.0,
                description="ADX value for maximum trend strength output",
                ui_group="ADX Settings"
            ),
            ParameterSpec(
                name="direction_filter",
                display_name="Direction Filter",
                parameter_type=ParameterType.CHOICE,
                default_value="Both",
                choices=["Both", "Bull", "Bear"],
                description="Filter signals: Bull (positive only), Bear (negative only), Both (all signals)",
                ui_group="ADX Settings"
            ),
        ]

    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Calculate ADX trend values.

        Returns:
            - values: Array of trend values (range depends on direction_filter)
            - components: Dict with ADX, +DI, -DI values for visualization

        When direction_filter is set:
            - "Bull": Positive values (0 to +1) when bullish (+DI > -DI), 0 otherwise
            - "Bear": Negative values (-1 to 0) when bearish (-DI > +DI), 0 otherwise
            - "Both": Signed values (-1 to +1): positive=bullish, negative=bearish

        Note: The trend gate system expects negative values for bearish trends,
        which it then inverts for bear bars. So Bear filter keeps values negative.
        """
        period = self.get_parameter("period")
        trend_threshold = self.get_parameter("trend_threshold")
        strong_trend_threshold = self.get_parameter("strong_trend_threshold")
        direction_filter = self.get_parameter("direction_filter")

        n = len(tick_data)
        if n < period + 1:
            return np.zeros(n), {}

        # Extract OHLC data
        highs = np.array([tick.high for tick in tick_data], dtype=np.float64)
        lows = np.array([tick.low for tick in tick_data], dtype=np.float64)
        closes = np.array([tick.close for tick in tick_data], dtype=np.float64)

        # Calculate ADX and directional indicators
        adx = ta.ADX(highs, lows, closes, timeperiod=period)
        plus_di = ta.PLUS_DI(highs, lows, closes, timeperiod=period)
        minus_di = ta.MINUS_DI(highs, lows, closes, timeperiod=period)

        # Initialize result array
        result = np.zeros(n)

        # Create valid mask (non-NaN values)
        valid_mask = ~np.isnan(adx) & ~np.isnan(plus_di) & ~np.isnan(minus_di)

        # Calculate trend strength (normalized 0-1 based on thresholds)
        # Below trend_threshold: 0
        # Between trend_threshold and strong_trend_threshold: linear interpolation
        # Above strong_trend_threshold: 1.0
        trend_strength = np.zeros(n)
        threshold_range = strong_trend_threshold - trend_threshold

        for i in range(n):
            if valid_mask[i] and adx[i] >= trend_threshold:
                if adx[i] >= strong_trend_threshold:
                    trend_strength[i] = 1.0
                else:
                    # Linear interpolation between thresholds
                    trend_strength[i] = (adx[i] - trend_threshold) / threshold_range

        # Determine direction: +DI > -DI = bullish (+1), -DI > +DI = bearish (-1)
        direction = np.where(plus_di > minus_di, 1.0, -1.0)

        # Combine: strength * direction
        # Result: positive = bullish trend, negative = bearish trend
        result = trend_strength * direction

        # Set NaN positions to 0
        result[~valid_mask] = 0.0

        # Apply direction filter
        # Bull: only positive values (bullish trends), zero out bearish
        # Bear: only negative values (bearish trends), zero out bullish
        # Both: keep all values (positive=bullish, negative=bearish)
        #
        # Note: The trend gate expects negative values for bearish trends.
        # For bear bars, it inverts negative → positive gate. So Bear filter
        # must keep values negative (not convert to positive).
        if direction_filter == "Bull":
            result = np.where(result > 0, result, 0.0)
        elif direction_filter == "Bear":
            # Keep negative values for bearish trends (trend gate will invert for bear bars)
            result = np.where(result < 0, result, 0.0)
        # "Both" keeps all values unchanged (positive=bullish, negative=bearish)

        component_data = {
            f"{self.name()}_adx": adx,
            f"{self.name()}_plus_di": plus_di,
            f"{self.name()}_minus_di": minus_di,
            f"{self.name()}_strength": trend_strength,
            f"{self.name()}_direction": direction
        }

        return result, component_data


class EMASlopeTrendIndicator(BaseIndicator):
    """EMA slope-based trend indicator.

    Calculates the slope (rate of change) of an Exponential Moving Average to
    determine trend direction and strength:
    - Positive slope = bullish trend
    - Negative slope = bearish trend
    - Steeper slope = stronger trend

    The direction_filter parameter allows filtering signals:
    - "Both": Output all trend signals (default behavior)
    - "Bull": Only output bullish trends (positive values), zero out bearish
    - "Bear": Only output bearish trends (negative values), zero out bullish

    Output:
    - Positive values (0.0 to 1.0): Bullish trend with strength
    - Negative values (-1.0 to 0.0): Bearish trend with strength
    - Zero: No signal (filtered out or flat slope)

    Note: The trend gate system expects negative values for bearish trends,
    which it then inverts for bear bars. So Bear filter keeps values negative.
    """

    @classmethod
    def name(cls) -> str:
        return "ema_slope"

    @property
    def display_name(self) -> str:
        return "EMA Slope Trend"

    @property
    def description(self) -> str:
        return "Trend indicator based on EMA slope direction and steepness"

    @classmethod
    def get_indicator_type(cls) -> IndicatorType:
        return IndicatorType.TREND

    @classmethod
    def get_layout_type(cls) -> str:
        return "overlay"  # EMA displayed on price chart

    @classmethod
    def get_chart_config(cls) -> Dict[str, Any]:
        """Return EMA Slope chart configuration for visualization."""
        return {
            "chart_type": "ema_slope",
            "title_suffix": "EMA Slope Analysis",
            "components": [
                {"key_suffix": "ema", "name": "EMA", "color": "#2962FF", "line_width": 2},
                {"key_suffix": "normalized", "name": "Normalized Slope", "color": "#FF6D00", "line_width": 1.5, "y_axis": 1},
            ],
            "y_axis": {"title": "Price"},
            "reference_lines": []
        }

    @classmethod
    def get_parameter_specs(cls) -> List[ParameterSpec]:
        return [
            ParameterSpec(
                name="period",
                display_name="EMA Period",
                parameter_type=ParameterType.INTEGER,
                default_value=20,
                min_value=5,
                max_value=100,
                step=1,
                description="Period for EMA calculation",
                ui_group="EMA Settings"
            ),
            ParameterSpec(
                name="slope_period",
                display_name="Slope Lookback",
                parameter_type=ParameterType.INTEGER,
                default_value=5,
                min_value=2,
                max_value=20,
                step=1,
                description="Number of bars to calculate slope over",
                ui_group="Slope Settings"
            ),
            ParameterSpec(
                name="normalize_factor",
                display_name="Normalization Factor",
                parameter_type=ParameterType.FLOAT,
                default_value=0.005,
                min_value=0.001,
                max_value=0.05,
                step=0.001,
                description="Expected max slope as fraction of price (for normalization)",
                ui_group="Slope Settings"
            ),
            ParameterSpec(
                name="smoothing",
                display_name="Slope Smoothing",
                parameter_type=ParameterType.INTEGER,
                default_value=3,
                min_value=1,
                max_value=10,
                step=1,
                description="SMA period to smooth the slope values",
                ui_group="Slope Settings"
            ),
            ParameterSpec(
                name="direction_filter",
                display_name="Direction Filter",
                parameter_type=ParameterType.CHOICE,
                default_value="Both",
                choices=["Both", "Bull", "Bear"],
                description="Filter signals: Bull (positive only), Bear (negative only), Both (all signals)",
                ui_group="Slope Settings"
            ),
        ]

    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Calculate EMA slope trend values.

        Returns:
            - values: Array of trend values (range depends on direction_filter)
            - components: Dict with EMA and slope values for visualization

        When direction_filter is set:
            - "Bull": Positive values (0 to +1) when bullish (slope > 0), 0 otherwise
            - "Bear": Negative values (-1 to 0) when bearish (slope < 0), 0 otherwise
            - "Both": Signed values (-1 to +1): positive=bullish, negative=bearish

        Note: The trend gate system expects negative values for bearish trends,
        which it then inverts for bear bars. So Bear filter keeps values negative.
        """
        period = self.get_parameter("period")
        slope_period = self.get_parameter("slope_period")
        normalize_factor = self.get_parameter("normalize_factor")
        smoothing = self.get_parameter("smoothing")
        direction_filter = self.get_parameter("direction_filter")

        n = len(tick_data)
        min_required = period + slope_period + smoothing
        if n < min_required:
            return np.zeros(n), {}

        # Extract close prices
        closes = np.array([tick.close for tick in tick_data], dtype=np.float64)

        # Calculate EMA
        ema = ta.EMA(closes, timeperiod=period)

        # Calculate slope (rate of change over slope_period)
        slope = np.zeros(n)
        for i in range(slope_period, n):
            if not np.isnan(ema[i]) and not np.isnan(ema[i - slope_period]):
                # Slope = (EMA[now] - EMA[slope_period ago]) / slope_period
                slope[i] = (ema[i] - ema[i - slope_period]) / slope_period

        # Smooth the slope
        if smoothing > 1:
            smoothed_slope = ta.SMA(slope, timeperiod=smoothing)
        else:
            smoothed_slope = slope.copy()

        # Normalize slope relative to price level
        # normalize_factor represents expected max slope as fraction of price
        normalized = np.zeros(n)
        valid_mask = ~np.isnan(smoothed_slope) & ~np.isnan(closes) & (closes > 0)

        for i in range(n):
            if valid_mask[i]:
                # Normalize: slope / (price * normalize_factor)
                # This makes the output independent of price level
                max_expected_slope = closes[i] * normalize_factor
                if max_expected_slope > 0:
                    normalized[i] = smoothed_slope[i] / max_expected_slope

        # Clamp to [-1, 1]
        result = np.clip(normalized, -1.0, 1.0)

        # Apply direction filter
        # Bull: only positive values (bullish trends), zero out bearish
        # Bear: only negative values (bearish trends), zero out bullish
        # Both: keep signed values (positive=bullish, negative=bearish)
        #
        # Note: The trend gate expects negative values for bearish trends.
        # For bear bars, it inverts negative → positive gate. So Bear filter
        # must keep values negative (not convert to positive).
        if direction_filter == "Bull":
            # Keep positive values, zero out negative
            result = np.where(result > 0, result, 0.0)
        elif direction_filter == "Bear":
            # Keep negative values for bearish trends (trend gate will invert for bear bars)
            result = np.where(result < 0, result, 0.0)
        # "Both" keeps all values unchanged (positive=bullish, negative=bearish)

        component_data = {
            f"{self.name()}_ema": ema,
            f"{self.name()}_slope": slope,
            f"{self.name()}_smoothed_slope": smoothed_slope,
            f"{self.name()}_normalized": normalized  # Store pre-filter normalized for visualization
        }

        return result, component_data


class SuperTrendIndicator(BaseIndicator):
    """SuperTrend-based trend indicator.

    SuperTrend is a popular ATR-based trend following indicator:
    - Uses ATR to calculate dynamic support/resistance bands
    - Trend flips when price crosses the bands
    - Provides clear trend direction signals

    The direction_filter parameter allows filtering signals:
    - "Both": Output all trend signals (default behavior)
    - "Bull": Only output bullish trends (positive values), zero out bearish
    - "Bear": Only output bearish trends (negative values), zero out bullish

    Output:
    - Positive values (+1.0): Bullish trend
    - Negative values (-1.0): Bearish trend
    - Zero: No signal (filtered out or below threshold)

    Note: The trend gate system expects negative values for bearish trends,
    which it then inverts for bear bars. So Bear filter keeps values negative.
    """

    @classmethod
    def name(cls) -> str:
        return "supertrend"

    @property
    def display_name(self) -> str:
        return "SuperTrend"

    @property
    def description(self) -> str:
        return "ATR-based trend following indicator with dynamic support/resistance"

    @classmethod
    def get_indicator_type(cls) -> IndicatorType:
        return IndicatorType.TREND

    @classmethod
    def get_layout_type(cls) -> str:
        return "overlay"  # SuperTrend line on price chart

    @classmethod
    def get_chart_config(cls) -> Dict[str, Any]:
        """Return SuperTrend chart configuration for visualization."""
        return {
            "chart_type": "supertrend",
            "title_suffix": "SuperTrend Analysis",
            "components": [
                {"key_suffix": "line", "name": "SuperTrend", "color": "#2962FF", "line_width": 2},
                {"key_suffix": "upper", "name": "Upper Band", "color": "#EF5350", "line_width": 1, "dash_style": "Dot"},
                {"key_suffix": "lower", "name": "Lower Band", "color": "#26A69A", "line_width": 1, "dash_style": "Dot"},
            ],
            "y_axis": {"title": "Price"},
            "reference_lines": []
        }

    @classmethod
    def get_parameter_specs(cls) -> List[ParameterSpec]:
        return [
            ParameterSpec(
                name="atr_period",
                display_name="ATR Period",
                parameter_type=ParameterType.INTEGER,
                default_value=10,
                min_value=5,
                max_value=50,
                step=1,
                description="Period for ATR calculation",
                ui_group="SuperTrend Settings"
            ),
            ParameterSpec(
                name="multiplier",
                display_name="ATR Multiplier",
                parameter_type=ParameterType.FLOAT,
                default_value=3.0,
                min_value=1.0,
                max_value=6.0,
                step=0.1,
                description="Multiplier for ATR to set band distance",
                ui_group="SuperTrend Settings"
            ),
            ParameterSpec(
                name="direction_filter",
                display_name="Direction Filter",
                parameter_type=ParameterType.CHOICE,
                default_value="Both",
                choices=["Both", "Bull", "Bear"],
                description="Filter signals: Bull (positive only), Bear (negative only), Both (all signals)",
                ui_group="SuperTrend Settings"
            ),
        ]

    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Calculate SuperTrend trend values.

        Returns:
            - values: Array of trend values (range depends on direction_filter)
            - components: Dict with SuperTrend line and bands for visualization

        When direction_filter is set:
            - "Bull": Positive value (+1) when bullish, 0 otherwise
            - "Bear": Negative value (-1) when bearish, 0 otherwise
            - "Both": Signed values (+1 bullish, -1 bearish)

        Note: The trend gate system expects negative values for bearish trends,
        which it then inverts for bear bars. So Bear filter keeps values negative.
        """
        atr_period = self.get_parameter("atr_period")
        multiplier = self.get_parameter("multiplier")
        direction_filter = self.get_parameter("direction_filter")

        n = len(tick_data)
        if n < atr_period + 1:
            return np.zeros(n), {}

        # Extract OHLC data
        highs = np.array([tick.high for tick in tick_data], dtype=np.float64)
        lows = np.array([tick.low for tick in tick_data], dtype=np.float64)
        closes = np.array([tick.close for tick in tick_data], dtype=np.float64)

        # Calculate ATR
        atr = ta.ATR(highs, lows, closes, timeperiod=atr_period)

        # Calculate basic bands
        hl2 = (highs + lows) / 2  # Median price
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)

        # Initialize SuperTrend calculation arrays
        supertrend = np.zeros(n)
        direction = np.zeros(n)  # 1 = bullish, -1 = bearish

        # Final upper and lower bands (with trailing logic)
        final_upper = np.zeros(n)
        final_lower = np.zeros(n)

        # Start calculation after ATR warmup
        start_idx = atr_period
        if np.isnan(atr[start_idx]):
            start_idx += 1

        # Initialize first valid values
        final_upper[start_idx] = upper_band[start_idx]
        final_lower[start_idx] = lower_band[start_idx]

        # Initial direction based on close vs bands
        if closes[start_idx] > final_upper[start_idx]:
            direction[start_idx] = 1
            supertrend[start_idx] = final_lower[start_idx]
        else:
            direction[start_idx] = -1
            supertrend[start_idx] = final_upper[start_idx]

        # Calculate SuperTrend for remaining bars
        for i in range(start_idx + 1, n):
            if np.isnan(atr[i]):
                direction[i] = direction[i - 1]
                supertrend[i] = supertrend[i - 1]
                final_upper[i] = final_upper[i - 1]
                final_lower[i] = final_lower[i - 1]
                continue

            # Update final bands (trailing logic)
            # Lower band only moves up, never down
            if lower_band[i] > final_lower[i - 1] or closes[i - 1] < final_lower[i - 1]:
                final_lower[i] = lower_band[i]
            else:
                final_lower[i] = final_lower[i - 1]

            # Upper band only moves down, never up
            if upper_band[i] < final_upper[i - 1] or closes[i - 1] > final_upper[i - 1]:
                final_upper[i] = upper_band[i]
            else:
                final_upper[i] = final_upper[i - 1]

            # Determine trend direction
            if direction[i - 1] == 1:  # Was bullish
                if closes[i] < final_lower[i]:
                    direction[i] = -1  # Flip to bearish
                    supertrend[i] = final_upper[i]
                else:
                    direction[i] = 1  # Stay bullish
                    supertrend[i] = final_lower[i]
            else:  # Was bearish
                if closes[i] > final_upper[i]:
                    direction[i] = 1  # Flip to bullish
                    supertrend[i] = final_lower[i]
                else:
                    direction[i] = -1  # Stay bearish
                    supertrend[i] = final_upper[i]

        # Result is the direction (+1 or -1)
        result = direction.copy()

        # Apply direction filter
        # Bull: only positive values (bullish trends), zero out bearish
        # Bear: only negative values (bearish trends), zero out bullish
        # Both: keep signed values (positive=bullish, negative=bearish)
        #
        # Note: The trend gate expects negative values for bearish trends.
        # For bear bars, it inverts negative → positive gate. So Bear filter
        # must keep values negative (not convert to positive).
        if direction_filter == "Bull":
            # Keep positive values (+1), zero out negative (-1 becomes 0)
            result = np.where(result > 0, result, 0.0)
        elif direction_filter == "Bear":
            # Keep negative values for bearish trends (trend gate will invert for bear bars)
            result = np.where(result < 0, result, 0.0)
        # "Both" keeps all values unchanged (+1=bullish, -1=bearish)

        component_data = {
            f"{self.name()}_line": supertrend,
            f"{self.name()}_upper": final_upper,
            f"{self.name()}_lower": final_lower,
            f"{self.name()}_direction": direction,  # Original direction before filter
            f"{self.name()}_atr": atr
        }

        return result, component_data


class AROONTrendIndicator(BaseIndicator):
    """AROON Oscillator-based trend indicator.

    The AROON indicator identifies trend changes and trend strength:
    - AROON Up: How long since highest high in period
    - AROON Down: How long since lowest low in period
    - Oscillator: AROON Up - AROON Down (-100 to +100)

    Output:
    - Positive values (0.0 to 1.0): Bullish trend (AROON Up > AROON Down)
    - Negative values (-1.0 to 0.0): Bearish trend (AROON Down > AROON Up)
    """

    @classmethod
    def name(cls) -> str:
        return "aroon_trend"

    @property
    def display_name(self) -> str:
        return "AROON Trend"

    @property
    def description(self) -> str:
        return "AROON oscillator-based trend indicator measuring time since highs/lows"

    @classmethod
    def get_indicator_type(cls) -> IndicatorType:
        return IndicatorType.TREND

    @classmethod
    def get_layout_type(cls) -> str:
        return "stacked"  # AROON displayed in separate panel

    @classmethod
    def get_chart_config(cls) -> Dict[str, Any]:
        """Return AROON chart configuration for visualization."""
        return {
            "chart_type": "aroon",
            "title_suffix": "AROON Trend Analysis",
            "components": [
                {"key_suffix": "up", "name": "AROON Up", "color": "#26A69A", "line_width": 2},
                {"key_suffix": "down", "name": "AROON Down", "color": "#EF5350", "line_width": 2},
                {"key_suffix": "oscillator", "name": "Oscillator", "color": "#2962FF", "line_width": 1.5, "dash_style": "ShortDash"},
            ],
            "y_axis": {"min": -100, "max": 100, "title": "Value"},
            "reference_lines": [
                {"value": 0, "color": "#9E9E9E", "dash_style": "Dash", "label": "Zero Line"},
                {"value": 50, "color": "#66BB6A", "dash_style": "Dot", "label": "Strong Bull (50)"},
                {"value": -50, "color": "#EF5350", "dash_style": "Dot", "label": "Strong Bear (-50)"},
            ]
        }

    @classmethod
    def get_parameter_specs(cls) -> List[ParameterSpec]:
        return [
            ParameterSpec(
                name="period",
                display_name="AROON Period",
                parameter_type=ParameterType.INTEGER,
                default_value=25,
                min_value=5,
                max_value=50,
                step=1,
                description="Lookback period for AROON calculation",
                ui_group="AROON Settings"
            ),
            ParameterSpec(
                name="threshold",
                display_name="Signal Threshold",
                parameter_type=ParameterType.FLOAT,
                default_value=25.0,
                min_value=0.0,
                max_value=50.0,
                step=5.0,
                description="Oscillator must exceed this threshold for trend signal",
                ui_group="AROON Settings"
            ),
        ]

    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Calculate AROON trend values.

        Returns:
            - values: Array of trend values from -1.0 (bearish) to +1.0 (bullish)
            - components: Dict with AROON Up, Down, Oscillator for visualization
        """
        period = self.get_parameter("period")
        threshold = self.get_parameter("threshold")

        n = len(tick_data)
        if n < period + 1:
            return np.zeros(n), {}

        # Extract high/low data
        highs = np.array([tick.high for tick in tick_data], dtype=np.float64)
        lows = np.array([tick.low for tick in tick_data], dtype=np.float64)

        # Calculate AROON indicators
        aroon_down, aroon_up = ta.AROON(highs, lows, timeperiod=period)

        # Calculate oscillator (-100 to +100)
        oscillator = aroon_up - aroon_down

        # Normalize to -1 to +1, applying threshold
        result = np.zeros(n)
        valid_mask = ~np.isnan(oscillator)

        for i in range(n):
            if valid_mask[i]:
                if abs(oscillator[i]) >= threshold:
                    # Scale: oscillator/100, so +100 -> +1, -100 -> -1
                    result[i] = oscillator[i] / 100.0
                else:
                    # Below threshold: reduce proportionally
                    result[i] = (oscillator[i] / 100.0) * (abs(oscillator[i]) / threshold)

        # Clamp to [-1, 1]
        result = np.clip(result, -1.0, 1.0)

        component_data = {
            f"{self.name()}_up": aroon_up,
            f"{self.name()}_down": aroon_down,
            f"{self.name()}_oscillator": oscillator
        }

        return result, component_data


# Register all trend indicators
IndicatorRegistry().register(ADXTrendIndicator)
IndicatorRegistry().register(EMASlopeTrendIndicator)
IndicatorRegistry().register(SuperTrendIndicator)
IndicatorRegistry().register(AROONTrendIndicator)
