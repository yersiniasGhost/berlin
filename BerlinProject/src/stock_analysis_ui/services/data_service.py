import os
import logging
import threading
from typing import Dict, List, Any, Optional
import importlib
import sys

logger = logging.getLogger('DataService')


class DataService:
    """
    Service to manage data streaming and processing.
    Integrates with DataStreamer, SchwabDataLink, and indicator processing.
    """

    def __init__(self, ui_tool):
        """
        Initialize the data service.

        Args:
            ui_tool: UI external tool for visualization
        """
        self.ui_tool = ui_tool
        self.data_streamer = None
        self.schwab_data_link = None
        self.indicator_processor = None
        self.streaming_thread = None
        self.is_streaming = False
        self.current_symbols = []
        self.current_indicators = []
        self.current_weights = {}

        # Add path to import project modules
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
        sys.path.insert(0, project_root)

        # Initialize logger
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    def _import_modules(self):
        """Import required modules from the project"""
        try:
            # Add the parent directory to the path so Python can find the modules
            import os
            import sys
            current_dir = os.path.dirname(os.path.abspath(__file__))

            # Go up to the stock_analysis_ui directory
            project_dir = os.path.abspath(os.path.join(current_dir, '..'))

            # Go up to the src directory that contains both the stock_analysis_ui and data_streamer directories
            src_dir = os.path.abspath(os.path.join(project_dir, '..'))

            # Add the src directory to the path
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)

            # Now import the modules directly from data_streamer
            from data_streamer.data_streamer_orig import DataStreamer
            from data_streamer.schwab_data_link import SchwabDataLink
            from models.monitor_configuration import MonitorConfiguration
            from models.indicator_definition import IndicatorDefinition

            # Assign to self attributes
            self.DataStreamer = DataStreamer
            self.SchwabDataLink = SchwabDataLink
            self.MonitorConfiguration = MonitorConfiguration
            self.IndicatorDefinition = IndicatorDefinition

            logger.info("Successfully imported project modules")
            return True
        except ImportError as e:
            logger.error(f"Error importing project modules: {e}")
            return False

    def start(self, symbols: List[str], indicators: List[Dict], weights: Dict[str, float] = None,
              timeframe: str = "1m") -> bool:
        """
        Start data streaming for the specified symbols and indicators.

        Args:
            symbols: List of ticker symbols to monitor
            indicators: List of indicator configurations
            weights: Optional dictionary of indicator weights
            timeframe: Candle timeframe (1m, 5m, 15m, 30m, 1h, 1d)

        Returns:
            bool: True if streaming started successfully, False otherwise
        """
        if self.is_streaming:
            logger.info("Already streaming, stopping first")
            self.stop()

        # Inside the start method, after creating data_streamer:
        if weights:
            for symbol in symbols:
                if hasattr(self.ui_tool, 'update_weights'):
                    self.ui_tool.update_weights(symbol, weights)

        # Import required modules
        if not hasattr(self, 'DataStreamer'):
            success = self._import_modules()
            if not success:
                return False

        # Save current configuration
        self.current_symbols = symbols
        self.current_indicators = indicators
        self.current_weights = weights or {}
        self.current_timeframe = timeframe

        try:
            # Get Schwab authentication from the manager
            from .schwab_auth import SchwabAuthManager
            auth_manager = SchwabAuthManager()

            if not auth_manager.is_authenticated():
                logger.error("Not authenticated with Schwab API")
                return False

            # Create data configuration
            data_config = {
                "type": "CharlesSchwab",
                "user_prefs": auth_manager.user_prefs,
                "access_token": auth_manager.access_token,
                "symbols": symbols,
                "timeframe": timeframe,
                "days_history": 5
            }

            # Create model configuration (simple for now)
            model_config = {
                "feature_vector": [
                    {"name": "close"},
                    {"name": "open"},
                    {"name": "high"},
                    {"name": "low"},
                    {"name": "SMA", "parameters": {"sma": 20}},
                    {"name": "MACD", "parameters": {
                        "fast_period": 12,
                        "slow_period": 26,
                        "signal_period": 9
                    }}
                ]
            }

            # Create indicator configuration
            # Convert the indicators list to a format suitable for MonitorConfiguration
            indicator_defs = []
            for indicator in indicators:
                # Create IndicatorDefinition objects
                indicator_def = self.IndicatorDefinition(
                    name=indicator["name"],
                    type=indicator["type"],
                    function=indicator["function"],
                    parameters=indicator["parameters"]
                )
                indicator_defs.append(indicator_def)

            # Create the MonitorConfiguration
            monitor_config = self.MonitorConfiguration(
                name="trading_signals",
                indicators=indicator_defs
            )

            # Create DataStreamer
            self.data_streamer = self.DataStreamer(
                data_configuration=data_config,
                model_configuration=model_config,
                indicator_configuration=monitor_config
            )

            # Connect UI tool
            self.data_streamer.connect_tool(self.ui_tool)

            # Set weights in UI tool
            self.ui_tool.update_weights(self.current_weights)

            # Explicitly load historical data
            # In data_service.py, modify the start method:

            # After loading historical data, explicitly push it to the UI tool
            if hasattr(self.data_streamer.data_link, 'load_historical_data'):
                success = self.data_streamer.data_link.load_historical_data()

                if success:
                    for symbol in symbols:
                        candles = self.data_streamer.data_link.candle_data.get(symbol, [])
                        logger.info(f"Loaded {len(candles)} historical candles for {symbol}")

                        # Push each historical candle to the UI
                        for candle in candles:
                            self.ui_tool.handle_completed_candle(symbol, candle)

            # Connect to streaming service
            if hasattr(self.data_streamer.data_link, 'connect'):
                logger.info("Connecting to streaming service...")
                success = self.data_streamer.data_link.connect()
                if not success:
                    logger.warning("Failed to connect to streaming service, continuing with historical data only")

            # Start streaming in a separate thread
            self.streaming_thread = threading.Thread(target=self._stream_data)
            self.streaming_thread.daemon = True
            self.streaming_thread.start()

            self.is_streaming = True
            logger.info(f"Started streaming for symbols: {', '.join(symbols)} with timeframe: {timeframe}")
            return True

        except Exception as e:
            logger.error(f"Error starting data streaming: {e}", exc_info=True)
            return False

    def load_monitor_config(self, config_data: dict) -> bool:
        """
        Load a monitor configuration from a dictionary (parsed from JSON)

        Args:
            config_data: The monitor configuration dictionary

        Returns:
            bool: Success status
        """
        try:
            logger.info(f"Loading monitor configuration: {config_data.get('test_name', 'Unnamed Config')}")

            # Extract monitor and indicators
            monitor_config = config_data.get('monitor', {})
            indicators = config_data.get('indicators', [])

            if not indicators:
                logger.error("No indicators found in config")
                return False

            # Get symbols from data section if present
            symbols = []
            if 'data' in config_data and 'ticker' in config_data['data']:
                symbols.append(config_data['data']['ticker'])

            # Extract weights from triggers
            weights = {}
            if 'triggers' in monitor_config:
                weights.update(monitor_config['triggers'])
            if 'bear_triggers' in monitor_config:
                weights.update(monitor_config['bear_triggers'])

            # Start streaming with the new configuration
            success = self.start(symbols, indicators, weights)

            return success
        except Exception as e:
            logger.error(f"Error loading monitor configuration: {e}", exc_info=True)
            return False

    def _stream_data(self):
        """
        Stream data in a separate thread
        """
        try:
            logger.info("Starting data streaming thread")
            self.data_streamer.run()
        except Exception as e:
            logger.error(f"Error in data streaming thread: {e}")
        finally:
            self.is_streaming = False
            logger.info("Data streaming thread stopped")

    def stop(self):
        """
        Stop data streaming
        """
        if not self.is_streaming:
            logger.info("Not currently streaming")
            return True

        try:
            # If the data_streamer has a stop method, call it
            if hasattr(self.data_streamer, 'stop'):
                self.data_streamer.stop()

            # Wait for the thread to finish
            if self.streaming_thread:
                self.streaming_thread.join(timeout=5)

            self.is_streaming = False
            logger.info("Stopped data streaming")
            return True
        except Exception as e:
            logger.error(f"Error stopping data streaming: {e}")
            return False

    def add_symbols(self, symbols: List[str]) -> bool:
        """
        Add new symbols to the current streaming session

        Args:
            symbols: List of new symbols to add

        Returns:
            bool: True if symbols were added successfully, False otherwise
        """
        if not self.is_streaming:
            logger.warning("Not currently streaming, cannot add symbols")
            return False

        # Add new symbols to current list
        new_symbols = [s for s in symbols if s not in self.current_symbols]
        if not new_symbols:
            logger.info("No new symbols to add")
            return True

        try:
            # Restart with combined symbol list
            combined_symbols = self.current_symbols + new_symbols
            return self.start(combined_symbols, self.current_indicators, self.current_weights)
        except Exception as e:
            logger.error(f"Error adding symbols: {e}")
            return False

    def remove_symbols(self, symbols: List[str]) -> bool:
        """
        Remove symbols from the current streaming session

        Args:
            symbols: List of symbols to remove

        Returns:
            bool: True if symbols were removed successfully, False otherwise
        """
        if not self.is_streaming:
            logger.warning("Not currently streaming, cannot remove symbols")
            return False

        try:
            # Remove symbols from current list
            remaining_symbols = [s for s in self.current_symbols if s not in symbols]
            if not remaining_symbols:
                logger.warning("Cannot remove all symbols, stopping streaming instead")
                return self.stop()

            # Restart with reduced symbol list
            return self.start(remaining_symbols, self.current_indicators, self.current_weights)
        except Exception as e:
            logger.error(f"Error removing symbols: {e}")
            return False

    def update_weights(self, weights: Dict[str, float]) -> bool:
        """
        Update indicator weights

        Args:
            weights: Dictionary of indicator weights

        Returns:
            bool: True if weights were updated successfully, False otherwise
        """
        try:
            # Update current weights
            self.current_weights.update(weights)

            # Update UI tool
            self.ui_tool.update_weights(self.current_weights)

            logger.info("Updated indicator weights")
            return True
        except Exception as e:
            logger.error(f"Error updating weights: {e}")
            return False

    def get_ticker_data(self) -> Dict:
        """
        Get current ticker data

        Returns:
            Dictionary with all ticker data
        """
        if self.ui_tool:
            return self.ui_tool.get_ticker_data()
        return {}

    def is_active(self) -> bool:
        """
        Check if streaming is active

        Returns:
            bool: True if streaming is active, False otherwise
        """
        return self.is_streaming