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

from features.indicators import *

logger = logging.getLogger('IndicatorProcessor')


class IndicatorProcessor:

    def __init__(self, configuration: MonitorConfiguration):
        self.config: MonitorConfiguration = configuration

        # Group indicators by timeframe
        self.indicators_by_timeframe = self._group_indicators_by_timeframe()

        # Create a cache for the most recent calculated results for each indicator
        self.last_calculated_results = {}
        self.last_raw_results = {}

    def _group_indicators_by_timeframe(self) -> Dict[str, List[IndicatorDefinition]]:
        """Group indicators by their timeframe"""
        result = {}

        for indicator in self.config.indicators:
            # Get the timeframe for this indicator (default to "1m")
            timeframe = getattr(indicator, 'time_increment', "1m")

            # Initialize the list for this timeframe if needed
            if timeframe not in result:
                result[timeframe] = []

            # Add the indicator to its timeframe group
            result[timeframe].append(indicator)

        return result

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


    # fix this and test it in isolation with the candlestick aggregator
    # try to make candlestick get_data the same.
    def next_tick(self, data_preprocessor: DataPreprocessor) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Process the next tick for indicators, taking timeframe into account.
        Returns indicator results specific to the current tick's timeframe.
        """
        tick, history = data_preprocessor.get_data()  # get non-normalized data

        # Skip if tick is None
        if tick is None:
            logger.debug("Received None tick")
            return {}, {}

        # Ensure we're working with a completed candle
        is_completed_candle = (hasattr(tick, 'open') and hasattr(tick, 'high') and
                               hasattr(tick, 'low') and hasattr(tick, 'close') and
                               not getattr(tick, 'is_current', False))

        if not is_completed_candle:
            logger.debug("Received incomplete candle data")
            # Return empty results for incomplete candles
            return {}, {}

        # Get the timeframe of the current tick (default to "1m")
        # Explicitly check for time_increment attribute
        current_timeframe = getattr(tick, 'time_increment', "1m") if hasattr(tick, 'time_increment') else "1m"

        # Get indicators for the current timeframe
        current_timeframe_indicators = self.indicators_by_timeframe.get(current_timeframe, [])

        logger.info(f"Processing {len(current_timeframe_indicators)} indicators for timeframe {current_timeframe}")

        if not current_timeframe_indicators:
            logger.info(f"No indicators found for timeframe {current_timeframe}")
            # If no indicators for this timeframe, return empty results
            return {}, {}

        # Filter history by the current timeframe
        filtered_history = []
        for hist_tick in history:
            # Explicitly check if the tick has a time_increment attribute
            hist_timeframe = getattr(hist_tick, 'time_increment', "1m") if hasattr(hist_tick,
                                                                                   'time_increment') else "1m"
            if hist_timeframe == current_timeframe:
                filtered_history.append(hist_tick)

        logger.info(f"Found {len(filtered_history)} historical points for timeframe {current_timeframe}")

        # Process only indicators for the current timeframe
        output = {}  # Will store calculated indicators for this timeframe
        raw_output = {}  # Will store raw indicator values for this timeframe

        for indicator in current_timeframe_indicators:
            look_back = indicator.parameters.get('lookback', 10)

            # Log the parameters for debugging
            logger.debug(
                f"Processing indicator: {indicator.name}, function: {indicator.function}, timeframe: {current_timeframe}")

            # Candle stick patterns (TALIB definitions)
            if indicator.type == CANDLE_STICK_PATTERN:
                indicator_name = indicator.parameters['talib']
                cp = CandlePatterns([indicator_name])
                result = cp.process_tick_data(filtered_history, look_back)
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
                result = self.calculate_indicator(tick, filtered_history, indicator)
                metric = self.calculate_time_based_metric(result[indicator.name], look_back)
                output[indicator.name] = metric
                raw_output[indicator.name] = result[indicator.name][-1] if len(result[indicator.name]) > 0 else 0.0

            # Pattern matching (DTW)
            elif indicator.type == PATTERN_MATCH:
                pass

            logger.debug(
                f"Calculated {indicator.name} = {output.get(indicator.name, 'N/A')} for timeframe {current_timeframe}")

        # Initialize timeframe-specific result dictionaries if they don't exist
        if not hasattr(self, 'results_by_timeframe'):
            self.results_by_timeframe = {}
        if not hasattr(self, 'raw_results_by_timeframe'):
            self.raw_results_by_timeframe = {}

        # Initialize for this timeframe if needed
        if current_timeframe not in self.results_by_timeframe:
            self.results_by_timeframe[current_timeframe] = {}
        if current_timeframe not in self.raw_results_by_timeframe:
            self.raw_results_by_timeframe[current_timeframe] = {}

        # Update the results for the current timeframe only
        self.results_by_timeframe[current_timeframe] = output
        self.raw_results_by_timeframe[current_timeframe] = raw_output

        # Return only the results for the current timeframe
        return self.results_by_timeframe[current_timeframe], self.raw_results_by_timeframe[current_timeframe]

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