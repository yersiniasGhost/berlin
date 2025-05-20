from typing import Union, Tuple, Dict, List, Optional
import numpy as np
import logging

from features.indicators2 import support_level, resistance_level
from .data_preprocessor import DataPreprocessor
from models.monitor_configuration import MonitorConfiguration
from config.types import CANDLE_STICK_PATTERN, PATTERN_MATCH, INDICATOR_TYPE
from features.candle_patterns import CandlePatterns
from models.indicator_definition import IndicatorDefinition
from environments.tick_data import TickData
from data_streamer.candle_aggregator import CandleAggregator

from features.indicators import *

logger = logging.getLogger('IndicatorProcessor')


class IndicatorProcessor:

    def __init__(self, configuration: MonitorConfiguration):
        self.config: MonitorConfiguration = configuration

        # Create a cache for the most recent calculated results for each indicator
        self.last_calculated_results = {}
        self.last_raw_results = {}


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

    def next_tick(self, candle_aggregators: Dict[str, CandleAggregator]):
        output = {}  # Will store calculated indicators for this timeframe
        raw_output = {}  # Will store raw indicator values for this timeframe

        for indicator in self.config.indicators:
            tf = indicator.get("time_increment", "1m")
            look_back = indicator.parameters.get('lookback', 10)
            # get the appropriate data
            tick, history = candle_aggregators[tf].get_data()

            # Log the parameters for debugging
            logger.debug(
                f"Processing indicator: {indicator.name}, function: {indicator.function}, timeframe: {current_timeframe}")

            # Candle stick patterns (TALIB definitions)
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

                # Standard indicators
            elif indicator.type == INDICATOR_TYPE:
                result = self.calculate_indicator(tick, history, indicator)
                metric = self.calculate_time_based_metric(result[indicator.name], look_back)
                output[indicator.name] = metric
                raw_output[indicator.name] = result[indicator.name][-1] if len(result[indicator.name]) > 0 else 0.0

                # Pattern matching (DTW)
            elif indicator.type == PATTERN_MATCH:
                pass

            logger.debug(
                f"Calculated {indicator.name} = {output.get(indicator.name, 'N/A')} for timeframe {tf}")
        return output, raw_output


    @staticmethod
    def calculate_indicator(tick: TickData, history: List[TickData], indicator: IndicatorDefinition) -> Dict[
        str, np.ndarray]:
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