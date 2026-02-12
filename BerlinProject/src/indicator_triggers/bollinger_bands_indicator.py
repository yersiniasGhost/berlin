"""Bollinger Bands Lower Band Bounce signal indicator."""

import math
from typing import List, Tuple, Dict, Any
import numpy as np
import talib as ta

from models.tick_data import TickData
from indicator_triggers.indicator_base import BaseIndicator, ParameterSpec, ParameterType, IndicatorRegistry


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


IndicatorRegistry().register(BollingerBandsLowerBandBounceIndicator)
