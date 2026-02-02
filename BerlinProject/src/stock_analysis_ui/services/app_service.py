"""
Updated application service for both live Schwab and CSReplayDataLink support
"""

import os
import json
from typing import Dict, List, Optional, Any, Union

from socket import SocketIO

from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.cs_replay_data_link import CSReplayDataLink
from data_streamer.data_streamer import DataStreamer
from models.monitor_configuration import MonitorConfiguration, load_monitor_config
from stock_analysis_ui.services.ui_external_tool import UIExternalTool
from stock_analysis_ui.services.pip_saver import PipSaver
from stock_analysis_ui.services.schwab_auth import SchwabAuthManager
from mlf_utils.log_manager import LogManager
from mlf_utils.timezone_utils import now_utc, isoformat_et


class AppService:
    """
    Updated application service that supports both live Schwab streaming and CSReplayDataLink
    """

    def __init__(self, socketio: SocketIO, auth_manager: Optional[SchwabAuthManager] = None,
                 session_id: str = None) -> None:
        """
        Initialize AppService

        Args:
            socketio: SocketIO instance for WebSocket communication
            auth_manager: SchwabAuthManager for live mode (None for replay mode)
            session_id: Session ID for this app service instance
        """
        self.socketio: SocketIO = socketio
        self.auth_manager: Optional[SchwabAuthManager] = auth_manager
        self.session_id: str = session_id  # NEW: Track session ID

        self.data_link: Optional[Union[SchwabDataLink, CSReplayDataLink]] = None
        # MODIFIED: Pass self to UIExternalTool so it can access combination data
        self.ui_tool: UIExternalTool = UIExternalTool(socketio, app_service=self)

        # Initialize pip saver and connect to ui_tool
        self.pip_saver: PipSaver = PipSaver(session_id=session_id)
        self.ui_tool.pip_saver = self.pip_saver

        # State tracking
        self.is_streaming: bool = False
        self.combinations: Dict[str, Dict[str, Any]] = {}
        self.card_counter: int = 0
        self.subscribed_symbols: set = set()
        self.logger = LogManager().get_logger(f"AppService-{session_id or 'global'}")

        # Determine mode for logging
        mode = "CS Replay" if auth_manager is None else "Live Schwab"
        session_info = f" (Session: {session_id})" if session_id else ""
        self.logger.info(f"AppService initialized for {mode} mode{session_info}")

    # Add cleanup method
    def cleanup(self):
        """Cleanup resources when session ends"""
        try:
            if self.is_streaming:
                self.stop_streaming()

            if self.data_link:
                if hasattr(self.data_link, 'disconnect'):
                    self.data_link.disconnect()

            # Cleanup pip saver
            if self.pip_saver:
                self.pip_saver.cleanup()

            self.combinations.clear()
            self.logger.info(f"AppService cleanup completed for session {self.session_id}")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def start_streaming(self) -> bool:
        """Initialize streaming infrastructure - supports both live and replay modes"""
        if self.is_streaming:
            self.logger.info("Streaming already active")
            return True

        try:
            self.logger.info("Starting streaming infrastructure")

            # Case 1: CSReplayDataLink already set (replay mode)
            if self.data_link and isinstance(self.data_link, CSReplayDataLink):
                self.logger.info("Using existing CSReplayDataLink")
                if hasattr(self.data_link, 'connect_stream'):
                    success = self.data_link.connect_stream()
                else:
                    # CSReplayDataLink doesn't have connect_stream, assume ready
                    success = True

                if success:
                    self.is_streaming = True
                    self.logger.info("CSReplayDataLink streaming started")
                return success

            # Case 2: Other data_link already set
            elif self.data_link:
                self.logger.info("Using existing data_link")
                if hasattr(self.data_link, 'connect_stream'):
                    success = self.data_link.connect_stream()
                    if success:
                        self.is_streaming = True
                    return success
                # If no connect_stream method, assume it's ready
                self.is_streaming = True
                return True

            # Case 3: Live Schwab mode - create SchwabDataLink
            if not self.auth_manager:
                self.logger.error("No auth manager or data link available for live mode")
                return False

            self.logger.info("Creating SchwabDataLink for live mode")
            self.data_link = SchwabDataLink()
            self.data_link.access_token = self.auth_manager.access_token
            self.data_link.refresh_token = self.auth_manager.refresh_token
            self.data_link.user_prefs = self.auth_manager.user_prefs

            if not self.data_link.connect_stream():
                self.logger.error("Failed to connect to Schwab streaming")
                return False

            self.is_streaming = True
            self.logger.info("Live Schwab streaming started successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error starting streaming: {e}")
            import traceback
            traceback.print_exc()
            self.is_streaming = False
            return False

    def add_combination(self, symbol: str, config_file: str) -> Dict[str, Any]:
        """Add a new combination - works with both live and replay modes"""
        try:
            # Ensure streaming is started
            if not self.is_streaming:
                if not self.start_streaming():
                    return {"success": False, "error": "Failed to start streaming"}

            self.card_counter += 1
            card_id: str = f"card{self.card_counter}"

            # Extract test_name from config file
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

            # Create DataStreamer
            data_streamer: DataStreamer = DataStreamer(
                card_id=card_id,
                symbol=symbol,
                monitor_config=monitor_config
            )

            # Store test_name in the DataStreamer
            data_streamer.test_name = test_name

            # Load historical data (empty for CSReplayDataLink, real data for SchwabDataLink)
            data_streamer.load_historical_data(self.data_link)

            # Connect UI tool to DataStreamer
            data_streamer.connect_tool(self.ui_tool)

            # Register DataStreamer with the data_link
            self.data_link.add_data_streamer(symbol, data_streamer)

            # Store combination info
            self.combinations[card_id] = {
                'card_id': card_id,
                'symbol': symbol,
                'config_file': config_file,
                'monitor_config': monitor_config,
                'test_name': test_name,
                'data_streamer': data_streamer
            }

            # Subscribe to symbol - handle both data link types
            self._subscribe_to_symbol(symbol)

            # Emit current state with calculated indicators (from historical data if available)
            # This ensures cards appear immediately with actual indicator values
            data_streamer.emit_current_state()

            self.logger.info(f"Successfully added combination: {card_id} ({symbol}) - '{test_name}'")

            return {
                "success": True,
                "card_id": card_id,
                "symbol": symbol,
                "monitor_config_name": monitor_config.name,
                "test_name": test_name
            }

        except Exception as e:
            self.logger.error(f"Error adding combination: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def _subscribe_to_symbol(self, symbol: str) -> None:
        """Subscribe to symbol using the appropriate method for the data_link type"""
        try:
            if isinstance(self.data_link, CSReplayDataLink):
                # CSReplayDataLink uses add_symbol_subscription
                self.data_link.add_symbol_subscription(symbol)
                self.logger.info(f"Subscribed to {symbol} via CSReplayDataLink")

            elif hasattr(self.data_link, 'add_symbol_subscription'):
                # SchwabDataLink uses add_symbol_subscription
                self.data_link.add_symbol_subscription(symbol)
                self.logger.info(f"Subscribed to {symbol} via SchwabDataLink")

            elif hasattr(self.data_link, 'subscribe_quotes'):
                # Fallback to subscribe_quotes method
                self.data_link.subscribe_quotes([symbol])
                self.logger.info(f"Subscribed to {symbol} via subscribe_quotes")

            else:
                self.logger.warning(f"No subscription method found for {symbol}")

        except Exception as e:
            self.logger.error(f"Error subscribing to {symbol}: {e}")

    def _emit_initial_card_update(self, card_id: str, symbol: str, test_name: str, data_streamer) -> None:
        """Emit an initial card_update event so the card appears immediately in the UI"""
        try:
            # Get data status from the indicator processor
            data_status = data_streamer.indicator_processor.get_data_status()

            # Build initial update data with placeholder values
            initial_data = {
                'card_id': card_id,
                'symbol': symbol,
                'price': 0.0,
                'timestamp': isoformat_et(now_utc()),
                'indicators': {},
                'raw_indicators': {},
                'bar_scores': {},
                'data_status': data_status,
                'test_name': test_name,
                'monitor_config_name': test_name
            }

            # Emit using the UI tool
            self.ui_tool.emit_to_session('card_update', initial_data, self.session_id)
            self.logger.info(f"Emitted initial card_update for {card_id}")

        except Exception as e:
            self.logger.error(f"Error emitting initial card_update: {e}")

    def remove_combination(self, card_id: str) -> Dict[str, Any]:
        """Remove a combination and cleanup properly - works with both modes"""
        try:
            if card_id not in self.combinations:
                return {"success": False, "error": f"Card {card_id} not found"}

            combination = self.combinations[card_id]
            symbol = combination['symbol']
            data_streamer = combination['data_streamer']

            # Remove DataStreamer from data_link
            if self.data_link and symbol in self.data_link.data_streamers:
                if data_streamer in self.data_link.data_streamers[symbol]:
                    self.data_link.data_streamers[symbol].remove(data_streamer)

                # If no more DataStreamers for this symbol, remove the symbol entry
                if not self.data_link.data_streamers[symbol]:
                    del self.data_link.data_streamers[symbol]

            # Clear UI tool data for this card
            self.ui_tool.clear_meaningful_data(card_id)

            # Close pip saver file for this card
            if self.pip_saver:
                self.pip_saver.close_card_file(card_id)

            # Remove from combinations
            del self.combinations[card_id]

            self.logger.info(f"Successfully removed combination: {card_id}")

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
                    # MODIFIED: Prioritize test_name from config file over generic monitor name
                    "monitor_config_name": data.get("test_name", data["monitor_config"].name),
                    "test_name": data.get("test_name", "Unknown Config")  # Include both for flexibility
                }
                for card_id, data in self.combinations.items()
            ],
            "total": len(self.combinations)
        }

    def stop_streaming(self) -> bool:
        """Stop all streaming - works with both modes"""
        try:
            self.is_streaming = False

            if self.data_link:
                if hasattr(self.data_link, 'disconnect'):
                    self.data_link.disconnect()
                elif hasattr(self.data_link, 'stop_streaming'):
                    self.data_link.stop_streaming()

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

    def get_mode(self) -> str:
        """Get current operating mode"""
        if isinstance(self.data_link, CSReplayDataLink):
            return "CS Replay"
        elif isinstance(self.data_link, SchwabDataLink):
            return "Live Schwab"
        else:
            return "Unknown"

    def get_status_info(self) -> Dict[str, Any]:
        """Get detailed status information"""
        status = {
            "mode": self.get_mode(),
            "is_streaming": self.is_streaming,
            "combinations_count": len(self.combinations),
            "subscribed_symbols": list(self.subscribed_symbols),
            "pip_saver": self.pip_saver.get_status() if self.pip_saver else None
        }

        # Add mode-specific info
        if isinstance(self.data_link, CSReplayDataLink):
            status["replay_progress"] = self.data_link.get_progress()
        elif self.auth_manager:
            status["authenticated"] = self.auth_manager.is_authenticated()

        return status

    # Pip saver management methods
    def toggle_pip_saving(self) -> Dict[str, Any]:
        """Toggle pip saving on/off. Returns new status."""
        if not self.pip_saver:
            return {"success": False, "error": "Pip saver not initialized"}

        new_state = self.pip_saver.toggle()

        # Emit status update to connected clients
        self._emit_pip_saver_status()

        return {
            "success": True,
            "enabled": new_state,
            "status": self.pip_saver.get_status()
        }

    def enable_pip_saving(self) -> Dict[str, Any]:
        """Enable pip saving. Returns status."""
        if not self.pip_saver:
            return {"success": False, "error": "Pip saver not initialized"}

        success = self.pip_saver.enable()
        if success:
            self._emit_pip_saver_status()

        return {
            "success": success,
            "enabled": self.pip_saver.is_enabled,
            "status": self.pip_saver.get_status()
        }

    def disable_pip_saving(self) -> Dict[str, Any]:
        """Disable pip saving. Returns status."""
        if not self.pip_saver:
            return {"success": False, "error": "Pip saver not initialized"}

        success = self.pip_saver.disable()
        if success:
            self._emit_pip_saver_status()

        return {
            "success": success,
            "enabled": self.pip_saver.is_enabled,
            "status": self.pip_saver.get_status()
        }

    def get_pip_saver_status(self) -> Dict[str, Any]:
        """Get current pip saver status."""
        if not self.pip_saver:
            return {"enabled": False, "error": "Pip saver not initialized"}
        return self.pip_saver.get_status()

    def _emit_pip_saver_status(self):
        """Emit pip saver status to connected clients via WebSocket."""
        try:
            status = self.pip_saver.get_status() if self.pip_saver else {"enabled": False}
            self.ui_tool.emit_to_session('pip_saver_status', status, self.session_id)
            self.logger.info(f"Emitted pip saver status: enabled={status.get('enabled')}")
        except Exception as e:
            self.logger.error(f"Error emitting pip saver status: {e}")