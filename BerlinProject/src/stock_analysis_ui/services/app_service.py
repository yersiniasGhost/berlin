"""
Main application service that manages all trading components with simple ID-based routing
"""

import os
import sys
import json
import logging
import threading
from typing import Dict, List, Optional
from datetime import datetime
from flask_socketio import SocketIO
import time

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..', '..'))

from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.candle_aggregator import CandleAggregator
from models.monitor_configuration import MonitorConfiguration
from models.indicator_definition import IndicatorDefinition
from stock_analysis_ui.services.streaming_manager import StreamingManager
from stock_analysis_ui.services.master_ui_external_tool import MasterUIExternalTool
from stock_analysis_ui.services.trading_combination import TradingCombination
from stock_analysis_ui.services.schwab_auth import SchwabAuthManager

logger = logging.getLogger('AppService')


class AppService:
    """
    Main service that coordinates all trading application components
    Uses simple ID-based routing for combinations
    """

    def __init__(self, socketio: SocketIO, auth_manager: SchwabAuthManager):
        self.socketio: SocketIO = socketio
        self.auth_manager: SchwabAuthManager = auth_manager

        # Core components
        self.data_link: Optional[SchwabDataLink] = None
        self.streaming_manager: Optional[StreamingManager] = None
        self.master_ui_tool: Optional[MasterUIExternalTool] = None

        # State tracking
        self.is_streaming: bool = False
        self.streaming_thread: Optional[threading.Thread] = None

        # Simple combination storage: combination_id -> TradingCombination
        self.combinations: Dict[str, TradingCombination] = {}

        # Initialize Master UI tool
        self.master_ui_tool = MasterUIExternalTool(socketio)

        # Track subscribed symbols to avoid duplicate subscriptions
        self.subscribed_symbols: set = set()

        logger.info("AppService initialized with simple ID-based routing")

    def broadcast_status_update(self) -> None:
        """Broadcast current status to all connected clients"""
        try:
            status = {
                'streaming': self.is_streaming,
                'authenticated': self.auth_manager.is_authenticated() if self.auth_manager else True,
                'combinations': [
                    {
                        'combination_id': combo.combination_id,
                        'symbol': combo.symbol,
                        'monitor_config_name': combo.monitor_config.name,
                        'timeframes': list(combo.timeframes),
                        'card_id': combo.card_id
                    }
                    for combo in self.combinations.values()
                ],
                'total_combinations': len(self.combinations),
                'timestamp': datetime.now().isoformat()
            }

            self.socketio.emit('status_update', status)
            logger.debug(f"Broadcasted status: {status['total_combinations']} combinations, streaming: {status['streaming']}")

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

            # Start background indicator processing thread
            logger.info("Starting indicator processing thread...")
            self.streaming_thread = threading.Thread(target=self._process_indicators_loop, name="IndicatorProcessor")
            self.streaming_thread.daemon = True
            self.streaming_thread.start()

            # Give the thread a moment to start
            import time
            time.sleep(1.0)

            if self.streaming_thread.is_alive():
                logger.info("Indicator processing thread started successfully")
            else:
                logger.error("Indicator processing thread failed to start")
                self.is_streaming = False
                return False

            logger.info("Streaming infrastructure started successfully")
            return True

        except Exception as e:
            logger.error(f"Error starting streaming: {e}")
            import traceback
            traceback.print_exc()
            self.is_streaming = False
            return False

    def add_combination(self, symbol: str, config_file: str, card_id: Optional[str] = None) -> Dict:
        """
        Add a new symbol + monitor config combination with simple ID-based routing

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

            # Create TradingCombination wrapper - this generates unique IDs automatically
            trading_combination = TradingCombination(
                symbol=symbol,
                monitor_config=monitor_config,
                config_file=config_file,
                card_id=card_id
            )

            combination_id = trading_combination.combination_id

            # Check if combination already exists
            if combination_id in self.combinations:
                return {"success": False, "error": f"Combination {combination_id} already exists"}

            logger.info(f"Creating combination {combination_id} with timeframes: {trading_combination.timeframes}")

            # Create aggregators for this combination's unique aggregator key
            aggregators = {}
            for timeframe in trading_combination.timeframes:
                aggregator = CandleAggregator(symbol, timeframe)
                # Load historical data
                count = aggregator.prepopulate_data(self.data_link)
                aggregators[timeframe] = aggregator
                logger.info(f"Loaded {count} {timeframe} candles for {symbol} (combination: {combination_id})")

            # Store aggregators in trading combination
            trading_combination.aggregators = aggregators

            # Register unique aggregators with streaming manager using unique key
            unique_key = trading_combination.unique_aggregator_key
            self.streaming_manager.aggregators[unique_key] = aggregators
            logger.info(f"Registered aggregators under unique key: {unique_key}")

            # ALSO register under symbol for live data routing (shared by all combinations of same symbol)
            if symbol not in self.streaming_manager.aggregators:
                self.streaming_manager.aggregators[symbol] = {}
            # Update with latest aggregators for this symbol
            self.streaming_manager.aggregators[symbol].update(aggregators)

            # Create DataStreamer with combination_id for routing
            data_streamer = trading_combination.create_data_streamer()

            # Connect MasterUIExternalTool to DataStreamer
            data_streamer.connect_tool(self.master_ui_tool)
            logger.info(f"Connected MasterUIExternalTool to DataStreamer for {combination_id}")

            # Register combination with MasterUIExternalTool
            self.master_ui_tool.register_combination(
                combination_id=combination_id,
                symbol=symbol,
                monitor_config=monitor_config,
                card_id=trading_combination.card_id
            )

            # Store combination
            self.combinations[combination_id] = trading_combination

            # Subscribe to quotes for this symbol if not already subscribed
            self._ensure_symbol_subscription(symbol)

            # Populate initial data from historical candles
            logger.info(f"Populating initial data for {combination_id}")
            self.master_ui_tool.populate_initial_data(combination_id, aggregators)

            # Process indicators once to get initial values using unique aggregators
            logger.info(f"Processing initial indicators for {combination_id}")
            data_streamer.process_tick(aggregators)

            logger.info(f"Successfully added combination: {combination_id}")

            # Broadcast status update to all clients
            self.broadcast_status_update()

            return {
                "success": True,
                "combination_id": combination_id,
                "symbol": symbol,
                "monitor_config_name": monitor_config.name,
                "timeframes": list(trading_combination.timeframes),
                "card_id": trading_combination.card_id
            }

        except Exception as e:
            logger.error(f"Error adding combination: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def remove_combination(self, combination_id: str) -> Dict:
        """Remove a combination using simple ID-based routing"""
        try:
            if combination_id not in self.combinations:
                return {"success": False, "error": "Combination not found"}

            trading_combination = self.combinations[combination_id]

            # Unregister from MasterUIExternalTool
            self.master_ui_tool.unregister_combination(combination_id)

            # Remove unique aggregators from streaming manager
            unique_key = trading_combination.unique_aggregator_key
            if unique_key in self.streaming_manager.aggregators:
                del self.streaming_manager.aggregators[unique_key]
                logger.info(f"Removed aggregators for key: {unique_key}")

            # Remove from combinations
            del self.combinations[combination_id]

            logger.info(f"Removed combination: {combination_id}")

            # Broadcast status update
            self.broadcast_status_update()

            return {"success": True}

        except Exception as e:
            logger.error(f"Error removing combination: {e}")
            return {"success": False, "error": str(e)}

    def get_combinations(self) -> Dict:
        """Get all active combinations"""
        return {
            "combinations": [
                {
                    "combination_id": combo.combination_id,
                    "symbol": combo.symbol,
                    "monitor_config_name": combo.monitor_config.name,
                    "timeframes": list(combo.timeframes),
                    "card_id": combo.card_id
                }
                for combo in self.combinations.values()
            ],
            "total": len(self.combinations)
        }

    def get_combination_data(self, combination_id: str) -> Optional[Dict]:
        """Get data for a specific combination"""
        if self.master_ui_tool:
            return self.master_ui_tool.get_combination_data(combination_id)
        return None

    def get_available_configs(self) -> List[str]:
        """Get available monitor configuration files"""
        config_files = []

        # Look in current directory and parent directories
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_dirs = [
            os.path.join(current_dir, '..'),  # Parent directory
            os.path.join(current_dir, '..', '..'),  # Project root
            '.'  # Current directory
        ]

        for config_dir in config_dirs:
            if os.path.exists(config_dir):
                for file in os.listdir(config_dir):
                    if file.endswith('.json') and ('monitor' in file.lower() or 'config' in file.lower()):
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

            if self.streaming_thread and self.streaming_thread.is_alive():
                self.streaming_thread.join(timeout=2)

            logger.info("Streaming stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
            return False

    def debug_live_data_flow(self) -> None:
        """Debug method to check live data flow"""
        logger.info("=== DEBUG LIVE DATA FLOW ===")
        logger.info(f"Streaming active: {self.is_streaming}")
        logger.info(f"Total combinations: {len(self.combinations)}")

        for combination_id, combo in self.combinations.items():
            logger.info(f"Combination {combination_id}:")
            logger.info(f"  Symbol: {combo.symbol}")
            logger.info(f"  Unique key: {combo.unique_aggregator_key}")
            logger.info(f"  Timeframes: {combo.timeframes}")

            # Check aggregators
            if combo.unique_aggregator_key in self.streaming_manager.aggregators:
                aggregators = self.streaming_manager.aggregators[combo.unique_aggregator_key]
                for timeframe, aggregator in aggregators.items():
                    current_candle = aggregator.get_current_candle()
                    history_size = len(aggregator.get_history())
                    logger.info(f"    {timeframe}: {history_size} historical, current: ${current_candle.close:.2f}" if current_candle else f"    {timeframe}: {history_size} historical, no current candle")

        logger.info("=== END DEBUG ===")

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
            if symbol not in self.subscribed_symbols:
                logger.info(f"🔔 SUBSCRIBING to new symbol: {symbol}")
                self.data_link.subscribe_quotes([symbol])

                # Set up quote handler if not already done
                if self.streaming_manager.route_pip_data not in self.data_link.quote_handlers:
                    self.data_link.add_quote_handler(self.streaming_manager.route_pip_data)
                    logger.info("🔗 Added quote handler to data_link")

                self.subscribed_symbols.add(symbol)
                logger.info(f"✅ Successfully subscribed to symbol: {symbol}")
            else:
                logger.info(f"⚡ Already subscribed to symbol: {symbol}")

            # Debug: Show all subscribed symbols
            logger.info(f"📊 All subscribed symbols: {list(self.subscribed_symbols)}")

        except Exception as e:
            logger.error(f"❌ Error subscribing to symbol {symbol}: {e}")

    def debug_process_all_combinations(self) -> Dict:
        """Debug method to manually process all combinations"""
        try:
            if not self.is_streaming:
                return {"success": False, "error": "Streaming not active"}

            processed_count = 0
            results = []

            logger.info(f"=== DEBUG PROCESS: Processing {len(self.combinations)} combinations ===")

            for combination_id, trading_combination in self.combinations.items():
                try:
                    logger.info(f"DEBUG: Processing combination {combination_id} ({trading_combination.symbol})")

                    # Get unique aggregators for this combination
                    aggregators = trading_combination.aggregators
                    if not aggregators:
                        logger.warning(f"DEBUG: No aggregators for {combination_id}")
                        results.append({
                            'combination_id': combination_id,
                            'symbol': trading_combination.symbol,
                            'processed': False,
                            'error': 'No aggregators'
                        })
                        continue

                    # Log aggregator status
                    for timeframe, aggregator in aggregators.items():
                        current_candle = aggregator.get_current_candle()
                        if current_candle:
                            logger.info(f"DEBUG: {timeframe} current candle: ${current_candle.close:.2f}")
                        else:
                            logger.info(f"DEBUG: {timeframe} no current candle")

                    # Process indicators using combination's DataStreamer
                    data_streamer = trading_combination.data_streamer
                    if data_streamer:
                        logger.info(f"DEBUG: Calling data_streamer.process_tick() for {combination_id}")
                        data_streamer.process_tick(aggregators)
                        processed_count += 1

                        results.append({
                            'combination_id': combination_id,
                            'symbol': trading_combination.symbol,
                            'processed': True
                        })
                    else:
                        logger.warning(f"DEBUG: No data_streamer for {combination_id}")
                        results.append({
                            'combination_id': combination_id,
                            'symbol': trading_combination.symbol,
                            'processed': False,
                            'error': 'No data_streamer'
                        })

                except Exception as e:
                    logger.error(f"DEBUG: Error processing {combination_id}: {e}")
                    results.append({
                        'combination_id': combination_id,
                        'symbol': trading_combination.symbol,
                        'processed': False,
                        'error': str(e)
                    })

            logger.info(f"=== DEBUG PROCESS COMPLETE: {processed_count} processed ===")

            return {
                "success": True,
                "processed_count": processed_count,
                "total_combinations": len(self.combinations),
                "results": results
            }

        except Exception as e:
            logger.error(f"Error in debug processing: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def _process_indicators_loop(self):
        while self.is_streaming:
            for combination_id, trading_combination in self.combinations.items():
                # Get THIS combination's unique aggregators
                unique_key = trading_combination.unique_aggregator_key
                live_aggregators = self.streaming_manager.aggregators[unique_key]

                # Process indicators for THIS specific combination
                trading_combination.data_streamer.process_tick(live_aggregators)

            time.sleep(2)