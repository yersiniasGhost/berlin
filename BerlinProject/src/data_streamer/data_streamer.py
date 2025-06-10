"""
Simplified DataStreamer with proper typing
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from environments.tick_data import TickData
from data_streamer.indicator_processor import IndicatorProcessor
from data_streamer.candle_aggregator import CandleAggregator
from models.monitor_configuration import MonitorConfiguration
from data_streamer.external_tool import ExternalTool

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
        self.indicator_processor: IndicatorProcessor = IndicatorProcessor(monitor_config)
        self.external_tools: List[ExternalTool] = []

        logger.info(f"Created DataStreamer for {symbol} with timeframes: {required_timeframes}")

    def process_pip(self, pip_data: Dict[str, Any]) -> None:
        """Process incoming PIP data through aggregators"""
        symbol: Optional[str] = pip_data.get('key')
        print(f"DATASTREAMER RECEIVED PIP: {symbol}")  # ADD THIS
        if symbol != self.symbol:
            return

        # Send PIP to all aggregators and handle completed candles
        for timeframe, aggregator in self.aggregators.items():
            print(f"SENDING PIP to {timeframe} aggregator")  # ADD THIS
            completed_candle: Optional[TickData] = aggregator.process_pip(pip_data)

            if completed_candle:
                print(f"CANDLE COMPLETED: {timeframe}")  # ADD THIS
                self._handle_completed_candle(timeframe, completed_candle)

        # Send current price update
        self._send_price_update(pip_data)

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

    def get_symbol(self) -> str:
        """Get symbol"""
        return self.symbol

    def get_card_id(self) -> str:
        """Get card ID"""
        return self.card_id