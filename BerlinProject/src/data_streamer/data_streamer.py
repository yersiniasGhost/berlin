# File: BerlinProject/src/data_streamer/data_streamer.py
# ENHANCED DEBUG VERSION

"""
DataStreamer with extensive debug logging to trace the complete flow
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
    DataStreamer with extensive debug logging
    """

    def __init__(self, card_id: str, symbol: str, monitor_config: MonitorConfiguration):
        self.card_id: str = card_id
        self.symbol: str = symbol
        self.monitor_config: MonitorConfiguration = monitor_config

        # Debug: Print initialization details
        print(f"🔧 DATASTREAMER INIT: {card_id} for {symbol}")

        # Own candle aggregators for this symbol
        self.aggregators: Dict[str, CandleAggregator] = {}

        # Create aggregators for each timeframe needed
        required_timeframes = monitor_config.get_time_increments()
        print(f"🔧 DATASTREAMER: Required timeframes: {list(required_timeframes)}")

        for timeframe in required_timeframes:
            self.aggregators[timeframe] = CandleAggregator(symbol, timeframe)
            print(f"🔧 DATASTREAMER: Created {timeframe} aggregator for {symbol}")

        # Create indicator processor
        self.indicator_processor: IndicatorProcessor = IndicatorProcessor(monitor_config)

        # External tools
        self.external_tools: List[ExternalTool] = []

        # Debug counters
        self.pip_count = 0
        self.candle_completions = {tf: 0 for tf in required_timeframes}

        logger.info(f"Created DataStreamer for {symbol} with timeframes: {list(required_timeframes)}")

    def process_pip(self, pip_data: Dict) -> None:
        """
        Process PIP data - send to aggregators and handle completed candles
        """
        symbol = pip_data.get('key')
        if symbol != self.symbol:
            return

        self.pip_count += 1

        # Debug: Log every 10th PIP to avoid spam
        if self.pip_count % 10 == 0:
            price = pip_data.get('3', 0)
            timestamp_ms = pip_data.get('38', 0)
            pip_time = datetime.fromtimestamp(timestamp_ms / 1000) if timestamp_ms else 'unknown'
            print(f"🔧 PIP #{self.pip_count}: {symbol} @ ${price} at {pip_time}")

        # Send PIP to all aggregators
        completed_any = False
        for timeframe, aggregator in self.aggregators.items():
            completed_candle = aggregator.process_pip(pip_data)

            if completed_candle:
                # A candle completed in this timeframe
                self.candle_completions[timeframe] += 1
                completed_any = True
                print(f"🔧 CANDLE #{self.candle_completions[timeframe]} COMPLETED: {symbol}-{timeframe}")
                self._handle_completed_candle(timeframe, completed_candle)

        # Always send current price update to UI (but only log occasionally)
        if self.pip_count % 20 == 0 or completed_any:
            self._send_price_update(pip_data)

    def _handle_completed_candle(self, timeframe: str, completed_candle: TickData) -> None:
        """
        Handle when a candle completes - calculate indicators and send to UI
        """
        try:
            print(f"🔧 ========== CANDLE COMPLETED ==========")
            print(f"🔧 Symbol: {self.symbol}")
            print(f"🔧 Timeframe: {timeframe}")
            print(f"🔧 Price: ${completed_candle.close:.2f}")
            print(f"🔧 Time: {completed_candle.timestamp}")
            print(
                f"🔧 OHLCV: O:${completed_candle.open:.2f} H:${completed_candle.high:.2f} L:${completed_candle.low:.2f} C:${completed_candle.close:.2f} V:{completed_candle.volume}")

            # Get all candle data from aggregators
            all_candle_data = self._get_all_candle_data()
            print(f"🔧 Available timeframe data:")
            for tf, data in all_candle_data.items():
                print(f"🔧 - {tf}: {len(data)} candles (latest: ${data[-1].close:.2f} @ {data[-1].timestamp})")

            # Debug: Show what indicators we should calculate
            indicators_for_this_tf = [ind for ind in self.monitor_config.indicators
                                      if getattr(ind, 'time_increment', '1m') == timeframe]
            print(f"🔧 Indicators for {timeframe} timeframe: {[ind.name for ind in indicators_for_this_tf]}")

            # Calculate indicators using all available data
            print(f"🔧 Calling indicator_processor.calculate_indicators...")
            indicators, raw_indicators, bar_scores = self.indicator_processor.calculate_indicators(
                all_candle_data, timeframe  # Pass which timeframe just completed
            )

            print(f"🔧 ========== INDICATOR RESULTS ==========")
            print(f"🔧 Indicators: {indicators}")
            print(f"🔧 Raw indicators: {raw_indicators}")
            print(f"🔧 Bar scores: {bar_scores}")

            # Send results to external tools
            print(f"🔧 Sending to {len(self.external_tools)} external tools...")
            for i, tool in enumerate(self.external_tools):
                print(f"🔧 Sending to tool #{i}: {type(tool).__name__}")
                try:
                    tool.indicator_vector(
                        card_id=self.card_id,
                        symbol=self.symbol,
                        tick=completed_candle,
                        indicators=indicators,
                        bar_scores=bar_scores,
                        raw_indicators=raw_indicators
                    )
                    print(f"🔧 ✅ Successfully sent to tool #{i}")
                except Exception as tool_error:
                    print(f"🔧 ❌ Error sending to tool #{i}: {tool_error}")

            print(f"🔧 ========== CANDLE PROCESSING COMPLETE ==========")

        except Exception as e:
            logger.error(f"Error handling completed candle: {e}")
            print(f"🔧 ❌ ERROR in handle_completed_candle: {e}")
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

            # Debug logging
            print(
                f"🔧 Aggregator {timeframe}: {len(aggregator.get_history())} completed + {'1 current' if current else '0 current'} = {len(all_data[timeframe])} total")

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

            # Send to external tools (price update only)
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
        """
        Load historical data for all timeframes
        """
        print(f"🔧 LOADING HISTORICAL DATA for {self.symbol}")

        total_loaded = 0
        for timeframe, aggregator in self.aggregators.items():
            print(f"🔧 Loading {timeframe} data...")
            count = aggregator.prepopulate_data(data_link)
            total_loaded += count

            # Debug: Show what we loaded
            history = aggregator.get_history()
            if history:
                first_candle = history[0]
                last_candle = history[-1]
                print(f"🔧 ✅ {timeframe}: {count} candles loaded")
                print(f"🔧 Range: {first_candle.timestamp} to {last_candle.timestamp}")
                print(f"🔧 Price range: ${min(c.close for c in history):.2f} - ${max(c.close for c in history):.2f}")
            else:
                print(f"🔧 ❌ {timeframe}: No data loaded")

        logger.info(f"Loaded {total_loaded} total candles for {self.symbol}")
        print(f"🔧 HISTORICAL DATA LOADING COMPLETE: {total_loaded} total candles")

    def connect_tool(self, external_tool: ExternalTool) -> None:
        """Connect an external tool"""
        self.external_tools.append(external_tool)
        print(f"🔧 Connected external tool: {type(external_tool).__name__} (total: {len(self.external_tools)})")

    def get_symbol(self) -> str:
        """Get symbol"""
        return self.symbol

    def get_card_id(self) -> str:
        """Get card ID"""
        return self.card_id

    def debug_status(self) -> Dict:
        """Get debug status information"""
        status = {
            'card_id': self.card_id,
            'symbol': self.symbol,
            'pip_count': self.pip_count,
            'candle_completions': self.candle_completions,
            'external_tools_count': len(self.external_tools),
            'aggregators': {},
            'stored_indicators': {}
        }

        # Get aggregator status
        for timeframe, aggregator in self.aggregators.items():
            history = aggregator.get_history()
            current = aggregator.get_current_candle()
            status['aggregators'][timeframe] = {
                'history_count': len(history),
                'has_current': current is not None,
                'latest_timestamp': history[-1].timestamp.isoformat() if history else None,
                'latest_price': history[-1].close if history else None
            }

        # Get stored indicator values
        if hasattr(self.indicator_processor, 'stored_values'):
            for name, data in self.indicator_processor.stored_values.items():
                status['stored_indicators'][name] = {
                    'value': data['value'],
                    'raw_value': data['raw_value'],
                    'timestamp': data['timestamp'].isoformat(),
                    'timeframe': data['timeframe']
                }

        return status