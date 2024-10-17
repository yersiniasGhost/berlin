from typing import List, Dict
import numpy as np
from environments.tick_data import TickData
from models import IndicatorConfiguration
from config.types import CANDLE_STICK_PATTERN, PATTERN_MATCH, INDICATOR_TYPE
from features.candle_patterns import CandlePatterns


class IndicatorProcessor:

    def __init__(self, configuration: IndicatorConfiguration):
        self.config: IndicatorConfiguration = configuration

    @staticmethod
    def calculate_time_based_metric(talib_data: np.ndarray, lookback: int) -> float:
        search = talib_data[-lookback-1:]
        non_zero_indices = np.nonzero(search)[0]
        if non_zero_indices.size == 0:
            return 0.0
        c = search[non_zero_indices[-1]]
        metric = (1.0 - ((float(len(search) - non_zero_indices[-1])) / float(lookback))) * np.sign(c)

        return metric

    # Each indicator will calculate a rating based upon different factors such as
    # indicator strength or age.   TBD
    def next_tick(self, tick: TickData, history: List[TickData]) -> Dict[str, float]:

        output = {}
        for indicator in self.config.indicators:
            look_back = indicator.parameters.get('lookback', 10)

            # Candle stick patterns are using TALIB definitions
            if indicator.type == CANDLE_STICK_PATTERN:
                indicator_name = indicator.parameters['talib']
                cp = CandlePatterns([indicator_name])
                result = cp.process_tick_data(tick, history, look_back)
                metric = self.calculate_time_based_metric(result[indicator_name], look_back)
                bull = indicator.parameters.get('bull', None)
                if bull is True and metric < 0:
                    metric = 0.0
                elif bull is False and metric > 0:
                    metric = 0.0
                output[indicator.name] = metric

            elif indicator.type == INDICATOR_TYPE:
                indicator_calculator = IndicatorCalculator()
                result = indicator_calculator.process_tick_data(tick, history, indicator)
                metric = self.calculate_time_based_metric(result[indicator.name], look_back)

                output[indicator.name] = metric

            # Pattern matching is using Eamonn's DTW
            elif indicator.type == PATTERN_MATCH:
                pass

        return output
