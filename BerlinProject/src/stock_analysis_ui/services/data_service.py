import os
import logging
import threading
from typing import Dict, List, Any, Optional, Set
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

    def __init__(self):
        """
        Initialize the data service without UI tool - tool will be passed later.
        """
        self.ui_tool = None  # Will be set later when needed
        self.data_streamer = None
        self.schwab_data_link = None
        self.indicator_processor = None
        self.streaming_thread = None
        self.is_streaming = False
        self.current_symbols = []
        self.current_indicators = []
        self.current_weights = {}
        self.current_timeframe = "1m"  # Default timeframe
        self.streaming_manager = None  # Will be created when needed
        self.required_timeframes = {"1m"}  # Default to 1-minute timeframe

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
              timeframe: str = "1m", ui_tool=None) -> bool:
        """
        Start data streaming for the specified symbols and indicators.
        Now accepts ui_tool as an optional parameter and handles multiple timeframes.
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
        self.current_timeframe = timeframe  # This is now just a base timeframe

        # Store UI tool if provided
        if ui_tool:
            self.ui_tool = ui_tool

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

            # Convert dictionary indicators to IndicatorDefinition objects if needed
            indicator_defs = []
            for indicator in indicators:
                # Check if this is already an IndicatorDefinition object
                if hasattr(indicator, 'name') and hasattr(indicator, 'type'):
                    indicator_defs.append(indicator)
                else:
                    # It's a dictionary, convert it
                    indicator_def = self.IndicatorDefinition(
                        name=indicator["name"],
                        type=indicator["type"],
                        function=indicator["function"],
                        parameters=indicator["parameters"],
                        # Add time_increment field if present
                        time_increment=indicator.get("time_increment", "1m")
                    )
                    indicator_defs.append(indicator_def)

            # Create the MonitorConfiguration
            monitor_config = self.MonitorConfiguration(
                name="trading_signals",
                indicators=indicator_defs
            )

            # Get all required timeframes
            self.required_timeframes = monitor_config.get_time_increments()
            logger.info(f"Required timeframes: {self.required_timeframes}")

            # Create DataStreamer with the direct data_link instance
            self.data_streamer = self.DataStreamer(
                data_link=self.schwab_data_link,
                model_configuration=model_config,
                indicator_configuration=monitor_config
            )

            # Connect UI tool if available
            if self.ui_tool:
                self.data_streamer.connect_tool(self.ui_tool)

                # Update weights in UI tool if available
                if weights and hasattr(self.ui_tool, 'update_weights'):
                    self.ui_tool.update_weights(weights)

                # Store data_streamer reference in UI tool if needed
                if hasattr(self.ui_tool, 'set_data_streamer_ref'):
                    self.ui_tool.set_data_streamer_ref(self.data_streamer)

            # Initialize data with historical data for all timeframes
            logger.info(f"Initializing with historical data for symbols: {symbols}")
            self.data_streamer.initialize(symbols)

            # Log initial history size
            initial_history_size = len(self.data_streamer.preprocessor.history)
            logger.info(f"Loaded {initial_history_size} historical data points")

            # Store in UI tool for reference if available
            if self.ui_tool and hasattr(self.ui_tool, 'set_initial_history_size'):
                self.ui_tool.set_initial_history_size(initial_history_size)

            # Start streaming in a separate thread
            self.streaming_thread = threading.Thread(target=self._stream_data)
            self.streaming_thread.daemon = True
            self.streaming_thread.start()

            self.is_streaming = True
            logger.info(
                f"Started streaming for symbols: {', '.join(symbols)} with timeframes: {self.required_timeframes}")
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
            # Connect to streaming API
            if self.schwab_data_link.connect_stream():
                base_timeframe = "1m"  # Always use 1m as base timeframe for real-time data

                # Subscribe to base timeframe for each symbol
                for symbol in self.current_symbols:
                    self.schwab_data_link.subscribe_charts([symbol], base_timeframe)
                    logger.info(f"Subscribed to {symbol} with base timeframe {base_timeframe}")

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

            # Update UI tool if available
            if self.ui_tool and hasattr(self.ui_tool, 'update_weights'):
                self.ui_tool.update_weights(self.current_weights)

            logger.info("Updated indicator weights")
            return True
        except Exception as e:
            logger.error(f"Error updating weights: {e}")
            return False

    def get_ticker_data(self) -> Dict:
        """
        Get current ticker data from UI tool if available
        """
        if self.ui_tool and hasattr(self.ui_tool, 'get_ticker_data'):
            return self.ui_tool.get_ticker_data()
        return {}

    def create_streaming_manager(self):
        """Create a new StreamingManager instance that supports multiple timeframes"""
        # Initialize data link if needed
        if not hasattr(self, 'schwab_data_link') or self.schwab_data_link is None:
            from .schwab_auth import SchwabAuthManager
            auth_manager = SchwabAuthManager()

            if not auth_manager.is_authenticated():
                logger.error("Not authenticated with Schwab API")
                raise ValueError("Not authenticated with Schwab API")

            from data_streamer.schwab_data_link import SchwabDataLink
            self.schwab_data_link = SchwabDataLink()
            self.schwab_data_link.access_token = auth_manager.access_token
            self.schwab_data_link.refresh_token = auth_manager.refresh_token
            self.schwab_data_link.user_prefs = auth_manager.user_prefs

            # Connect to streaming API
            if not self.schwab_data_link.connect_stream():
                logger.error("Failed to connect to streaming API")
                raise ValueError("Failed to connect to streaming API")

        # Create StreamingManager
        from .streaming_manager import StreamingManager
        self.streaming_manager = StreamingManager(self.schwab_data_link)
        logger.info("Created new StreamingManager with multi-timeframe support")

        return self.streaming_manager