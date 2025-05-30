# File: BerlinProject/src/stock_analysis_ui/services/app_service.py
# UPDATED VERSION with proper candle aggregation

"""
Simplified application service with proper candle aggregation
"""

import os
import sys
import json
import logging
import threading
from typing import Dict, List, Optional
from datetime import datetime
from flask_socketio import SocketIO
from collections import defaultdict

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..', '..'))

from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.data_streamer import DataStreamer
from data_streamer.candle_aggregator import CandleAggregator
from models.monitor_configuration import MonitorConfiguration
from models.indicator_definition import IndicatorDefinition
from stock_analysis_ui.services.ui_external_tool import UIExternalTool
from stock_analysis_ui.services.schwab_auth import SchwabAuthManager

logger = logging.getLogger('AppService')


class AppService:
    """
    Simplified application service with proper candle aggregation
    """

    def __init__(self, socketio: SocketIO, auth_manager: SchwabAuthManager):
        self.socketio: SocketIO = socketio
        self.auth_manager: SchwabAuthManager = auth_manager

        # Core components
        self.data_link: Optional[SchwabDataLink] = None
        self.ui_tool: UIExternalTool = UIExternalTool(socketio)

        # Simple state tracking
        self.is_streaming: bool = False
        self.combinations: Dict[str, Dict] = {}  # card_id -> combination data
        self.card_counter: int = 0
        self.subscribed_symbols: set = set()

        # Candle aggregators: symbol -> {timeframe -> CandleAggregator}
        self.aggregators: Dict[str, Dict[str, CandleAggregator]] = defaultdict(dict)

        logger.info("AppService initialized - simplified version with candle aggregation")

    def start_streaming(self) -> bool:
        """Initialize streaming infrastructure"""
        if self.is_streaming:
            logger.info("Streaming already active")
            return True

        try:
            logger.info("Starting streaming infrastructure...")

            # Setup data link
            self.data_link = SchwabDataLink()
            self.data_link.access_token = self.auth_manager.access_token
            self.data_link.refresh_token = self.auth_manager.refresh_token
            self.data_link.user_prefs = self.auth_manager.user_prefs

            if not self.data_link.connect_stream():
                logger.error("Failed to connect to Schwab streaming")
                return False

            self.is_streaming = True
            logger.info("Streaming infrastructure started successfully")
            return True

        except Exception as e:
            logger.error(f"Error starting streaming: {e}")
            import traceback
            traceback.print_exc()
            self.is_streaming = False
            return False

    def add_combination(self, symbol: str, config_file: str) -> Dict:
        """
        Add a new combination with proper candle aggregation
        """
        try:
            if not self.is_streaming:
                if not self.start_streaming():
                    return {"success": False, "error": "Failed to start streaming"}

            # Auto-generate card ID
            self.card_counter += 1
            card_id = f"card{self.card_counter}"

            # Load monitor configuration
            monitor_config = self._load_monitor_config(config_file)
            if not monitor_config:
                return {"success": False, "error": f"Failed to load config: {config_file}"}

            logger.info(f"Creating combination {card_id} for {symbol}")

            # Get required timeframes from indicators
            timeframes = monitor_config.get_time_increments()
            logger.info(f"Required timeframes for {symbol}: {timeframes}")

            # Create aggregators for each required timeframe
            if symbol not in self.aggregators:
                self.aggregators[symbol] = {}

            for timeframe in timeframes:
                if timeframe not in self.aggregators[symbol]:
                    aggregator = CandleAggregator(symbol, timeframe)
                    # Load historical data
                    count = aggregator.prepopulate_data(self.data_link)
                    self.aggregators[symbol][timeframe] = aggregator
                    logger.info(f"Created aggregator for {symbol}-{timeframe}, loaded {count} candles")

            # Create simple DataStreamer
            data_streamer = DataStreamer(
                card_id=card_id,
                symbol=symbol,
                monitor_config=monitor_config
            )

            # Connect UI tool
            data_streamer.connect_tool(self.ui_tool)

            # Store combination
            self.combinations[card_id] = {
                'card_id': card_id,
                'symbol': symbol,
                'config_file': config_file,
                'monitor_config': monitor_config,
                'data_streamer': data_streamer,
                'timeframes': timeframes
            }

            # Subscribe to quotes for this symbol (only once per symbol)
            self._ensure_symbol_subscription(symbol)

            # Send initial data to UI
            self._send_initial_data(card_id, symbol)

            logger.info(f"Successfully added combination: {card_id} ({symbol})")

            return {
                "success": True,
                "card_id": card_id,
                "symbol": symbol,
                "monitor_config_name": monitor_config.name
            }

        except Exception as e:
            logger.error(f"Error adding combination: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def _send_initial_data(self, card_id: str, symbol: str):
        """Send initial price data to UI"""
        try:
            # Get current price from any aggregator
            current_price = 0.0
            for timeframe, aggregator in self.aggregators[symbol].items():
                current_candle = aggregator.get_current_candle()
                if current_candle and current_candle.close > 0:
                    current_price = current_candle.close
                    break

            if current_price > 0:
                # Send initial price update
                self.ui_tool.price_update(
                    card_id=card_id,
                    symbol=symbol,
                    tick=self._create_mock_tick(symbol, current_price)
                )
                logger.info(f"Sent initial price for {card_id}: ${current_price:.2f}")
        except Exception as e:
            logger.error(f"Error sending initial data for {card_id}: {e}")

    def _create_mock_tick(self, symbol: str, price: float):
        """Create a mock tick for initial data"""
        from environments.tick_data import TickData
        return TickData(
            symbol=symbol,
            timestamp=datetime.now(),
            open=price,
            high=price,
            low=price,
            close=price,
            volume=1000,
            time_increment="1m"
        )

    def remove_combination(self, card_id: str) -> Dict:
        """Remove a combination"""
        try:
            if card_id not in self.combinations:
                return {"success": False, "error": "Combination not found"}

            del self.combinations[card_id]
            logger.info(f"Removed combination: {card_id}")

            return {"success": True}

        except Exception as e:
            logger.error(f"Error removing combination: {e}")
            return {"success": False, "error": str(e)}

    def get_combinations(self) -> Dict:
        """Get all active combinations"""
        return {
            "combinations": [
                {
                    "card_id": card_id,
                    "symbol": data["symbol"],
                    "monitor_config_name": data["monitor_config"].name
                }
                for card_id, data in self.combinations.items()
            ],
            "total": len(self.combinations)
        }

    def _ensure_symbol_subscription(self, symbol: str):
        """Subscribe to quotes for symbol and set up PIP processing"""
        try:
            if symbol not in self.subscribed_symbols:
                # Subscribe to ALL symbols at once to avoid replacement
                self.subscribed_symbols.add(symbol)
                all_symbols = list(self.subscribed_symbols)

                logger.info(f"Subscribing to all symbols: {all_symbols}")
                self.data_link.subscribe_quotes(all_symbols)

                # Set up quote handler for this symbol (only once)
                def quote_handler(quote_data):
                    if quote_data.get('key') == symbol:
                        self._process_pip_for_symbol(symbol, quote_data)

                self.data_link.add_quote_handler(quote_handler)
                logger.info(f"Added quote handler for {symbol}")

        except Exception as e:
            logger.error(f"Error subscribing to symbol {symbol}: {e}")

    def _process_pip_for_symbol(self, symbol: str, quote_data: Dict):
        """Process PIP data for a symbol - aggregate into candles"""
        try:
            # Process PIP through all aggregators for this symbol
            if symbol in self.aggregators:
                for timeframe, aggregator in self.aggregators[symbol].items():
                    # Process PIP and check if candle completed
                    completed_candle = aggregator.process_pip(quote_data)

                    if completed_candle:
                        logger.info(f"Completed {timeframe} candle for {symbol}: ${completed_candle.close:.2f}")
                        # Process indicators for combinations that use this timeframe
                        self._process_completed_candle(symbol, timeframe, completed_candle)

            # Also send current price updates to UI (for real-time price display)
            self._send_current_price_updates(symbol, quote_data)

        except Exception as e:
            logger.error(f"Error processing PIP for {symbol}: {e}")

    def _process_completed_candle(self, symbol: str, timeframe: str, completed_candle):
        """Process indicators when a candle completes"""
        try:
            # Find combinations that use this symbol and have indicators for this timeframe
            for card_id, combination in self.combinations.items():
                if combination['symbol'] == symbol:
                    # Check if this combination has indicators for this timeframe
                    has_timeframe_indicators = any(
                        getattr(ind, 'time_increment', '1m') == timeframe
                        for ind in combination['monitor_config'].indicators
                    )

                    if has_timeframe_indicators:
                        logger.info(f"Processing indicators for {card_id} on {timeframe} candle completion")

                        # Get all historical data for this combination's timeframes
                        historical_data = self._get_historical_data_for_combination(symbol, combination['timeframes'])

                        # DEBUG: Check what we're passing
                        logger.info(f"🔍 Passing {len(historical_data)} historical candles to {card_id}")
                        if historical_data:
                            logger.info(
                                f"🔍 Sample candle: {historical_data[-1].symbol} @ ${historical_data[-1].close:.2f}")

                        # Process indicators
                        data_streamer = combination['data_streamer']
                        data_streamer.process_candle_completion(historical_data, completed_candle)

        except Exception as e:
            logger.error(f"Error processing completed candle: {e}")
            import traceback
            traceback.print_exc()

    def _send_current_price_updates(self, symbol: str, quote_data: Dict):
        """Send current price updates to UI for real-time display"""
        try:
            # Extract price from quote
            price = None
            for field in ['3', '2', '1', '5']:
                if field in quote_data:
                    try:
                        price = float(quote_data[field])
                        if price > 0:
                            break
                    except:
                        continue

            if not price:
                return

            # Create current tick
            current_tick = self._create_mock_tick(symbol, price)

            # Send to all combinations with this symbol
            for card_id, combination in self.combinations.items():
                if combination['symbol'] == symbol:
                    self.ui_tool.price_update(
                        card_id=card_id,
                        symbol=symbol,
                        tick=current_tick
                    )

        except Exception as e:
            logger.error(f"Error sending current price updates: {e}")

    def _get_historical_data_for_combination(self, symbol: str, timeframes: set) -> List:
        """Get historical data for all timeframes used by a combination"""
        historical_data = []

        for timeframe in timeframes:
            if symbol in self.aggregators and timeframe in self.aggregators[symbol]:
                aggregator = self.aggregators[symbol][timeframe]
                history = aggregator.get_history()
                historical_data.extend(history)
                logger.info(f"🔍 Added {len(history)} {timeframe} candles for {symbol}")

        # Sort by timestamp
        historical_data.sort(key=lambda x: x.timestamp)
        logger.info(f"🔍 Total historical data for {symbol}: {len(historical_data)} candles")
        return historical_data

    def _load_monitor_config(self, config_file: str) -> Optional[MonitorConfiguration]:
        """Load monitor configuration from JSON file"""
        try:
            # Try different paths
            possible_paths = [
                config_file,
                os.path.join(os.path.dirname(__file__), '..', config_file),
                os.path.join(os.path.dirname(__file__), '..', '..', config_file)
            ]

            config_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break

            if not config_path:
                logger.error(f"Config file not found: {config_file}")
                return None

            with open(config_path, 'r') as f:
                config_data = json.load(f)

            # Extract monitor and indicators
            monitor_data = config_data.get('monitor', {})
            indicators_data = config_data.get('indicators', [])

            # Create IndicatorDefinition objects
            indicators = []
            for ind_data in indicators_data:
                indicator = IndicatorDefinition(
                    name=ind_data['name'],
                    type=ind_data['type'],
                    function=ind_data['function'],
                    parameters=ind_data['parameters'],
                    time_increment=ind_data.get('time_increment', '1m')
                )
                indicators.append(indicator)

            # Create MonitorConfiguration
            monitor_config = MonitorConfiguration(
                name=monitor_data.get('name', 'Trading Signals'),
                indicators=indicators
            )

            # Add bars if present
            if 'bars' in monitor_data:
                monitor_config.bars = monitor_data['bars']

            logger.info(f"Loaded monitor config: {monitor_config.name} with {len(indicators)} indicators")
            return monitor_config

        except Exception as e:
            logger.error(f"Error loading monitor config: {e}")
            return None

    def get_available_configs(self) -> List[str]:
        """Get available monitor configuration files"""
        config_files = []

        # Look in current directory and parent directories
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_dirs = [
            os.path.join(current_dir, '..'),
            os.path.join(current_dir, '..', '..'),
            '.'
        ]

        for config_dir in config_dirs:
            if os.path.exists(config_dir):
                for file in os.listdir(config_dir):
                    if file.endswith('.json') and ('monitor' in file.lower() or 'config' in file.lower()):
                        if file not in config_files:
                            config_files.append(file)

        if not config_files:
            config_files = ['monitor_config_example_time_intervals.json']

        return sorted(config_files)

    def stop_streaming(self) -> bool:
        """Stop all streaming"""
        try:
            self.is_streaming = False

            if self.data_link:
                self.data_link.disconnect()

            logger.info("Streaming stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
            return False