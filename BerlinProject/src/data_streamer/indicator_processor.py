from typing import Union
from .data_preprocessor import DataPreprocessor
from models.monitor_configuration import MonitorConfiguration
from config.types import CANDLE_STICK_PATTERN, PATTERN_MATCH, INDICATOR_TYPE
from features.candle_patterns import CandlePatterns
from models.indicator_definition import IndicatorDefinition

from features.indicators import *


class IndicatorProcessor:

    def __init__(self, configuration: MonitorConfiguration):
        self.config: MonitorConfiguration = configuration

    @staticmethod
    def calculate_time_based_metric(indicator_data: np.ndarray, lookback: int) -> float:
        search = indicator_data[-lookback:]
        non_zero_indices = np.nonzero(search)[0]
        if non_zero_indices.size == 0:
            return 0.0
        c = search[non_zero_indices[-1]]
        lookback_location = len(search) - non_zero_indices[-1] - 1
        lookback_ratio = lookback_location / float(lookback)
        metric = (1.0 - lookback_ratio) * np.sign(c)

        return metric

    # Each indicator will calculate a rating based upon different factors such as
    # indicator strength or age.   TBD
    def next_tick(self, data_preprocessor: DataPreprocessor) -> Dict[str, float]:
        tick, history = data_preprocessor.get_data()  # get non-normalized data
        history = history[-50:]
        output = {}
        for indicator in self.config.indicators:
            look_back = indicator.parameters.get('lookback', 10)

            # Candle stick patterns are using TALIB definitions
            if indicator.type == CANDLE_STICK_PATTERN:
                indicator_name = indicator.parameters['talib']
                cp = CandlePatterns([indicator_name])
                result = cp.process_tick_data(tick, history, look_back)
                bull = indicator.parameters.get('bull', True)
                metric = self.calculate_time_based_metric(result[indicator_name], look_back)
                if bull is True and metric < 0:
                    metric = 0.0
                elif bull is False and metric > 0:
                    metric = 0.0
                output[indicator.name] = metric

            elif indicator.type == INDICATOR_TYPE:
                result = self.calculate_indicator(tick, history, indicator)
                metric = self.calculate_time_based_metric(result[indicator.name], look_back)

                output[indicator.name] = metric

            # Pattern matching is using Eamonn's DTW
            elif indicator.type == PATTERN_MATCH:
                pass

        return output

    @staticmethod
    def calculate_indicator(tick: TickData, history: List[TickData], indicator: IndicatorDefinition) -> Dict[str, np.ndarray]:
        if indicator.function == 'sma_crossover':
            return {indicator.name: sma_crossover(history, indicator.parameters)}

        elif indicator.function == 'macd_histogram_crossover':
            return {indicator.name: macd_histogram_crossover(history, indicator.parameters)}

        elif indicator.function == 'bol_bands_lower_band_bounce':
            return {indicator.name: bol_bands_lower_band_bounce(history, indicator.parameters)}

        else:
            raise ValueError(f"Unknown indicator: {indicator.name}")
