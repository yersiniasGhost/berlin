from typing import List
import numpy as np
from environments.tick_data import TickData
from models import IndicatorConfiguration
from config.types import CANDLE_STICK_PATTERN, PATTERN_MATCH
from features.candle_patterns import CandlePatterns


class IndicatorProcessor:

    def __init__(self, configuration: IndicatorConfiguration):
        self.config: IndicatorConfiguration = configuration

    # Each indicator will calculate a rating based upon different factors such as
    # indicator strength or age.   TBD
    def calculate_vector(self, tick: TickData, history: List[TickData]) -> np.array:

        output = []
        for indicator in self.config.indicators:

            # Candle stick patterns are using TALIB definitions
            if indicator.type == CANDLE_STICK_PATTERN:
                indicator_name = indicator.parameters['talib']
                cp = CandlePatterns([indicator_name])
                look_back = indicator.parameters.get('lookback', 10)

                result = cp.process_tick_data(tick, history, look_back)
                output.append(result[indicator_name][-1])

            # Pattern matching is using Eamonn's DTW
            elif indicator.type == PATTERN_MATCH:
                pass

        return np.array(output)


