from typing import Union, Tuple

from features.indicators2 import support_level, resistance_level
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

    def next_tick(self, data_preprocessor: DataPreprocessor) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Process the next tick for indicators.
        This should only be called with completed candles.

        Args:
            data_preprocessor: The data preprocessor containing the current tick and history

        Returns:
            Tuple of (indicator_results, raw_indicators)
        """
        tick, history = data_preprocessor.get_data()  # get non-normalized data

        # Ensure we're working with a completed candle
        if not hasattr(tick, 'open') or not hasattr(tick, 'high') or not hasattr(tick, 'low') or not hasattr(tick,
                                                                                                             'close'):
            logger.warning("IndicatorProcessor received incomplete candle data")
            return {}, {}

        # Use a reasonable history length but cap it to avoid performance issues
        max_history = 50
        history = history[-max_history:]

        output = {}
        raw_output = {}  # Add this to store raw indicator values

        for indicator in self.config.indicators:
            look_back = indicator.parameters.get('lookback', 10)

            # Candle stick patterns are using TALIB definitions
            if indicator.type == CANDLE_STICK_PATTERN:
                indicator_name = indicator.parameters['talib']
                cp = CandlePatterns([indicator_name])
                result = cp.process_tick_data(history, look_back)
                bull = indicator.parameters.get('bull', True)
                metric = self.calculate_time_based_metric(result[indicator_name], look_back)
                if bull is True and metric < 0:
                    metric = 0.0
                elif bull is False and metric > 0:
                    metric = 0.0
                output[indicator.name] = metric
                raw_output[indicator.name] = result[indicator_name][-1] if len(result[indicator_name]) > 0 else 0.0

            elif indicator.type == INDICATOR_TYPE:
                result = self.calculate_indicator(tick, history, indicator)
                metric = self.calculate_time_based_metric(result[indicator.name], look_back)
                output[indicator.name] = metric
                raw_output[indicator.name] = result[indicator.name][-1] if len(result[indicator.name]) > 0 else 0.0

            # Pattern matching is using Eamonn's DTW
            elif indicator.type == PATTERN_MATCH:
                pass

        return output, raw_output

    @staticmethod
    def calculate_indicator(tick: TickData, history: List[TickData], indicator: IndicatorDefinition) -> Dict[str, np.ndarray]:
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
