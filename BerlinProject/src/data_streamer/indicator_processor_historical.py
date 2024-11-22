from typing import List, Dict, Union, Tuple
import numpy as np
from numpy import ndarray

from .data_preprocessor import DataPreprocessor
from models.monitor_configuration import MonitorConfiguration
from config.types import CANDLE_STICK_PATTERN, PATTERN_MATCH, INDICATOR_TYPE
from features.candle_patterns import CandlePatterns
from models.indicator_definition import IndicatorDefinition
from mongo_tools.sample_tools import SampleTools
from mongo_tools.tick_history_tools import TickHistoryTools
from features.indicators2 import support_level, resistance_level
from features.indicators import sma_crossover, macd_histogram_crossover, bol_bands_lower_band_bounce
from environments.tick_data import TickData


class IndicatorProcessorHistorical:

    def __init__(self, configuration: MonitorConfiguration, data_link: Union[SampleTools, TickHistoryTools]):
        self.config: MonitorConfiguration = configuration
        self.data_link = data_link
        self.indicator_values, self.raw_indicators = self.precalculate()
        self.index = 0


    @staticmethod
    def calculate_time_based_metric_over_array(indicator_data: np.ndarray, lookback: int) -> np.ndarray:
        metrics = np.zeros(len(indicator_data))

        for i in range(len(metrics)):
            start = max(0, i-lookback)
            window = indicator_data[start:i]
            non_zero_indices = np.nonzero(window)[0]

            if non_zero_indices.size > 0:
                c = window[non_zero_indices[-1]]
                lookback_location = len(window) - non_zero_indices[-1] - 1  # lookback - non_zero_indices[-1] - 1
                lookback_ratio = lookback_location / float(lookback)
                metrics[i] = (1.0 - lookback_ratio) * np.sign(c)
        return metrics

    def next_tick(self, _: DataPreprocessor) -> Tuple[Dict[str, float], Dict[str, float]]:
        output, raw = {}, {}
        for indicator in self.config.indicators:
            output[indicator.name] = self.indicator_values[indicator.name][day_index][tick_index]
            if indicator.name in self.raw_indicators.keys():
                raw[indicator.name] = self.raw_indicators[indicator.name][self.index]
        return output, raw

    def precalculate(self) -> tuple[dict[str, ndarray], dict[str, ndarray]]:
        history_by_days = self.data_link.get_history()
        output = {}
        raw_indicators = {}

        # Build continuous history from all days
        episode_history = []
        for day_idx in sorted(history_by_days.keys()):
            episode_history.extend(history_by_days[day_idx])

        # Process indicators
        for indicator in self.config.indicators:
            look_back = indicator.parameters.get('lookback', 10)

            if indicator.type == CANDLE_STICK_PATTERN:
                indicator_name = indicator.parameters['talib']
                cp = CandlePatterns([indicator_name])
                result = cp.process_tick_data(episode_history, len(episode_history))
                bull = indicator.parameters.get('bull', True)
                metric = self.calculate_time_based_metric_over_array(result[indicator_name], look_back)
                if bull is True:
                    metric[metric < 0] = 0
                elif bull is False:
                    metric[metric > 0] = 0
                output[indicator.name] = metric

            elif indicator.type == INDICATOR_TYPE:
                result = self.calculate_indicator(episode_history, indicator)
                metric = self.calculate_time_based_metric_over_array(result[indicator.name], look_back)
                output[indicator.name] = metric
                raw_indicators[indicator.name] = result[indicator.name]

            elif indicator.type == PATTERN_MATCH:
                pass

        return output, raw_indicators

    # Each indicator will calculate a rating based upon different factors such as
    # indicator strength or age.   TBD
    # Change this next for THT??? allow it to read in the episode it is on???
    def precalculate_orig(self) -> Tuple[Dict[str, np.array], Dict[str, np.array]]:
        history = self.data_link.get_history()
        output = {}
        raw_indicators = {}
        for indicator in self.config.indicators:
            look_back = indicator.parameters.get('lookback', 10)

            # Candle stick patterns are using TALIB definitions
            if indicator.type == CANDLE_STICK_PATTERN:
                indicator_name = indicator.parameters['talib']
                cp = CandlePatterns([indicator_name])
                result = cp.process_tick_data(history, len(history))
                bull = indicator.parameters.get('bull', True)
                metric = self.calculate_time_based_metric_over_array(result[indicator_name], look_back)
                if bull is True:
                    metric[metric < 0] = 0
                elif bull is False:
                    metric[metric > 0] = 0
                output[indicator.name] = metric

            elif indicator.type == INDICATOR_TYPE:
                result = self.calculate_indicator(history, indicator)
                metric = self.calculate_time_based_metric_over_array(result[indicator.name], look_back)

                output[indicator.name] = metric
                raw_indicators[indicator.name] = result[indicator.name]

            # Pattern matching is using Eamonn's DTW
            elif indicator.type == PATTERN_MATCH:
                pass

        return output, raw_indicators

    @staticmethod
    def calculate_indicator(history: List[TickData], indicator: IndicatorDefinition) -> Dict[str, np.ndarray]:

        if indicator.function == 'sma_crossover':
            return {indicator.name: sma_crossover(history, indicator.parameters)}

        elif indicator.function == 'macd_histogram_crossover':
            return {indicator.name: macd_histogram_crossover(history, indicator.parameters)}

        elif indicator.function == 'bol_bands_lower_band_bounce':
            return {indicator.name: bol_bands_lower_band_bounce(history, indicator.parameters)}

        elif indicator.function == 'support_level':
            return {indicator.name: support_level(history, indicator.parameters)}

        elif indicator.function == 'resistance_level':
            return {indicator.name: resistance_level(history, indicator.parameters)}

        else:
            raise ValueError(f"Unknown indicator: {indicator.name}")
