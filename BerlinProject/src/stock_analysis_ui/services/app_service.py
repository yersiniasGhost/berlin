"""
Simplified application service - DataStreamers own their aggregators
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
    Simplified application service - DataStreamers own their aggregators
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
        self.logger.info("AppService initialized")

    def start_streaming(self) -> bool:
        """Initialize streaming infrastructure"""
        if self.is_streaming:
            return True

        try:
            self.logger.info("Starting streaming infrastructure")

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
        """Add a new combination"""
        try:
            if not self.is_streaming:
                if not self.start_streaming():
                    return {"success": False, "error": "Failed to start streaming"}

            self.card_counter += 1
            card_id: str = f"card{self.card_counter}"

            monitor_config: Optional[MonitorConfiguration] = load_monitor_config(config_file)
            if not monitor_config:
                return {"success": False, "error": f"Failed to load config: {config_file}"}

            data_streamer: DataStreamer = DataStreamer(
                card_id=card_id,
                symbol=symbol,
                monitor_config=monitor_config
            )
            data_streamer.load_historical_data(self.data_link)
            data_streamer.connect_tool(self.ui_tool)
            self.data_link.add_data_streamer(symbol, data_streamer)


            self.combinations[card_id] = {
                'card_id': card_id,
                'symbol': symbol,
                'config_file': config_file,
                'monitor_config': monitor_config,
                'data_streamer': data_streamer
            }
            self.data_link.add_symbol_subscription(symbol)

            self.logger.info(f"Successfully added combination: {card_id} ({symbol})")

            return {
                "success": True,
                "card_id": card_id,
                "symbol": symbol,
                "monitor_config_name": monitor_config.name
            }

        except Exception as e:
            self.logger.error(f"Error adding combination: {e}")
            return {"success": False, "error": str(e)}

    # def _ensure_symbol_subscription(self, symbol: str) -> None:
    #     """Subscribe to quotes for symbol and set up routing"""
    #     try:
    #         if symbol not in self.subscribed_symbols:
    #             self.subscribed_symbols.add(symbol)
    #             all_symbols: List[str] = list(self.subscribed_symbols)
    #
    #             self.data_link.subscribe_quotes(all_symbols)
    #
    #             def quote_handler(quote_data: Dict[str, Any]) -> None:
    #                 symbol_from_pip = quote_data.get('key')
    #                 if symbol_from_pip:
    #                     # Add timestamp if missing  MOVE To SCHWAB
    #                     if '38' not in quote_data:
    #                         from datetime import datetime
    #                         quote_data['38'] = int(datetime.now().timestamp() * 1000)
    #                         print(f"ADDED TIMESTAMP: {quote_data['38']}")  # DEBUG
    #                     else:
    #                         print(f"EXISTING TIMESTAMP: {quote_data['38']}")  # DEBUG
    #
    #                     self._route_pip_to_streamers(quote_data)
    #
    #             self.data_link.add_quote_handler(quote_handler)
    #
    #     except Exception as e:
    #         self.logger.error(f"Error subscribing to symbol {symbol}: {e}")

    # This should GO

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