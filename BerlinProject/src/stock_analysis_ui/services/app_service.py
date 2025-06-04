"""
Simplified application service - each DataStreamer owns its aggregators
"""

import os
import json
import logging
from typing import Dict, List, Optional
from flask_socketio import SocketIO

from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.data_streamer import DataStreamer
from models.monitor_configuration import MonitorConfiguration
from models.indicator_definition import IndicatorDefinition
from stock_analysis_ui.services.ui_external_tool import UIExternalTool
from stock_analysis_ui.services.schwab_auth import SchwabAuthManager


logger = logging.getLogger('AppService')


class AppService:
    """
    Simplified application service - DataStreamers own their aggregators
    """

    def __init__(self, socketio: SocketIO, auth_manager: SchwabAuthManager):
        self.socketio: SocketIO = socketio
        self.auth_manager: SchwabAuthManager = auth_manager

        # Core components
        self.data_link: Optional[SchwabDataLink] = None
        self.ui_tool: UIExternalTool = UIExternalTool(socketio)

        # State tracking
        self.is_streaming: bool = False
        self.combinations: Dict[str, Dict] = {}  # card_id -> {data_streamer, symbol, etc}
        self.card_counter: int = 0
        self.subscribed_symbols: set = set()

        logger.info("Simplified AppService initialized")

    def start_streaming(self) -> bool:
        """Initialize streaming infrastructure"""
        if self.is_streaming:
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
            self.is_streaming = False
            return False

    def add_combination(self, symbol: str, config_file: str) -> Dict:
        """Add a new combination - simple version"""
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

            # Create DataStreamer (it owns its aggregators)
            data_streamer = DataStreamer(
                card_id=card_id,
                symbol=symbol,
                monitor_config=monitor_config
            )

            # Load historical data into the data streamer's aggregators
            data_streamer.load_historical_data(self.data_link)

            # Connect UI tool
            data_streamer.connect_tool(self.ui_tool)

            # Store combination
            self.combinations[card_id] = {
                'card_id': card_id,
                'symbol': symbol,
                'config_file': config_file,
                'monitor_config': monitor_config,
                'data_streamer': data_streamer
            }

            # Subscribe to quotes for this symbol
            self._ensure_symbol_subscription(symbol)

            logger.info(f"Successfully added combination: {card_id} ({symbol})")

            return {
                "success": True,
                "card_id": card_id,
                "symbol": symbol,
                "monitor_config_name": monitor_config.name
            }

        except Exception as e:
            logger.error(f"Error adding combination: {e}")
            return {"success": False, "error": str(e)}

    def _ensure_symbol_subscription(self, symbol: str):
        """Subscribe to quotes for symbol"""
        try:
            if symbol not in self.subscribed_symbols:
                self.subscribed_symbols.add(symbol)
                all_symbols = list(self.subscribed_symbols)

                self.data_link.subscribe_quotes(all_symbols)

                # Set up quote handler that routes to all relevant DataStreamers
                def quote_handler(quote_data):
                    symbol_from_pip = quote_data.get('key')
                    if symbol_from_pip:
                        self._route_pip_to_streamers(quote_data)

                self.data_link.add_quote_handler(quote_handler)

        except Exception as e:
            logger.error(f"Error subscribing to symbol {symbol}: {e}")

    def _route_pip_to_streamers(self, quote_data: Dict):
        """Route PIP data to all relevant DataStreamers"""
        symbol = quote_data.get('key')
        if not symbol:
            return

        # Send to all DataStreamers that handle this symbol
        for combination in self.combinations.values():
            if combination['symbol'] == symbol:
                combination['data_streamer'].process_pip(quote_data)

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