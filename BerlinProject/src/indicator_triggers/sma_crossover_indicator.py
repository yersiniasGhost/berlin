"""SMA Crossover signal indicator."""

import math
from typing import List, Tuple, Dict
import numpy as np
import talib as ta

from models.tick_data import TickData
from indicator_triggers.indicator_base import BaseIndicator, ParameterSpec, ParameterType, IndicatorRegistry


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


IndicatorRegistry().register(SMACrossoverIndicator)
