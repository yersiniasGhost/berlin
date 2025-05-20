from datetime import datetime
import time
from typing import List, Optional, Tuple
import logging

from environments.tick_data import TickData
from data_streamer.data_streamer import DataLink

# Configure at module level
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DataStreamer')

from mongo_tools.sample_tools import SampleTools
from data_streamer.data_streamer import DataPreprocessor
from data_streamer.data_streamer import IndicatorProcessor
from models.monitor_configuration import MonitorConfiguration
from data_streamer.data_streamer import ExternalTool


class DataStreamer:
    def __init__(self, data_link: DataLink, model_configuration: dict,
                 indicator_configuration: Optional[MonitorConfiguration] = None):
        self.preprocessor = DataPreprocessor(model_configuration)
        # self.feature_vector_calculator = FeatureVectorCalculator(model_configuration)
        self.indicators: Optional[IndicatorProcessor] = IndicatorProcessor(
            indicator_configuration) if indicator_configuration else None
        self.data_link: DataLink = data_link
        self.data_link.add_chart_handler(self.chart_handler)
        self.external_tool: List[ExternalTool] = []
        self.reset_after_sample: bool = False

        # Store the required timeframes for this streamer
        if indicator_configuration:
            self.required_timeframes = indicator_configuration.get_time_increments()
        else:
            self.required_timeframes = {"1m"}  # Default to 1-minute timeframe

    def initialize(self, symbols: List[str], timeframe: str = "1m") -> bool:
        """
        Initialize the data streamer with historical data for all required timeframes

        Args:
            symbols: List of symbols to initialize
            timeframe: Deprecated, kept for backward compatibility
        """
        # Log all required timeframes
        logger.info(f"Initializing with timeframes: {self.required_timeframes}")

        # Initialize for each symbol
        for symbol in symbols:
            # Load and process historical data for each required timeframe
            for time_increment in self.required_timeframes:
                logger.info(f"Loading {time_increment} historical data for {symbol}")
                history = self.data_link.load_historical_data(symbol, time_increment)

                if not history:
                    logger.warning(f"No {time_increment} historical data found for {symbol}")
                    continue

                logger.info(f"Processing {len(history)} historical candles for {symbol} at {time_increment}")

                # Add timeframe information to each tick if not already present
                for tick in history:
                    if not hasattr(tick, 'time_increment'):
                        tick.time_increment = time_increment

                    # Process tick through the pipeline
                    self.preprocessor.next_tick(tick)

                    # Calculate indicators
                    if self.indicators:
                        indicator_results, raw_indicators = self.indicators.next_tick(self.preprocessor)

                        # Notify external tools about indicators
                        for external_tool in self.external_tool:
                            external_tool.indicator_vector(indicator_results, tick, 0, raw_indicators)

        return True

    def run(self):
        """
        Start the DataStreamer and begin processing real-time data.
        """
        # Register our chart handler with the data link
        self.data_link.add_chart_handler(self.chart_handler)

        logger.info("DataStreamer is now running and processing real-time data")

        try:
            # This will keep the main thread alive
            # The chart_handler will be called in a background thread when data arrives
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("DataStreamer stopped by user")
        except Exception as e:
            logger.error(f"Error in DataStreamer: {e}")
            import traceback
            traceback.print_exc()

    def tick_converter(self, data: dict) -> Optional[TickData]:
        """
        Convert Schwab chart data to a TickData object.

        Args:
            data: Raw chart data from Schwab API

        Returns:
            TickData object or None if conversion fails
        """
        try:
            # Extract data from the chart entry
            symbol = data.get('key', '')
            if not symbol:
                logger.warning("Received chart data without symbol key")
                return None

            # Extract timestamp
            timestamp_ms = int(data.get('7', 0))
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000)

            # Extract OHLCV data
            open_price = float(data.get('2', 0.0))
            high_price = float(data.get('3', 0.0))
            low_price = float(data.get('4', 0.0))
            close_price = float(data.get('5', 0.0))
            volume = float(data.get('6', 0))

            # Create TickData object with default timeframe (1m for real-time data)
            tick = TickData(
                symbol=symbol,
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
                time_increment="1m"  # Default timeframe for real-time data
            )

            logger.info(f"Converted chart data for {symbol} at {timestamp}")
            return tick

        except Exception as e:
            logger.error(f"Error converting chart data: {e}")
            return None

    def chart_handler(self, data):
        """
        Process chart data from the data link.
        Converts chart data to TickData, adds it to history, and processes indicators.
        """
        try:
            # Extract symbol from data and check if it's one we care about
            symbol = data.get('key', '')
            if not hasattr(self, 'configured_symbols') or symbol not in self.configured_symbols:
                return  # Skip if this isn't one of our symbols

            # Convert incoming data to TickData
            tick = self.tick_converter(data)
            if not tick:
                return

            # Check if the timeframe is one we need
            if tick.time_increment not in self.required_timeframes:
                return  # Skip if this timeframe is not required by this streamer

            # Use next_tick to properly add to history
            self.preprocessor.next_tick(tick)

            # Notify external tools about the completed candle
            for external_tool in self.external_tool:
                if hasattr(external_tool, 'handle_completed_candle'):
                    external_tool.handle_completed_candle(tick.symbol, tick)

            # Process indicators
            if self.indicators:
                # Calculate indicators for this tick
                indicator_results, raw_indicators = self.indicators.next_tick(self.preprocessor)

                # Notify external tools about the indicator results
                if indicator_results:
                    # Use the full history length as the index
                    history_index = len(self.preprocessor.history) - 1
                    for external_tool in self.external_tool:
                        external_tool.indicator_vector(indicator_results, tick, history_index, raw_indicators)

        except Exception as e:
            logger.error(f"Error in chart handler: {e}")
            import traceback
            traceback.print_exc()

    def reset(self):
        """Reset internal state"""
        self.data_link.reset_index()
        stats = self.data_link.get_stats()
        self.preprocessor.reset_state(stats)

    def connect_tool(self, external_tool: ExternalTool) -> None:
        """Connect an external tool to the data streamer"""
        self.external_tool.append(external_tool)

    def replace_external_tools(self, et: ExternalTool) -> None:
        """Replace all external tools with a single tool"""
        self.external_tool = [et]

    def get_present_sample(self) -> Tuple[dict, int]:
        """Get the current sample and its index (for SampleTools only)"""
        if not isinstance(self.data_link, SampleTools):
            return None, None
        return self.data_link.get_present_sample_and_index()