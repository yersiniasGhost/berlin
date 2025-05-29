"""
Main application service that manages all trading components with simple ID routing
"""

import os
import sys
import json
import logging
import threading
from typing import Dict, List, Optional
from datetime import datetime
from flask_socketio import SocketIO

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
    Now using simple ID-based routing with MasterUIExternalTool
    """

    def __init__(self, socketio: SocketIO, auth_manager: SchwabAuthManager):
        self.socketio: SocketIO = socketio
        self.auth_manager: SchwabAuthManager = auth_manager

        # Core components
        self.data_link: Optional[SchwabDataLink] = None
        self.streaming_manager: Optional[StreamingManager] = None

        # Single master UI tool for all combinations
        self.master_ui_tool: MasterUIExternalTool = MasterUIExternalTool(socketio)

        # State tracking
        self.is_streaming: bool = False
        self.streaming_thread: Optional[threading.Thread] = None

        # Combination storage: combination_id -> TradingCombination
        self.combinations: Dict[str, TradingCombination] = {}

        logger.info("AppService initialized with simple ID routing")

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
        Add a new symbol + monitor config combination with simple ID routing
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

            # Create combination with automatic ID generation
            combination = TradingCombination(symbol, monitor_config, card_id)
            combination_id = combination.get_combination_id()

            # Check if combination already exists
            if combination_id in self.combinations:
                return {"success": False, "error": f"Combination {combination_id} already exists"}

            # Get required timeframes from monitor config
            timeframes = combination.get_timeframes()
            logger.info(f"Creating combination {combination_id} with timeframes: {timeframes}")

            # Create aggregators for this combination
            aggregators = {}
            for timeframe in timeframes:
                aggregator = CandleAggregator(symbol, timeframe)
                # Load historical data
                count = aggregator.prepopulate_data(self.data_link)
                aggregators[timeframe] = aggregator
                logger.info(f"Loaded {count} {timeframe} candles for {symbol}")

            # Register aggregators with streaming manager using unique key
            unique_key = combination.get_unique_aggregator_key()
            self.streaming_manager.aggregators[unique_key] = aggregators
            logger.info(f"Registered aggregators under unique key: {unique_key}")

            # Connect combination's DataStreamer to MasterUIExternalTool
            combination.connect_to_external_tool(self.master_ui_tool)
            logger.info(f"Connected {combination_id} to MasterUIExternalTool")

            # Register combination with master UI tool
            self.master_ui_tool.register_combination(combination_id, combination.get_metadata())

            # Store combination
            self.combinations[combination_id] = combination

            # Subscribe to quotes for this symbol
            self._ensure_symbol_subscription(symbol)

            # Process initial indicators
            logger.info(f"Processing initial indicators for {combination_id}")
            combination.process_indicators(aggregators)

            logger.info(f"Successfully added combination: {combination_id}")

            # Broadcast status update to all clients
            self.broadcast_status_update()

            return {
                "success": True,
                "combination_id": combination_id,
                "symbol": symbol,
                "monitor_config_name": monitor_config.name,
                "timeframes": list(timeframes),
                "card_id": combination_id
            }

        except Exception as e:
            logger.error(f"Error adding combination: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def remove_combination(self, combination_id: str) -> Dict:
        """Remove a combination"""
        try:
            if combination_id not in self.combinations:
                return {"success": False, "error": "Combination not found"}

            combination = self.combinations[combination_id]

            # Unregister from master UI tool
            self.master_ui_tool.unregister_combination(combination_id)

            # Remove aggregators from streaming manager
            unique_key = combination.get_unique_aggregator_key()
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
        combinations_list = []

        for combination_id, combination in self.combinations.items():
            combinations_list.append({
                "combination_id": combination_id,
                "symbol": combination.get_symbol(),
                "monitor_config_name": combination.monitor_config.name,
                "timeframes": list(combination.get_timeframes()),
                "card_id": combination_id
            })

        return {
            "combinations": combinations_list,
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
                    time_increment=ind_data.get('time_increment',