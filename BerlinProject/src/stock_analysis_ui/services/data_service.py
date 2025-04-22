import os
import logging
import threading
from typing import Dict, List, Any, Optional
import importlib
import sys
import time
from datetime import datetime

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
        self.current_timeframe = "1m"  # Default timeframe

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

            # Now import the modules directly
            from data_streamer.data_streamer import DataStreamer  # Use the new refactored version
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
        """
        if self.is_streaming:
            logger.info("Already streaming, stopping first")
            self.stop()

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
            # Get Schwab authentication
            from .schwab_auth import SchwabAuthManager
            auth_manager = SchwabAuthManager()

            if not auth_manager.is_authenticated():
                logger.error("Not authenticated with Schwab API")
                return False

            # Create SchwabDataLink instance with authentication
            self.schwab_data_link = self.SchwabDataLink()

            # Manually set authentication credentials from auth_manager
            self.schwab_data_link.access_token = auth_manager.access_token
            self.schwab_data_link.refresh_token = auth_manager.refresh_token
            self.schwab_data_link.user_prefs = auth_manager.user_prefs

            # Create model configuration
            model_config = {
                "feature_vector": [
                    {"name": "close"},
                    {"name": "open"},
                    {"name": "high"},
                    {"name": "low"}
                ],
                "normalization": None  # No normalization for UI display
            }

            # Identify the type of indicators being passed in
            if indicators and isinstance(indicators[0], dict):
                # Indicators are dictionaries, convert them to IndicatorDefinition objects
                indicator_defs = []
                for indicator in indicators:
                    indicator_def = self.IndicatorDefinition(
                        name=indicator["name"],
                        type=indicator["type"],
                        function=indicator["function"],
                        parameters=indicator["parameters"]
                    )
                    indicator_defs.append(indicator_def)
            else:
                # Indicators are already IndicatorDefinition objects
                indicator_defs = indicators

            monitor_config = self.MonitorConfiguration(
                name="trading_signals",
                indicators=indicator_defs
            )

            # Create DataStreamer with the direct data_link instance
            self.data_streamer = self.DataStreamer(
                data_link=self.schwab_data_link,
                model_configuration=model_config,
                indicator_configuration=monitor_config
            )

            # Connect UI tool to receive updates
            self.data_streamer.connect_tool(self.ui_tool)

            # Update weights in UI tool
            if weights:
                self.ui_tool.update_weights(weights)

            # Initialize data with historical data
            logger.info(f"Initializing with historical data for symbols: {symbols}")
            self.data_streamer.initialize(symbols, timeframe)

            # Log initial history size
            initial_history_size = len(self.data_streamer.preprocessor.history)
            logger.info(f"Loaded {initial_history_size} historical data points")

            # Store in UI tool for reference
            if hasattr(self.ui_tool, 'set_initial_history_size'):
                self.ui_tool.set_initial_history_size(initial_history_size)

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

    def _stream_data(self):
        """
        Run the DataStreamer in a separate thread
        """
        try:
            logger.info("Starting data streaming thread")
            # Connect to streaming API and subscribe to symbols
            if self.schwab_data_link.connect_stream():
                for symbol in self.current_symbols:
                    self.schwab_data_link.subscribe_charts([symbol], self.current_timeframe)
                    logger.info(f"Subscribed to {symbol} with timeframe {self.current_timeframe}")

                # Run the DataStreamer - this will process incoming data
                self.data_streamer.run()
            else:
                logger.error("Failed to connect to streaming API")
        except Exception as e:
            logger.error(f"Error in data streaming thread: {e}")
            import traceback
            traceback.print_exc()
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
            # Disconnect the WebSocket in the data link
            if self.schwab_data_link and hasattr(self.schwab_data_link, 'disconnect'):
                self.schwab_data_link.disconnect()

            # Wait for the thread to finish
            if self.streaming_thread:
                self.streaming_thread.join(timeout=2)  # Short timeout for responsive UI

            self.is_streaming = False
            logger.info("Stopped data streaming")
            return True
        except Exception as e:
            logger.error(f"Error stopping data streaming: {e}")
            return False

    def update_weights(self, weights: Dict[str, float]) -> bool:
        """
        Update indicator weights
        """
        try:
            # Update current weights
            self.current_weights.update(weights)

            # Update UI tool
            if self.ui_tool and hasattr(self.ui_tool, 'update_weights'):
                self.ui_tool.update_weights(self.current_weights)

            logger.info("Updated indicator weights")
            return True
        except Exception as e:
            logger.error(f"Error updating weights: {e}")
            return False

    def get_ticker_data(self) -> Dict:
        """
        Get current ticker data
        """
        if self.ui_tool and hasattr(self.ui_tool, 'get_ticker_data'):
            return self.ui_tool.get_ticker_data()
        return {}