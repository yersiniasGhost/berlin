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

    def calculate_bar_scores(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """Calculate weighted bar scores from individual indicators"""
        bar_scores = {}

        for bar_name, bar_weights in self.config.bars.items():
            weighted_sum = 0.0
            total_weight = 0.0

            for indicator_name, weight in bar_weights.items():
                if indicator_name in indicators:
                    weighted_sum += indicators[indicator_name] * weight
                    total_weight += weight

            # Calculate weighted average (avoid division by zero)
            bar_scores[bar_name] = weighted_sum / total_weight if total_weight > 0 else 0.0

        return bar_scores

    def next_tick(self, candle_aggregators: Dict[str, CandleAggregator]) -> Tuple[
        Dict[str, float], Dict[str, float], Dict[str, float]]:
        """Now returns: indicators, raw_indicators, bar_scores"""
        output = {}  # Individual indicator results
        raw_output = {}  # Raw indicator values

        for indicator in self.config.indicators:
            tf = indicator.time_increment
            look_back = indicator.parameters.get('lookback', 10)
            tick, history = candle_aggregators[tf].get_data()

            # Calculate indicator (existing logic)
            if indicator.type == CANDLE_STICK_PATTERN:
                # Your existing candlestick pattern logic
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
                # Your existing indicator logic
                result = self.calculate_indicator(tick, history, indicator)
                metric = self.calculate_time_based_metric(result[indicator.name], look_back)
                output[indicator.name] = metric
                raw_output[indicator.name] = result[indicator.name][-1] if len(result[indicator.name]) > 0 else 0.0

        # NEW: Calculate bar scores from individual indicators
        bar_scores = self.calculate_bar_scores(output)

        return output, raw_output, bar_scores

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