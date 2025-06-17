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

logger = logging.getLogger('DataStreamer')


class DataStreamer:
    """
    DataStreamer owns aggregators and processes data for one symbol+config combination
    """

    def __init__(self, card_id: str, symbol: str, monitor_config: MonitorConfiguration) -> None:
        self.card_id: str = card_id
        self.symbol: str = symbol
        self.monitor_config: MonitorConfiguration = monitor_config

        # Own candle aggregators for each required timeframe
        self.aggregators: Dict[str, CandleAggregator] = {}
        required_timeframes: List[str] = list(monitor_config.get_time_increments())

        for timeframe in required_timeframes:
            self.aggregators[timeframe] = CandleAggregator(symbol, timeframe)

        # Processing components
        # self.trade_executor = TradeExecutor(monitor_config, default_position_size=1.0, stop_loss_pct=0.5)
        # self.external_tool = ExternalTool()
        self.indicator_processor: IndicatorProcessor = IndicatorProcessor(monitor_config)
        self.external_tools: List[ExternalTool] = []

        logger.info(f"Created DataStreamer for {symbol} with timeframes: {required_timeframes}")

    def process_tick(self, tick_data: TickData) -> None:
        """
        Process incoming TickData (formerly process_tick)

        Args:
            tick_data: TickData object with type="PIP" for real-time data
        """
        if tick_data.symbol != self.symbol:
            return

        for aggregator in self.aggregators.values():
            aggregator.process_tick(tick_data)

        # Calculate indicators based on current aggregator state
        self.indicators, self.raw_indicators, self.bar_scores = (
            self.indicator_processor.calculate_indicators_new(self.aggregators))

        for tool in self.external_tools:
            tool.process_tick(
                card_id=self.card_id,
                symbol=self.symbol,
                tick_data=tick_data,
                indicators=self.indicators,
                raw_indicators=self.raw_indicators,
                bar_scores=self.bar_scores
            )


    # for each tick data from the data link will be passed to the aggregator process pip
    # def process_pip(self, pip_data: Dict[str, Any]) -> None:
    #     symbol: Optional[str] = pip_data.get('key')
    #     if symbol != self.symbol:
    #         return
    #     ##############
    #     for aggregator in self.aggregators.values():
    #         aggregator.process_pip(pip_data)
    #
    #     self.indicators, self.raw_indicators, self.bar_scores = (
    #         self.indicator_processor.calculate_indicators_new(self.aggregators))
    #
    #     self.external_tool.process_pip(
    #             card_id=self.card_id,
    #             symbol=self.symbol,
    #             pip_data=pip_data,
    #             indicators=self.indicators,
    #             raw_indicators=self.raw_indicators,
    #             bar_scores=self.bar_scores
    #         )
    #
    #     # add new method process pip in ui external tool for extenral tool deciding
    #     # if it needs to indicator vector or to use price update
    #     ##############
    #
    #     # Send PIP to all aggregators and handle completed candles
    #     for timeframe, aggregator in self.aggregators.items():
    #         print(f"SENDING PIP to {timeframe} aggregator")  # ADD THIS
    #         completed_candle: Optional[TickData] = aggregator.process_pip(pip_data)
    #
    #         if completed_candle:
    #             print(f"CANDLE COMPLETED: {timeframe}")  # ADD THIS
    #             self._handle_completed_candle(timeframe, completed_candle)
    #     # Send current price update
    #     self._send_price_update(pip_data)

    def _handle_completed_candle(self, timeframe: str, completed_candle: TickData) -> None:
        """Handle when a candle completes - calculate indicators and notify tools"""
        try:
            print(f"HANDLING COMPLETED CANDLE: {timeframe} @ ${completed_candle.close}")  # ADD THIS

            all_candle_data: Dict[str, List[TickData]] = self._get_all_candle_data()
            print(f"ALL CANDLE DATA: {list(all_candle_data.keys())}")  # ADD THIS

            print("CALLING INDICATOR PROCESSOR...")  # ADD THIS
            indicators, raw_indicators, bar_scores = self.indicator_processor.calculate_indicators(
                all_candle_data, timeframe
            )
            print(f"INDICATOR RESULTS: {indicators}")  # ADD THIS

            print(f"SENDING TO {len(self.external_tools)} EXTERNAL TOOLS...")  # ADD THIS
            for tool in self.external_tools:
                tool.indicator_vector(
                    card_id=self.card_id,
                    symbol=self.symbol,
                    tick=completed_candle,
                    indicators=indicators,
                    bar_scores=bar_scores,
                    raw_indicators=raw_indicators
                )

        except Exception as e:
            logger.error(f"Error handling completed candle: {e}")
            print(f"ERROR IN HANDLE_COMPLETED_CANDLE: {e}")  # ADD THIS

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

    def _send_price_update(self, pip_data: Dict[str, Any]) -> None:
        """Send current price update to tools"""
        try:
            price: float = float(pip_data.get('3', 0.0))
            if price <= 0:
                return

            current_tick = TickData(
                symbol=self.symbol,
                timestamp=datetime.now(),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=1000,
                time_increment="1m"
            )

            for tool in self.external_tools:
                if hasattr(tool, 'price_update'):
                    tool.price_update(
                        card_id=self.card_id,
                        symbol=self.symbol,
                        tick=current_tick
                    )

        except Exception as e:
            logger.error(f"Error sending price update: {e}")

    def load_historical_data(self, data_link) -> None:
        """Load historical data for all timeframes"""
        for timeframe, aggregator in self.aggregators.items():
            count: int = aggregator.prepopulate_data(data_link)
            logger.info(f"Loaded {count} {timeframe} candles for {self.symbol}")

    def connect_tool(self, external_tool: ExternalTool) -> None:
        """Connect an external tool"""
        self.external_tools.append(external_tool)

    # def get_trade_executor(self):
    #     return self.trade_executor

    def get_symbol(self) -> str:
        """Get symbol"""
        return self.symbol

    def get_card_id(self) -> str:
        """Get card ID"""
        return self.card_id
