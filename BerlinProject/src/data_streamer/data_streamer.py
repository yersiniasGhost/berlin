"""
Simplified DataStreamer with proper typing
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from models.tick_data import TickData
from data_streamer.indicator_processor import IndicatorProcessor
from data_streamer.candle_aggregator import CandleAggregator
from models.monitor_configuration import MonitorConfiguration
from data_streamer.external_tool import ExternalTool
from portfolios.trade_executor import TradeExecutor
from portfolios.trade_executor_simple import TradeExecutorSimple

logger = logging.getLogger('DataStreamer')


class DataStreamer:
    """
    DataStreamer owns aggregators and processes data for one symbol+config combination
    """

    class DataStreamer:
        """
        DataStreamer owns aggregators and processes data for one symbol+config combination
        Now includes TradeExecutor for portfolio management with simplified metrics
        """

        def __init__(self, card_id: str, symbol: str, monitor_config: MonitorConfiguration,
                     default_position_size: float = 1.0, stop_loss_pct: float = 0.5) -> None:
            self.card_id: str = card_id
            self.symbol: str = symbol
            self.monitor_config: MonitorConfiguration = monitor_config

            # Own candle aggregators for each required timeframe
            self.aggregators: Dict[str, CandleAggregator] = {}
            required_timeframes: List[str] = list(monitor_config.get_time_increments())

            for timeframe in required_timeframes:
                self.aggregators[timeframe] = CandleAggregator(symbol, timeframe)

            # Processing components
            self.indicator_processor: IndicatorProcessor = IndicatorProcessor(monitor_config)
            self.external_tools: List[ExternalTool] = []

            # Add TradeExecutor instance
            self.trade_executor: TradeExecutorSimple = TradeExecutorSimple(
                monitor_config=monitor_config,
                default_position_size=default_position_size,
                stop_loss_pct=stop_loss_pct
            )

            logger.info(f"Created DataStreamer for {symbol} with timeframes: {required_timeframes}")
            logger.info(
                f"TradeExecutor initialized with position size: {default_position_size}, stop loss: {stop_loss_pct}%")

        def process_tick(self, tick_data: TickData) -> None:
            """
            Process incoming TickData and execute trading logic

            Args:
                tick_data: TickData object with type="PIP" for real-time data
            """
            if tick_data.symbol != self.symbol:
                return

            # Process tick through aggregators
            for aggregator in self.aggregators.values():
                aggregator.process_tick(tick_data)

            # Calculate indicators based on current aggregator state
            self.indicators, self.raw_indicators, self.bar_scores = (
                self.indicator_processor.calculate_indicators_new(self.aggregators))

            # Execute trading logic based on current indicators and bar scores
            self.trade_executor.make_decision(
                tick=tick_data,
                indicators=self.indicators,
                bar_scores=self.bar_scores
            )

            # Get simplified portfolio performance metrics with current price
            portfolio_metrics = self.trade_executor.portfolio.get_performance_metrics(tick_data.close)

            # Send data to external tools (including portfolio data)
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

    def load_historical_data(self, data_link) -> None:
        """Load historical data for all timeframes"""
        for timeframe, aggregator in self.aggregators.items():
            count: int = aggregator.prepopulate_data(data_link)
            logger.info(f"Loaded {count} {timeframe} candles for {self.symbol}")

    def connect_tool(self, external_tool: ExternalTool) -> None:
        """Connect an external tool"""
        self.external_tools.append(external_tool)
