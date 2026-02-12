"""Simple Moving Average indicator."""

import math
from typing import List, Tuple, Dict
import numpy as np
import talib as ta

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


IndicatorRegistry().register(SMAIndicator)
