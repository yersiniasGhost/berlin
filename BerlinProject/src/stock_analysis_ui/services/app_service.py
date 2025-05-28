"""
Main application service that manages all trading components
"""

import os
import sys
import json
import logging
import threading
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime
from flask_socketio import SocketIO

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..', '..'))

from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.candle_aggregator import CandleAggregator
from data_streamer.data_streamer import DataStreamer
from models.monitor_configuration import MonitorConfiguration
from models.indicator_definition import IndicatorDefinition
from stock_analysis_ui.services.streaming_manager import StreamingManager
from stock_analysis_ui.services.ui_external_tool import UIExternalTool
from stock_analysis_ui.services.schwab_auth import SchwabAuthManager

logger = logging.getLogger('AppService')


class AppService:
    """
    Main service that coordinates all trading application components
    """

    def __init__(self, socketio: SocketIO, auth_manager: SchwabAuthManager):
        self.socketio: SocketIO = socketio
        self.auth_manager: SchwabAuthManager = auth_manager

        # Core components
        self.data_link: Optional[SchwabDataLink] = None
        self.streaming_manager: Optional[StreamingManager] = None
        self.ui_tool: Optional[UIExternalTool] = None

        # State tracking
        self.is_streaming: bool = False
        self.streaming_thread: Optional[threading.Thread] = None
        self.combinations: Dict[str, Dict] = {}  # combination_id -> metadata

        # Initialize UI tool
        self.ui_tool = UIExternalTool(socketio)

        logger.info("AppService initialized")

    def broadcast_status_update(self) -> None:
        """Broadcast current status to all connected clients"""
        try:
            combinations_data = self.get_combinations()
            status = {
                'streaming': self.is_streaming,
                'authenticated': self.auth_manager.is_authenticated() if self.auth_manager else True,
                'combinations': combinations_data.get('combinations', []),
                'total_combinations': combinations_data.get('total', 0),
                'timestamp': datetime.now().isoformat()
            }

            self.socketio.emit('status_update', status)
            logger.debug(f"Broadcasted status update: {status['total_combinations']} combinations, streaming: {status['streaming']}")

        except Exception as e:
            logger.error(f"Error broadcasting status: {e}")

    def start_streaming(self) -> bool:
        """Initialize streaming infrastructure (called once)"""
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

            # Create streaming manager
            self.streaming_manager = StreamingManager(self.data_link)

            # Set streaming flag BEFORE starting thread
            self.is_streaming = True
            logger.info("Set streaming flag to True")

            # Start background processing thread
            logger.info("Starting indicator processing thread...")
            self.streaming_thread = threading.Thread(target=self._process_indicators_loop, name="IndicatorProcessor")
            self.streaming_thread.daemon = True
            self.streaming_thread.start()

            # Give the thread a moment to start and verify it's running
            import time
            time.sleep(1.0)  # Wait a bit longer

            if self.streaming_thread.is_alive():
                logger.info("Indicator processing thread started successfully")
            else:
                logger.error("Indicator processing thread failed to start")
                self.is_streaming = False
                return False

            # Double-check by waiting a bit more and checking for the loop message
            time.sleep(1.0)
            logger.info("Streaming infrastructure started successfully")
            return True

        except Exception as e:
            logger.error(f"Error starting streaming: {e}")
            import traceback
            traceback.print_exc()
            self.is_streaming = False
            return False

    def debug_aggregator_data(self, symbol: str) -> None:
        """Debug method to check what data is in the aggregators"""
        if symbol not in self.streaming_manager.aggregators:
            logger.warning(f"No aggregators found for {symbol}")
            return

        symbol_aggregators = self.streaming_manager.aggregators[symbol]
        logger.info(f"=== Debug Aggregator Data for {symbol} ===")

        for timeframe, aggregator in symbol_aggregators.items():
            current_candle = aggregator.get_current_candle()
            history = aggregator.get_history()

            logger.info(f"{timeframe} timeframe:")
            logger.info(f"  History size: {len(history)}")

            if history:
                last_historical = history[-1]
                logger.info(f"  Last historical candle: ${last_historical.close:.2f} @ {last_historical.timestamp}")

            if current_candle:
                logger.info(f"  Current candle: ${current_candle.close:.2f} @ {current_candle.timestamp}")
                logger.info(f"  Current candle symbol: {getattr(current_candle, 'symbol', 'NOT SET')}")
            else:
                logger.info(f"  Current candle: None")

        logger.info("=== End Debug ===")

    def add_combination(self, symbol: str, config_file: str, card_id: Optional[str] = None) -> Dict:
        """
        Add a new symbol + monitor config combination

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            config_file: Path to monitor configuration JSON file
            card_id: Optional custom card ID

        Returns:
            Dict with success status and combination details
        """
    def add_combination(self, symbol: str, config_file: str, card_id: Optional[str] = None) -> Dict:
        """
        Add a new symbol + monitor config combination

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            config_file: Path to monitor configuration JSON file
            card_id: Optional custom card ID

        Returns:
            Dict with success status and combination details
        """
        try:
            # Streaming should already be started at app startup
            if not self.is_streaming:
                logger.warning("Streaming not active, attempting to start...")
                if not self.start_streaming():
                    return {"success": False, "error": "Failed to start streaming"}

            # Load monitor configuration
            monitor_config = self._load_monitor_config(config_file)
            if not monitor_config:
                return {"success": False, "error": f"Failed to load config: {config_file}"}

            # Generate combination ID if not provided
            if not card_id:
                card_id = f"{symbol}_{monitor_config.name}_{len(self.combinations)}"

            combination_id = card_id

            # Check if combination already exists
            if combination_id in self.combinations:
                return {"success": False, "error": f"Combination {combination_id} already exists"}

            # Get required timeframes from monitor config
            timeframes = monitor_config.get_time_increments()
            logger.info(f"Creating combination {combination_id} with timeframes: {timeframes}")

            # Create aggregators for this symbol/timeframes
            aggregators = {}
            for timeframe in timeframes:
                aggregator = CandleAggregator(symbol, timeframe)
                # Load historical data
                count = aggregator.prepopulate_data(self.data_link)
                aggregators[timeframe] = aggregator
                logger.info(f"Loaded {count} {timeframe} candles for {symbol}")

            # Create DataStreamer for this combination
            model_config = {"feature_vector": [{"name": "close"}]}
            data_streamer = DataStreamer(model_config, monitor_config)

            # CRITICAL: Connect the UIExternalTool to the DataStreamer
            data_streamer.connect_tool(self.ui_tool)
            logger.info(f"Connected UIExternalTool to DataStreamer for {symbol}")

            # Register combination with UI tool
            actual_combination_id = self.ui_tool.register_combination(
                data_streamer=data_streamer,
                symbol=symbol,
                monitor_config=monitor_config,
                card_id=card_id
            )

            # NOW create the unique key using the actual combination ID
            unique_symbol_key = f"{symbol}_{actual_combination_id}"

            # Register aggregators with streaming manager - DON'T OVERWRITE EXISTING ONES
            # Each combination gets its own unique aggregators
            self.streaming_manager.aggregators[unique_symbol_key] = aggregators
            logger.info(f"Registered aggregators under unique key: {unique_symbol_key}")

            # ALSO keep them in the symbol-based aggregators for live data routing
            if symbol not in self.streaming_manager.aggregators:
                self.streaming_manager.aggregators[symbol] = {}
            # Don't overwrite - just ensure we have some aggregators for live data
            if not self.streaming_manager.aggregators[symbol]:
                self.streaming_manager.aggregators[symbol] = aggregators

            # Store combination metadata with unique aggregator key
            self.combinations[actual_combination_id] = {
                'symbol': symbol,
                'config_file': config_file,
                'monitor_config': monitor_config,
                'data_streamer': data_streamer,
                'aggregators': aggregators,
                'timeframes': timeframes,
                'card_id': card_id,
                'unique_symbol_key': unique_symbol_key  # Track the unique key
            }

            # Subscribe to quotes for this symbol if not already subscribed
            self._ensure_symbol_subscription(symbol)

            # Populate initial data from historical candles
            logger.info(f"Populating initial data for {actual_combination_id}")
            self.ui_tool.populate_initial_data(actual_combination_id, aggregators)

            # Process indicators once to get initial values
            # Use the unique aggregators for this specific combination
            unique_symbol_key = f"{symbol}_{actual_combination_id}"
            if unique_symbol_key in self.streaming_manager.aggregators:
                unique_aggregators = self.streaming_manager.aggregators[unique_symbol_key]
                logger.info(f"Processing initial indicators for {actual_combination_id} using {unique_symbol_key}")
                data_streamer.process_tick(unique_aggregators)

            logger.info(f"Successfully added combination: {actual_combination_id}")

            # Broadcast status update to all clients
            self.broadcast_status_update()

            return {
                "success": True,
                "combination_id": actual_combination_id,
                "symbol": symbol,
                "monitor_config_name": monitor_config.name,
                "timeframes": list(timeframes),
                "card_id": card_id
            }

        except Exception as e:
            logger.error(f"Error adding combination: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

            # Load monitor configuration
            monitor_config = self._load_monitor_config(config_file)
            if not monitor_config:
                return {"success": False, "error": f"Failed to load config: {config_file}"}

            # Generate combination ID if not provided
            if not card_id:
                card_id = f"{symbol}_{monitor_config.name}_{len(self.combinations)}"

            combination_id = card_id

            # Check if combination already exists
            if combination_id in self.combinations:
                return {"success": False, "error": f"Combination {combination_id} already exists"}

            # Get required timeframes from monitor config
            timeframes = monitor_config.get_time_increments()
            logger.info(f"Creating combination {combination_id} with timeframes: {timeframes}")

            # Create aggregators for this symbol/timeframes
            aggregators = {}
            for timeframe in timeframes:
                aggregator = CandleAggregator(symbol, timeframe)
                # Load historical data
                count = aggregator.prepopulate_data(self.data_link)
                aggregators[timeframe] = aggregator
                logger.info(f"Loaded {count} {timeframe} candles for {symbol}")

            # Register aggregators with streaming manager
            if symbol not in self.streaming_manager.aggregators:
                self.streaming_manager.aggregators[symbol] = {}
            self.streaming_manager.aggregators[symbol].update(aggregators)

            # Create DataStreamer for this combination
            model_config = {"feature_vector": [{"name": "close"}]}
            data_streamer = DataStreamer(model_config, monitor_config)

            # Register combination with UI tool
            actual_combination_id = self.ui_tool.register_combination(
                data_streamer=data_streamer,
                symbol=symbol,
                monitor_config=monitor_config,
                card_id=card_id
            )

            # Store combination metadata
            self.combinations[actual_combination_id] = {
                'symbol': symbol,
                'config_file': config_file,
                'monitor_config': monitor_config,
                'data_streamer': data_streamer,
                'aggregators': aggregators,
                'timeframes': timeframes,
                'card_id': card_id
            }

            # Subscribe to quotes for this symbol if not already subscribed
            self._ensure_symbol_subscription(symbol)

            # Populate initial data from historical candles
            logger.info(f"Populating initial data for {actual_combination_id}")
            self.ui_tool.populate_initial_data(actual_combination_id, aggregators)

            # Process indicators once to get initial values
            if symbol in self.streaming_manager.aggregators:
                symbol_aggregators = self.streaming_manager.aggregators[symbol]
                logger.info(f"Processing initial indicators for {actual_combination_id}")
                data_streamer.process_tick(symbol_aggregators)

            logger.info(f"Successfully added combination: {actual_combination_id}")

            # Broadcast status update to all clients
            self.broadcast_status_update()

            return {
                "success": True,
                "combination_id": actual_combination_id,
                "symbol": symbol,
                "monitor_config_name": monitor_config.name,
                "timeframes": list(timeframes),
                "card_id": card_id
            }

        except Exception as e:
            logger.error(f"Error adding combination: {e}")
            return {"success": False, "error": str(e)}

    def remove_combination(self, combination_id: str) -> Dict:
        """Remove a combination"""
        try:
            if combination_id not in self.combinations:
                return {"success": False, "error": "Combination not found"}

            combo_data = self.combinations[combination_id]
            data_streamer = combo_data['data_streamer']

            # Unregister from UI tool
            self.ui_tool.unregister_combination(data_streamer)

            # Remove from combinations
            del self.combinations[combination_id]

            logger.info(f"Removed combination: {combination_id}")
            return {"success": True}

        except Exception as e:
            logger.error(f"Error removing combination: {e}")
            return {"success": False, "error": str(e)}

    def get_combinations(self) -> Dict:
        """Get all active combinations"""
        return {
            "combinations": [
                {
                    "combination_id": comb_id,
                    "symbol": data["symbol"],
                    "monitor_config_name": data["monitor_config"].name,
                    "timeframes": list(data["timeframes"]),
                    "card_id": data["card_id"]
                }
                for comb_id, data in self.combinations.items()
            ],
            "total": len(self.combinations)
        }

    def get_available_configs(self) -> List[str]:
        """Get available monitor configuration files"""
        config_files = []

        # Look in current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_dirs = [
            os.path.join(current_dir, '..'),  # Parent directory
            os.path.join(current_dir, '..', '..'),  # Stock analysis UI directory
            '.'  # Current directory
        ]

        for config_dir in config_dirs:
            if os.path.exists(config_dir):
                for file in os.listdir(config_dir):
                    if file.endswith('.json') and 'monitor_config' in file.lower():
                        if file not in config_files:  # Avoid duplicates
                            config_files.append(file)

        # Add default if none found
        if not config_files:
            config_files = ['monitor_config_example_time_intervals.json']

        return sorted(config_files)

    def stop_streaming(self) -> bool:
        """Stop all streaming"""
        try:
            self.is_streaming = False

            if self.data_link:
                self.data_link.disconnect()

            if self.streaming_thread:
                self.streaming_thread.join(timeout=2)

            logger.info("Streaming stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
            return False

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

    def _ensure_symbol_subscription(self, symbol: str) -> None:
        """Ensure we're subscribed to quotes for this symbol"""
        try:
            # Subscribe to quotes for real-time price updates
            self.data_link.subscribe_quotes([symbol])

            # Set up quote handler if not already done
            if self.streaming_manager.route_pip_data not in self.data_link.quote_handlers:
                self.data_link.add_quote_handler(self.streaming_manager.route_pip_data)

            logger.info(f"Ensured subscription for symbol: {symbol}")

        except Exception as e:
            logger.error(f"Error subscribing to symbol {symbol}: {e}")

    def _process_indicators_loop(self) -> None:
        """Background thread to process indicators"""
        while self.is_streaming:
            try:
                # Process indicators for each combination
                for combination_id, combo_data in self.combinations.items():
                    symbol = combo_data['symbol']
                    data_streamer = combo_data['data_streamer']

                    # Get aggregators for this symbol
                    if symbol in self.streaming_manager.aggregators:
                        symbol_aggregators = self.streaming_manager.aggregators[symbol]

                        # Process indicators - this will call ui_tool.indicator_vector
                        data_streamer.process_tick(symbol_aggregators)

                import time
                time.sleep(2)  # Process every 2 seconds

            except Exception as e:
                logger.error(f"Error in indicator processing loop: {e}")
                import time
                time.sleep(5)  # Wait before retrying