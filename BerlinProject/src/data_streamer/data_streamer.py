# data_streamer/data_streamer.py - Minimal change: just swap trade executor
"""
DataStreamer with simple aggregator selection logic - MINIMAL CHANGE VERSION
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from models.tick_data import TickData
from data_streamer.indicator_processor import IndicatorProcessor
from candle_aggregator.candle_aggregator import CandleAggregator
from candle_aggregator.candle_aggregator_normal import CANormal
from candle_aggregator.candle_aggregator_heiken import CAHeiken
from models.monitor_configuration import MonitorConfiguration
from data_streamer.external_tool import ExternalTool
# ONLY CHANGE: Import unified trade executor instead of simple
from portfolios.trade_executor_unified import TradeExecutorUnified

logger = logging.getLogger('DataStreamer')


class DataStreamer:
    """
    DataStreamer with simple aggregator type selection
    """

    def __init__(self, card_id: str, symbol: str, monitor_config: MonitorConfiguration):
        self.card_id = card_id
        self.symbol = symbol
        self.monitor_config = monitor_config

        aggregator_configs = monitor_config.get_aggregator_configs()
        self.aggregators: Dict[str, CandleAggregator] = {}

        for agg_key, agg_type in aggregator_configs.items():
            timeframe = agg_key.split('-')[0]  # Extract timeframe from key
            aggregator = self._create_aggregator(agg_type, symbol, timeframe)
            self.aggregators[agg_key] = aggregator  # ← Store with unique key!
            logger.info(f"Created {agg_type} aggregator for {timeframe}")

        # Processing components
        self.indicator_processor: IndicatorProcessor = IndicatorProcessor(monitor_config)
        self.external_tools: List[ExternalTool] = []

        # ONLY CHANGE: Use unified TradeExecutor with configuration from monitor_config
        self.trade_executor: TradeExecutorUnified = TradeExecutorUnified(monitor_config)

        # Initialize tracking variables
        self.indicators: Dict[str, float] = {}
        self.raw_indicators: Dict[str, float] = {}
        self.bar_scores: Dict[str, float] = {}

        logger.info(f"DataStreamer initialized for {symbol}")
        logger.info(f"Trade Executor Config: {monitor_config.trade_executor}")

    def process_tick(self, tick_data: TickData) -> None:
        """
        Process incoming TickData and execute trading logic
        """
        if tick_data.symbol != self.symbol:
            return

        # Process tick through all aggregators
        for timeframe, aggregator in self.aggregators.items():
            completed_candle = aggregator.process_tick(tick_data)
            if completed_candle is not None:
                logger.debug(f"Completed {timeframe} {aggregator._get_aggregator_type()} candle")

        # Calculate indicators based on current aggregator state
        self.indicators, self.raw_indicators, self.bar_scores = (
            self.indicator_processor.calculate_indicators_new(self.aggregators))

        # Execute trading logic
        self.trade_executor.make_decision(
            tick=tick_data,
            indicators=self.indicators,
            bar_scores=self.bar_scores
        )

        # Get portfolio performance metrics
        portfolio_metrics = self.trade_executor.portfolio.get_performance_metrics(tick_data.close)

        # Send data to external tools
        for tool in self.external_tools:
            tool.process_tick(
                card_id=self.card_id,
                symbol=self.symbol,
                tick_data=tick_data,
                indicators=self.indicators,
                raw_indicators=self.raw_indicators,
                bar_scores=self.bar_scores,
                portfolio_metrics=portfolio_metrics
            )

    def _create_aggregator(self, agg_type: str, symbol: str, timeframe: str) -> CandleAggregator:
        """
        Create appropriate aggregator based on type
        """
        if agg_type == "heiken":
            return CAHeiken(symbol, timeframe)
        else:  # Default to normal
            return CANormal(symbol, timeframe)

    def _calculate_bar_scores(self) -> Dict[str, float]:
        """
        Calculate bar scores based on indicators and bar configurations
        """
        bar_scores = {}

        for bar_name, bar_config in self.monitor_config.bars.items():
            if 'indicators' not in bar_config:
                continue

            total_score = 0.0
            total_weight = 0.0

            for indicator_name, weight in bar_config['indicators'].items():
                if indicator_name in self.indicators:
                    indicator_value = self.indicators[indicator_name]
                    weighted_score = indicator_value * weight
                    total_score += weighted_score
                    total_weight += weight

            # Calculate normalized bar score
            if total_weight > 0:
                bar_scores[bar_name] = total_score / total_weight
            else:
                bar_scores[bar_name] = 0.0

        return bar_scores

    def get_portfolio_status(self) -> Dict:
        """Get current portfolio and trade executor status"""
        return {
            'portfolio': self.trade_executor.portfolio.get_summary(),
            'trade_executor': self.trade_executor.get_status(),
            'indicators': self.indicators,
            'bar_scores': self.bar_scores
        }

    def enable_debug_mode(self):
        """Enable debug mode for trade executor"""
        self.trade_executor.enable_debug_mode()

    def load_historical_data(self, data_link) -> None:
        """
        Load historical data for all aggregators using the provided data_link

        Args:
            data_link: Data link object with load_historical_data method
        """
        try:
            for agg_key, aggregator in self.aggregators.items():
                # Use prepopulate_data method from base CandleAggregator class
                candles_loaded = aggregator.prepopulate_data(data_link)
                logger.info(f"Loaded {candles_loaded} historical candles for {agg_key}")
        except Exception as e:
            logger.error(f"Error loading historical data: {e}")

    def connect_tool(self, external_tool) -> None:
        """
        Connect an external tool to receive updates

        Args:
            external_tool: External tool to add to the list
        """
        if external_tool not in self.external_tools:
            self.external_tools.append(external_tool)
            logger.info(f"Connected external tool: {type(external_tool).__name__}")

    def _get_all_candle_data(self) -> Dict[str, List[TickData]]:
        """Get all candle data from aggregators - needed for API routes"""
        all_data: Dict[str, List[TickData]] = {}

        for agg_key, aggregator in self.aggregators.items():
            history: List[TickData] = aggregator.get_history().copy()
            current: Optional[TickData] = aggregator.get_current_candle()

            if current:
                history.append(current)

            all_data[agg_key] = history

        return all_data