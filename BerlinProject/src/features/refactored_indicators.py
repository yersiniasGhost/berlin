"""
Refactored technical indicators using the new configurable base system.
"""

import math
from typing import List
import numpy as np
import talib as ta
from scipy.signal import argrelextrema

from models.tick_data import TickData
from features.indicator_base import BaseIndicator, ParameterSpec, ParameterType, IndicatorRegistry 


class SMAIndicator(BaseIndicator):
    """Simple Moving Average indicator."""
    
    @property
    def name(self) -> str:
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
                default_value=20,
                min_value=1,
                max_value=200,
                step=1,
                description="Number of periods for the moving average",
                ui_group="Basic Settings"
            )
        ]
    
    def calculate(self, tick_data: List[TickData]) -> np.ndarray:
        period = self.get_parameter("period")
        
        if len(tick_data) < period:
            return np.array([math.nan] * len(tick_data))
        
        closes = np.array([tick.close for tick in tick_data])
        return ta.SMA(closes, timeperiod=period)


class SMACrossoverIndicator(BaseIndicator):
    """SMA Crossover signal indicator."""
    
    @property
    def name(self) -> str:
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
                min_value=1,
                max_value=200,
                step=1,
                description="Period for the SMA calculation",
                ui_group="Basic Settings"
            ),
            ParameterSpec(
                name="crossover_value",
                display_name="Crossover Threshold",
                parameter_type=ParameterType.FLOAT,
                default_value=0.01,
                min_value=0.0,
                max_value=0.1,
                step=0.001,
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
            )
        ]
    
    def calculate(self, tick_data: List[TickData]) -> np.ndarray:
        period = self.get_parameter("period")
        crossover_value = self.get_parameter("crossover_value")
        trend = self.get_parameter("trend")
        
        if len(tick_data) < period:
            return np.array([math.nan] * len(tick_data))

        # Calculate SMA
        closes = np.array([tick.close for tick in tick_data])
        sma = ta.SMA(closes, timeperiod=period)

        if trend == 'bullish':
            sma_threshold = sma * (1 + crossover_value)
            crossovers = closes > sma_threshold
        else:  # bearish
            sma_threshold = sma * (1 - crossover_value)
            crossovers = closes < sma_threshold

        # Detect crossover moments
        result = np.zeros(len(tick_data))
        result[1:] = np.logical_and(crossovers[1:], ~crossovers[:-1])

        return result


class MACDHistogramCrossoverIndicator(BaseIndicator):
    """MACD Histogram Crossover signal indicator."""
    
    @property
    def name(self) -> str:
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
                min_value=1,
                max_value=50,
                step=1,
                description="Fast EMA period for MACD calculation",
                ui_group="MACD Settings"
            ),
            ParameterSpec(
                name="slow",
                display_name="Slow EMA Period",
                parameter_type=ParameterType.INTEGER,
                default_value=26,
                min_value=1,
                max_value=100,
                step=1,
                description="Slow EMA period for MACD calculation",
                ui_group="MACD Settings"
            ),
            ParameterSpec(
                name="signal",
                display_name="Signal Period",
                parameter_type=ParameterType.INTEGER,
                default_value=9,
                min_value=1,
                max_value=50,
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
                max_value=0.1,
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
            )
        ]
    
    def calculate(self, tick_data: List[TickData]) -> np.ndarray:
        fast = self.get_parameter("fast")
        slow = self.get_parameter("slow")
        signal = self.get_parameter("signal")
        histogram_threshold = self.get_parameter("histogram_threshold")
        trend = self.get_parameter("trend")
        
        if len(tick_data) < slow + signal:
            return np.array([math.nan] * len(tick_data))

        closes = np.array([tick.close for tick in tick_data], dtype=np.float64)
        macd, signal_line, histogram = ta.MACD(closes, fastperiod=fast, slowperiod=slow, signalperiod=signal)
        
        result = np.zeros(len(tick_data))

        if trend == 'bullish':
            above_threshold = histogram > histogram_threshold
            result[1:] = np.logical_and(above_threshold[1:], ~above_threshold[:-1])
        else:  # bearish
            below_threshold = histogram < -histogram_threshold
            result[1:] = np.logical_and(below_threshold[1:], ~below_threshold[:-1])

        return result


class BollingerBandsLowerBandBounceIndicator(BaseIndicator):
    """Bollinger Bands Lower Band Bounce signal indicator."""
    
    @property
    def name(self) -> str:
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
    
    def calculate(self, tick_data: List[TickData]) -> np.ndarray:
        period = self.get_parameter("period")
        sd = self.get_parameter("sd")
        candle_bounce_number = int(self.get_parameter("candle_bounce_number"))
        bounce_trigger = self.get_parameter("bounce_trigger")
        trend = self.get_parameter("trend")
        
        if len(tick_data) < period:
            return np.array([math.nan] * len(tick_data))

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

        return signals


class SupportResistanceIndicator(BaseIndicator):
    """Support and Resistance level detection indicator."""
    
    @property
    def name(self) -> str:
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
    
    def calculate(self, tick_data: List[TickData]) -> np.ndarray:
        sensitivity = self.get_parameter("sensitivity")
        level_type = self.get_parameter("level_type")
        
        closes = np.array([tick.close for tick in tick_data])
        result = np.zeros(len(closes))
        
        if level_type in ["support", "both"]:
            support_indices = argrelextrema(closes, np.less_equal, order=sensitivity)[0]
            result[support_indices] = 1
        
        if level_type in ["resistance", "both"]:
            resistance_indices = argrelextrema(closes, np.greater_equal, order=sensitivity)[0]
            result[resistance_indices] = -1 if level_type == "both" else 1
        
        return result


# Register all indicators
IndicatorRegistry().register(SMAIndicator)
IndicatorRegistry().register(SMACrossoverIndicator)
IndicatorRegistry().register(MACDHistogramCrossoverIndicator)
IndicatorRegistry().register(BollingerBandsLowerBandBounceIndicator)
IndicatorRegistry().register(SupportResistanceIndicator)
