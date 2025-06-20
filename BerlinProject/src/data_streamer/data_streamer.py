# data_streamer/data_streamer.py - Updated logic
"""
DataStreamer with simple aggregator selection logic
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
from portfolios.trade_executor_simple import TradeExecutorSimple

logger = logging.getLogger('DataStreamer')


class DataStreamer:
    """
    DataStreamer with simple aggregator type selection
    """

    def __init__(self, card_id: str, symbol: str, monitor_config: MonitorConfiguration,
                 default_position_size: float = 100.0, stop_loss_pct: float = 0.005) -> None:
        self.card_id: str = card_id
        self.symbol: str = symbol
        self.monitor_config: MonitorConfiguration = monitor_config

        # Get aggregator type from configuration
        aggregator_type = monitor_config.get_aggregator_type()
        self.aggregators: Dict[str, CandleAggregator] = {}
        required_timeframes: List[str] = list(monitor_config.get_time_increments())

        for timeframe in required_timeframes:
            aggregator = self._create_aggregator(aggregator_type, symbol, timeframe)
            self.aggregators[timeframe] = aggregator
            logger.info(f"Created {aggregator_type} aggregator for {timeframe}")

        # Processing components
        self.indicator_processor: IndicatorProcessor = IndicatorProcessor(monitor_config)
        self.external_tools: List[ExternalTool] = []

        # TradeExecutor instance
        self.trade_executor: TradeExecutorSimple = TradeExecutorSimple(
            monitor_config=monitor_config,
            default_position_size=default_position_size,
            stop_loss_pct=stop_loss_pct
        )

        # Initialize tracking variables
        self.indicators: Dict[str, float] = {}
        self.raw_indicators: Dict[str, float] = {}
        self.bar_scores: Dict[str, float] = {}

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

    def _get_all_candle_data(self) -> Dict[str, List[TickData]]:
        """Get all candle data from aggregators"""
        all_data: Dict[str, List[TickData]] = {}

        for timeframe, aggregator in self.aggregators.items():
            history: List[TickData] = aggregator.get_history().copy()
            current: Optional[TickData] = aggregator.get_current_candle()

            if current:
                history.append(current)

            all_data[timeframe] = history

        return all_data

    def _create_aggregator(self, aggregator_type: str, symbol: str, timeframe: str) -> CandleAggregator:
        if aggregator_type == "normal":
            return CANormal(symbol, timeframe)
        elif aggregator_type == "heiken":
            return CAHeiken(symbol, timeframe)

    def load_historical_data(self, data_link) -> None:
        """Load historical data for all timeframes"""
        for timeframe, aggregator in self.aggregators.items():
            aggregator.prepopulate_data(data_link)

    def connect_tool(self, external_tool: ExternalTool) -> None:
        """Connect an external tool"""
        self.external_tools.append(external_tool)