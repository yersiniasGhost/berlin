# File: BerlinProject/src/data_streamer/data_streamer.py
# SIMPLE VERSION - Back to basics

"""
Simple DataStreamer that owns a CandleAggregator and processes indicators
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

from environments.tick_data import TickData
from data_streamer.indicator_processor import IndicatorProcessor
from data_streamer.candle_aggregator import CandleAggregator
from models.monitor_configuration import MonitorConfiguration
from data_streamer.external_tool import ExternalTool

logger = logging.getLogger('DataStreamer')


class DataStreamer:
    """
    Simple DataStreamer that owns candle aggregation for one symbol
    """

    def __init__(self, card_id: str, symbol: str, monitor_config: MonitorConfiguration):
        self.card_id: str = card_id
        self.symbol: str = symbol
        self.monitor_config: MonitorConfiguration = monitor_config

        # Own candle aggregators for this symbol
        self.aggregators: Dict[str, CandleAggregator] = {}

        # Create aggregators for each timeframe needed
        required_timeframes = monitor_config.get_time_increments()
        for timeframe in required_timeframes:
            self.aggregators[timeframe] = CandleAggregator(symbol, timeframe)

        # Create indicator processor
        self.indicator_processor: IndicatorProcessor = IndicatorProcessor(monitor_config)

        # External tools
        self.external_tools: List[ExternalTool] = []

        logger.info(f"Created DataStreamer for {symbol} with timeframes: {list(required_timeframes)}")

    def process_pip(self, pip_data: Dict) -> None:
        """
        Process PIP data - send to aggregators and handle completed candles
        """
        symbol = pip_data.get('key')
        if symbol != self.symbol:
            return

        # Send PIP to all aggregators
        for timeframe, aggregator in self.aggregators.items():
            completed_candle = aggregator.process_pip(pip_data)

            if completed_candle:
                # A candle completed in this timeframe
                self._handle_completed_candle(timeframe, completed_candle)

        # Always send current price update to UI
        self._send_price_update(pip_data)

    def _handle_completed_candle(self, timeframe: str, completed_candle: TickData) -> None:
        """
        Handle when a candle completes - calculate indicators and send to UI
        """
        try:
            logger.info(f"🕯️ {self.symbol}-{timeframe} candle completed @ ${completed_candle.close:.2f}")
            print(f"🔧 CANDLE COMPLETED: {self.symbol}-{timeframe} @ ${completed_candle.close:.2f}")  # DEBUG

            # Get all candle data from aggregators
            all_candle_data = self._get_all_candle_data()
            print(f"🔧 All candle data timeframes: {list(all_candle_data.keys())}")  # DEBUG

            for tf, data in all_candle_data.items():
                print(f"🔧 {tf}: {len(data)} candles")  # DEBUG

            # Check what indicators we have
            print(f"🔧 Monitor config has {len(self.monitor_config.indicators)} indicators")  # DEBUG
            for ind in self.monitor_config.indicators:
                print(f"🔧 Indicator: {ind.name} ({getattr(ind, 'time_increment', '1m')})")  # DEBUG

            # Calculate indicators using all available data
            indicators, raw_indicators, bar_scores = self.indicator_processor.calculate_indicators(
                all_candle_data, timeframe  # Pass which timeframe just completed
            )

            print(f"🔧 CALCULATED INDICATORS: {indicators}")  # DEBUG
            print(f"🔧 RAW INDICATORS: {raw_indicators}")  # DEBUG
            print(f"🔧 BAR SCORES: {bar_scores}")  # DEBUG

            # Send results to external tools
            for tool in self.external_tools:
                print(f"🔧 Sending to external tool: {type(tool).__name__}")  # DEBUG
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
            print(f"🔧 ERROR in handle_completed_candle: {e}")  # DEBUG
            import traceback
            traceback.print_exc()

    def _get_all_candle_data(self) -> Dict[str, List[TickData]]:
        """
        Get all candle data from all aggregators
        Returns: {timeframe: [candles]}
        """
        all_data = {}
        for timeframe, aggregator in self.aggregators.items():
            history = aggregator.get_history().copy()
            current = aggregator.get_current_candle()
            if current:
                history.append(current)
            all_data[timeframe] = history
        return all_data

    def _send_price_update(self, pip_data: Dict) -> None:
        """
        Send current price update to UI
        """
        try:
            price = float(pip_data.get('3', 0.0))  # Last price
            if price <= 0:
                return

            # Create simple tick for price update
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

            # Send to external tools
            for tool in self.external_tools:
                tool.price_update(
                    card_id=self.card_id,
                    symbol=self.symbol,
                    tick=current_tick
                )

        except Exception as e:
            logger.error(f"Error sending price update: {e}")

    def load_historical_data(self, data_link) -> None:
        """
        Load historical data for all timeframes
        """
        for timeframe, aggregator in self.aggregators.items():
            count = aggregator.prepopulate_data(data_link)
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