"""
Updated application service for process_tick architecture
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any

from flask_socketio import SocketIO

from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.data_streamer import DataStreamer
from models.monitor_configuration import MonitorConfiguration, load_monitor_config
from stock_analysis_ui.services.ui_external_tool import UIExternalTool
from stock_analysis_ui.services.schwab_auth import SchwabAuthManager


class AppService:
    """
    Updated application service for process_tick architecture
    DataStreamers now own their aggregators and process TickData
    """

    def __init__(self, socketio: SocketIO, auth_manager: SchwabAuthManager) -> None:
        self.socketio: SocketIO = socketio
        self.auth_manager: SchwabAuthManager = auth_manager

        # Core components
        self.data_link: Optional[SchwabDataLink] = None
        self.ui_tool: UIExternalTool = UIExternalTool(socketio)

        # State tracking
        self.is_streaming: bool = False
        self.combinations: Dict[str, Dict[str, Any]] = {}
        self.card_counter: int = 0
        self.subscribed_symbols: set = set()
        self.logger = logging.getLogger('AppService')
        self.logger.info("AppService initialized for process_tick architecture")

    def start_streaming(self) -> bool:
        """Initialize streaming infrastructure"""
        if self.is_streaming:
            return True

        try:
            self.logger.info("Starting streaming infrastructure")

            # Create and configure SchwabDataLink
            self.data_link = SchwabDataLink()
            self.data_link.access_token = self.auth_manager.access_token
            self.data_link.refresh_token = self.auth_manager.refresh_token
            self.data_link.user_prefs = self.auth_manager.user_prefs

            if not self.data_link.connect_stream():
                self.logger.error("Failed to connect to Schwab streaming")
                return False

            self.is_streaming = True
            self.logger.info("Streaming infrastructure started successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error starting streaming: {e}")
            self.is_streaming = False
            return False

    def add_combination(self, symbol: str, config_file: str) -> Dict[str, Any]:
        """Add a new combination with updated architecture"""
        try:
            if not self.is_streaming:
                if not self.start_streaming():
                    return {"success": False, "error": "Failed to start streaming"}

            self.card_counter += 1
            card_id: str = f"card{self.card_counter}"

            # UPDATED: Extract test_name FIRST before loading monitor config
            test_name = "Unknown Config"
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                    test_name = config_data.get('test_name', 'Unknown Config')
                    self.logger.info(f"Extracted test_name: '{test_name}' from config file")
            except Exception as e:
                self.logger.error(f"Error reading config file for test_name: {e}")

            # Load monitor configuration
            monitor_config: Optional[MonitorConfiguration] = load_monitor_config(config_file)
            if not monitor_config:
                return {"success": False, "error": f"Failed to load config: {config_file}"}

            # Create DataStreamer (now owns its own aggregators)
            data_streamer: DataStreamer = DataStreamer(
                card_id=card_id,
                symbol=symbol,
                monitor_config=monitor_config
            )

            # UPDATED: Store test_name in the DataStreamer for easy access
            data_streamer.test_name = test_name

            # Load historical data for all timeframes
            data_streamer.load_historical_data(self.data_link)

            # Connect UI tool to DataStreamer
            data_streamer.connect_tool(self.ui_tool)

            # Register DataStreamer with SchwabDataLink
            self.data_link.add_data_streamer(symbol, data_streamer)

            # Store combination info with test_name
            self.combinations[card_id] = {
                'card_id': card_id,
                'symbol': symbol,
                'config_file': config_file,
                'monitor_config': monitor_config,
                'test_name': test_name,  # Store test_name
                'data_streamer': data_streamer
            }

            # Subscribe to symbol quotes
            self.data_link.add_symbol_subscription(symbol)

            self.logger.info(f"Successfully added combination: {card_id} ({symbol}) - '{test_name}'")

            return {
                "success": True,
                "card_id": card_id,
                "symbol": symbol,
                "monitor_config_name": monitor_config.name,
                "test_name": test_name  # Return test_name
            }

        except Exception as e:
            self.logger.error(f"Error adding combination: {e}")
            return {"success": False, "error": str(e)}

    def remove_combination(self, card_id: str) -> Dict[str, Any]:
        """Remove a combination and properly cleanup DataStreamer"""
        try:
            if card_id not in self.combinations:
                return {"success": False, "error": f"Card {card_id} not found"}

            combination = self.combinations[card_id]
            symbol = combination['symbol']
            data_streamer = combination['data_streamer']

            # Remove DataStreamer from SchwabDataLink
            if self.data_link and symbol in self.data_link.data_streamers:
                # Remove this specific data_streamer from the symbol's list
                if data_streamer in self.data_link.data_streamers[symbol]:
                    self.data_link.data_streamers[symbol].remove(data_streamer)

                # If no more DataStreamers for this symbol, remove the symbol entry
                if not self.data_link.data_streamers[symbol]:
                    del self.data_link.data_streamers[symbol]
                    # Optionally unsubscribe from symbol (for now we'll keep subscription active)

            # Clear UI tool data for this card
            self.ui_tool.clear_meaningful_data(card_id)

            # Remove from combinations
            del self.combinations[card_id]

            self.logger.info(f"Successfully removed combination and cleaned up DataStreamer: {card_id}")

            return {"success": True, "message": f"Removed {card_id}"}

        except Exception as e:
            self.logger.error(f"Error removing combination {card_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_combinations(self) -> Dict[str, Any]:
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

            # Clear all combinations
            self.combinations.clear()

            self.logger.info("Streaming stopped")
            return True

        except Exception as e:
            self.logger.error(f"Error stopping streaming: {e}")
            return False

    def get_available_configs(self) -> List[str]:
        """Get available monitor configuration files"""
        config_files: List[str] = []

        current_dir: str = os.path.dirname(os.path.abspath(__file__))
        config_dirs: List[str] = [
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