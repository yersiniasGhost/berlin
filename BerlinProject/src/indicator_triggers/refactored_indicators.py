"""
Refactored technical indicators using the new configurable base system.
"""

import math
from typing import List, Tuple, Dict, Any
import numpy as np
import talib as ta
from scipy.signal import argrelextrema

from models.tick_data import TickData
from indicator_triggers.indicator_base import BaseIndicator, ParameterSpec, ParameterType, IndicatorRegistry


class SMAIndicator(BaseIndicator):
    """Simple Moving Average indicator."""

    @classmethod
    def name(cls) -> str:
        return "sma"
    
    @property
    def display_name(self) -> str:
        return "Simple Moving Average"
    
    @property
    def description(self) -> str:
        return "Calculates the simple moving average over a specified period"
    
    @classmethod
    def get_parameter_specs(cls) -> List[ParameterSpec]:
        return [
            ParameterSpec(
                name="period",
                display_name="Period",
                parameter_type=ParameterType.INTEGER,
                default_value=10,
                min_value=2,
                max_value=20,
                step=1,
                description="Number of periods for the moving average",
                ui_group="Basic Settings"
            )
        ]

    @classmethod
    def get_layout_type(cls) -> str:
        """SMA uses overlay layout - line drawn on top of candlesticks."""
        return "overlay"

    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        period = self.get_parameter("period")

        if len(tick_data) < period:
            return np.array([math.nan] * len(tick_data)), {}

        closes = np.array([tick.close for tick in tick_data])
        sma = ta.SMA(closes, timeperiod=period)
        return sma, {f"{self.name()}_sma": sma}


class SMACrossoverIndicator(BaseIndicator):
    """SMA Crossover signal indicator."""

    @classmethod
    def name(cls) -> str:
        return "sma_crossover"

    @property
    def display_name(self) -> str:
        return "SMA Crossover"

    @property
    def description(self) -> str:
        return "Generates signals when price crosses above/below SMA with threshold"

    @classmethod
    def get_parameter_specs(cls) -> List[ParameterSpec]:
        return [
            ParameterSpec(
                name="period",
                display_name="SMA Period",
                parameter_type=ParameterType.INTEGER,
                default_value=20,
                min_value=2,
                max_value=30,
                step=1,
                description="Period for the SMA calculation",
                ui_group="Basic Settings"
            ),
            ParameterSpec(
                name="crossover_value",
                display_name="Crossover Threshold",
                parameter_type=ParameterType.FLOAT,
                default_value=0.005,
                min_value=0.0,
                max_value=0.01,
                step=0.0005,
                description="Percentage threshold for crossover detection",
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
        """SMA Crossover uses overlay layout - line drawn on top of candlesticks."""
        return "overlay"

    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        period = self.get_parameter("period")
        crossover_value = self.get_parameter("crossover_value")
        trend = self.get_parameter("trend")

        if len(tick_data) < period:
            return np.array([math.nan] * len(tick_data)), {f"{self.name()}_sma": np.array([0]*len(tick_data))}

        # Calculate SMA
        closes = np.array([tick.close for tick in tick_data])
        sma = ta.SMA(closes, timeperiod=period)

        # Create mask for valid (non-NaN) SMA values
        valid_mask = ~np.isnan(sma)

        if trend == 'bullish':
            sma_threshold = sma * (1 + crossover_value)
            crossovers = closes > sma_threshold
        else:  # bearish
            sma_threshold = sma * (1 - crossover_value)
            crossovers = closes < sma_threshold

        # Detect crossover moments - only trigger when BOTH current and previous are valid
        result = np.zeros(len(tick_data))
        crossover = np.logical_and(crossovers[1:], ~crossovers[:-1])
        both_valid = np.logical_and(valid_mask[1:], valid_mask[:-1])
        result[1:] = np.logical_and(crossover, both_valid)

        return result, {f"{self.name()}_sma": sma}


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



class BollingerBandsLowerBandBounceIndicator(BaseIndicator):
    """Bollinger Bands Lower Band Bounce signal indicator."""

    @classmethod
    def name(cls) -> str:
        return "bollinger_lower_bounce"
    
    @property
    def display_name(self) -> str:
        return "Bollinger Bands Lower Band Bounce"
    
    @property
    def description(self) -> str:
        return "Detects bounce signals when price touches lower band and moves back toward middle"
    
    @classmethod
    def get_parameter_specs(cls) -> List[ParameterSpec]:
        return [
            ParameterSpec(
                name="period",
                display_name="BB Period",
                parameter_type=ParameterType.INTEGER,
                default_value=20,
                min_value=5,
                max_value=100,
                step=1,
                description="Period for Bollinger Bands calculation",
                ui_group="Bollinger Bands Settings"
            ),
            ParameterSpec(
                name="sd",
                display_name="Standard Deviations",
                parameter_type=ParameterType.FLOAT,
                default_value=2.0,
                min_value=0.5,
                max_value=4.0,
                step=0.1,
                description="Number of standard deviations for band width",
                ui_group="Bollinger Bands Settings"
            ),
            ParameterSpec(
                name="candle_bounce_number",
                display_name="Lookback Candles",
                parameter_type=ParameterType.INTEGER,
                default_value=3,
                min_value=1,
                max_value=10,
                step=1,
                description="Number of candles to look back for band touch",
                ui_group="Bounce Settings"
            ),
            ParameterSpec(
                name="bounce_trigger",
                display_name="Bounce Trigger %",
                parameter_type=ParameterType.FLOAT,
                default_value=0.25,
                min_value=0.1,
                max_value=0.9,
                step=0.05,
                description="Percentage between bands to trigger bounce signal",
                ui_group="Bounce Settings"
            ),
            ParameterSpec(
                name="trend",
                display_name="Trend Direction",
                parameter_type=ParameterType.CHOICE,
                default_value="bullish",
                choices=["bullish", "bearish"],
                description="Direction of bounce to detect (bullish=lower band, bearish=upper band)",
                ui_group="Signal Settings"
            )
        ]
    
    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, Any]]:
        period = self.get_parameter("period")
        sd = self.get_parameter("sd")
        candle_bounce_number = int(self.get_parameter("candle_bounce_number"))
        bounce_trigger = self.get_parameter("bounce_trigger")
        trend = self.get_parameter("trend")

        if len(tick_data) < period:
            return np.array([math.nan] * len(tick_data)), {}

        closes = np.array([tick.close for tick in tick_data])
        upper, middle, lower = ta.BBANDS(closes, period, sd, sd)
        
        signals = np.zeros(len(closes))

        for i in range(candle_bounce_number, len(closes)):
            if trend == 'bullish':
                # Check if price touched lower band in lookback period
                if np.any(closes[i - candle_bounce_number:i] <= lower[i - candle_bounce_number:i]):
                    band_range = middle[i] - lower[i]
                    current_position = closes[i] - lower[i]
                    bounce_percentage = current_position / band_range

                    # Check bounce trigger condition
                    if (bounce_percentage >= bounce_trigger and
                            (i == candle_bounce_number or
                             (closes[i - 1] - lower[i - 1]) / (middle[i - 1] - lower[i - 1]) < bounce_trigger)):
                        signals[i] = 1

            else:  # bearish
                # Check if price touched upper band in lookback period
                if np.any(closes[i - candle_bounce_number:i] >= upper[i - candle_bounce_number:i]):
                    band_range = upper[i] - middle[i]
                    current_position = upper[i] - closes[i]
                    bounce_percentage = current_position / band_range

                    if (bounce_percentage >= bounce_trigger and
                            (i == candle_bounce_number or
                             (upper[i - 1] - closes[i - 1]) / (upper[i - 1] - middle[i - 1]) < bounce_trigger)):
                        signals[i] = 1

        component_data = {
            f"{self.name()}_upper": upper.tolist(),
            f"{self.name()}_middle": middle.tolist(),
            f"{self.name()}_lower": lower.tolist()
        }
        return signals, component_data


class SupportResistanceIndicator(BaseIndicator):
    """Support and Resistance level detection indicator."""



    @classmethod
    def name(cls) -> str:
        return "support_resistance"
    
    @property
    def display_name(self) -> str:
        return "Support & Resistance Levels"
    
    @property
    def description(self) -> str:
        return "Identifies support and resistance levels using local extrema"
    
    @classmethod
    def get_parameter_specs(cls) -> List[ParameterSpec]:
        return [
            ParameterSpec(
                name="sensitivity",
                display_name="Sensitivity",
                parameter_type=ParameterType.INTEGER,
                default_value=10,
                min_value=3,
                max_value=50,
                step=1,
                description="Sensitivity for detecting extrema (higher = less sensitive)",
                ui_group="Detection Settings"
            ),
            ParameterSpec(
                name="level_type",
                display_name="Level Type",
                parameter_type=ParameterType.CHOICE,
                default_value="support",
                choices=["support", "resistance", "both"],
                description="Type of levels to detect",
                ui_group="Detection Settings"
            )
        ]
    
    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, Any]]:
        sensitivity = self.get_parameter("sensitivity")
        level_type = self.get_parameter("level_type")

        closes = np.array([tick.close for tick in tick_data])
        result = np.zeros(len(closes))

        support_levels = []
        resistance_levels = []

        if level_type in ["support", "both"]:
            support_indices = argrelextrema(closes, np.less_equal, order=sensitivity)[0]
            result[support_indices] = 1
            support_levels = closes[support_indices].tolist() if len(support_indices) > 0 else []

        if level_type in ["resistance", "both"]:
            resistance_indices = argrelextrema(closes, np.greater_equal, order=sensitivity)[0]
            result[resistance_indices] = -1 if level_type == "both" else 1
            resistance_levels = closes[resistance_indices].tolist() if len(resistance_indices) > 0 else []

        component_data = {
            f"{self.name()}_support_levels": support_levels,
            f"{self.name()}_resistance_levels": resistance_levels
        }
        return result, component_data


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
                        # Debug: Check if pattern was detected on the most recent candle
                        # if len(pattern_detected) > 0 and pattern_detected[-1] == 1.0:
                        #     print(f"🔔 [CDL PATTERN DETECTED] {pattern_name} (bullish) on latest candle!")
                        result = np.maximum(result, pattern_detected)
                    else:  # bearish
                        # Detect bearish patterns (negative TA-Lib values)
                        # Convert to positive 1.0 for consistent bar weighting
                        pattern_detected = (pattern_values < 0).astype(float)
                        if len(pattern_detected) > 0 and pattern_detected[-1] == 1.0:
                            print(f"🔔 [CDL PATTERN DETECTED] {pattern_name} (bearish) on latest candle!")
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


# Register all indicators
IndicatorRegistry().register(SMAIndicator)
IndicatorRegistry().register(SMACrossoverIndicator)
IndicatorRegistry().register(MACDHistogramCrossoverIndicator)
IndicatorRegistry().register(BollingerBandsLowerBandBounceIndicator)
IndicatorRegistry().register(SupportResistanceIndicator)
IndicatorRegistry().register(CDLPatternIndicator)
IndicatorRegistry().register(RSIIndicator)
