"""Support and Resistance level detection indicator."""

from typing import List, Tuple, Dict, Any
import numpy as np
from scipy.signal import argrelextrema

from models.tick_data import TickData
from indicator_triggers.indicator_base import BaseIndicator, ParameterSpec, ParameterType, IndicatorRegistry


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


IndicatorRegistry().register(SupportResistanceIndicator)
