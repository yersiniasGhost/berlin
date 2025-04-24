import os
import logging
import threading
from typing import Dict, List, Any, Optional
import importlib
import sys
import time
from datetime import datetime

from models.monitor_configuration import MonitorConfiguration

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
        # Add tracking for multiple streaming instances
        self.streaming_instances = {}  # combination_id -> DataStreamer instance
        self.data_links = {}  # combination_id -> DataLink instance

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

    def create_combination_id(self, symbol, monitor_config, config=None):
        """Create a unique identifier for a symbol-monitor combination"""
        # Try to use test_name from configuration if available
        if config and 'test_name' in config:
            return f"{symbol}-{config['test_name']}"

        # Fallback to monitor name or ID
        monitor_id = monitor_config.name or str(hash(str(monitor_config.indicators)))
        return f"{symbol}-{monitor_id}"

    def start_combination(self, symbol, indicators, weights=None, timeframe="1m", config=None):
        # Make sure modules are imported first
        if not hasattr(self, 'DataStreamer'):
            success = self._import_modules()
            if not success:
                raise ValueError("Failed to import required modules")

        # Fix: Import MonitorConfiguration directly here if needed
        from models.monitor_configuration import MonitorConfiguration

        # Create monitor configuration using the imported class directly
        config_name = f"{symbol}_config_{len(self.streaming_instances)}"
        if config is not None:
            config_name = config.get('test_name', config_name)

        monitor_config = MonitorConfiguration(
            name=config_name,
            indicators=indicators
        )

        # Create unique ID using test_name if available
        combination_id = f"{symbol}-{config_name}"
        data_link = self.SchwabDataLink()

        # Get authentication credentials from the auth_manager
        from .schwab_auth import SchwabAuthManager
        auth_manager = SchwabAuthManager()

        # Set authentication credentials
        if auth_manager.is_authenticated():
            data_link.access_token = auth_manager.access_token
            data_link.refresh_token = auth_manager.refresh_token
            data_link.user_prefs = auth_manager.user_prefs
        else:
            logger.error("Not authenticated with Schwab API")
            return None
        # Create DataStreamer for this combination
        model_config = {
            "feature_vector": [
                {"name": "close"},
                {"name": "open"},
                {"name": "high"},
                {"name": "low"}
            ],
            "normalization": None
        }

        data_streamer = self.DataStreamer(
            data_link=data_link,
            model_configuration=model_config,
            indicator_configuration=monitor_config,
            combination_id=combination_id
        )

        # Connect UI tool
        data_streamer.connect_tool(self.ui_tool)

        # Update UI tool weights for this combination
        if weights:
            self.ui_tool.update_weights(weights, combination_id)

        # Initialize with historical data
        data_streamer.initialize([symbol], timeframe)

        # Store instances
        self.streaming_instances[combination_id] = data_streamer
        self.data_links[combination_id] = data_link

        # Start streaming in a thread
        threading.Thread(
            target=self._stream_data,
            args=(combination_id,),
            daemon=True
        ).start()

        return combination_id

    def _stream_data(self, combination_id):
        """Run streaming for a specific combination"""
        data_streamer = self.streaming_instances.get(combination_id)
        data_link = self.data_links.get(combination_id)

        if not data_streamer or not data_link:
            return

        try:
            # Connect to streaming API for this combination
            if data_link.connect_stream():
                # Extract symbol from combination_id
                symbol = combination_id.split('-')[0]
                data_link.subscribe_charts([symbol], self.current_timeframe)

                # Run the DataStreamer
                data_streamer.run()
        except Exception as e:
            logger.error(f"Error in data streaming thread for {combination_id}: {e}")

    def stop_combination(self, combination_id):
        """Stop a specific combination"""
        # Implementation to stop a specific streaming instance
        pass

    def stop_all(self):
        """Stop all streaming combinations"""
        # Implementation to stop all streaming instances
        pass

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