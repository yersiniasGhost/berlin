from datetime import datetime, time
from typing import List, Dict, Optional, Tuple, Union
import logging

from environments.tick_data import TickData
from .data_link import DataLink

# Configure at module level
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SchwabDataLink')  # Replace with appropriate name for each file
from mongo_tools.tick_history_tools_copy import TickHistoryTools
from .feature_vector_calculator import FeatureVectorCalculator
from mongo_tools.sample_tools import SampleTools
from .data_preprocessor import DataPreprocessor
from .indicator_processor_historical import IndicatorProcessorHistorical
from .indicator_processor import IndicatorProcessor
from models.monitor_configuration import MonitorConfiguration
from data_streamer.external_tool import ExternalTool
from .schwab_data_link import SchwabDataLink

# TODO: reinstate feature vector in the future.

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

    def initialize(self, symbols: List[str], timeframe: str = "1m") -> bool:
        """
        Initialize the DataStreamer with historical data.
        Uses the DataPreprocessor's history to calculate indicators.

        Args:
            symbols: List of stock symbols to initialize
            timeframe: Candle timeframe (e.g., "1m", "5m")

        Returns:
            bool: Success status
        """
        if not hasattr(self.data_link, 'load_historical_data'):
            return False

        # First initialize the preprocessor with historical data
        success = self.preprocessor.initialize(self.data_link, symbols, timeframe)

        if not success or not self.preprocessor.history:
            return False

        # Now process the historical data through the indicator processor
        if self.indicators:
            try:
                # Process each historical tick through indicators
                for i, tick in enumerate(self.preprocessor.history):
                    # Need to ensure the current tick is set before calculating indicators
                    self.preprocessor.tick = tick

                    # Calculate indicators for this tick
                    indicator_results, raw_indicators = self.indicators.next_tick(self.preprocessor)

                    # Important: Notify external tools about the indicator results
                    if indicator_results:
                        for external_tool in self.external_tool:
                            external_tool.indicator_vector(indicator_results, tick, i, raw_indicators)

            except Exception as e:
                import traceback
                traceback.print_exc()
                return False

        return True

    def run(self):
        """
        Start the DataStreamer and begin processing real-time tick data.
        This connects to the data link and processes incoming ticks.
        """

        # Register our chart handler with the data link
        self.data_link.add_chart_handler(self.chart_handler)

        print("DataStreamer is now running and processing real-time data")

        try:
            # This will keep the main thread alive
            # The chart_handler will be called in a background thread when data arrives
            while True:
                time.sleep(0.5)

        except KeyboardInterrupt:
            print("DataStreamer stopped by user")
        except Exception as e:
            print(f"Error in DataStreamer: {e}")
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

            # Create TickData object
            tick = TickData(
                symbol=symbol,
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume
            )

            logger.info(f"Converted chart data for {symbol} at {timestamp}")
            return tick

        except Exception as e:
            logger.error(f"Error converting chart data: {e}")
            return None

    def chart_handler(self, data: dict):
        """
        Process chart data from the data link.
        Converts chart data to TickData, adds it to history, and processes indicators.
        """
        try:
            # Convert incoming data to TickData
            tick = self.tick_converter(data)
            if not tick:
                return

            # APPEND the tick to the preprocessor's history instead of replacing it
            self.preprocessor.history.append(tick)

            # Update the current tick in preprocessor
            self.preprocessor.tick = tick

            # Process indicators
            if self.indicators:
                # Calculate indicators for this tick
                indicator_results, raw_indicators = self.indicators.next_tick(self.preprocessor)

                # Notify external tools about the indicator results
                if indicator_results:
                    for external_tool in self.external_tool:
                        external_tool.indicator_vector(indicator_results, tick, len(self.preprocessor.history) - 1,
                                                       raw_indicators)

        except Exception as e:
            print(f"Error in chart handler: {e}")
            import traceback
            traceback.print_exc()


    # def run2(self, data_link):
    #     """
    #     Alternative method to run the data streaming process with Schwab data.
    #     """
    #     data_link = SchwabDataLink()
    #
    #     if not data_link.authenticate():
    #         logger.error("Authentication failed, exiting")
    #         return
    #
    #     # Connect to streaming API
    #     if not data_link.connect_stream():
    #         logger.error("Failed to connect to streaming API")
    #         return

    # Add this to your DataStreamer class:
    def run(self):
        """
        Main method to run the data streaming process.
        Retrieves data from the configured data link and processes it.
        """
        if self.data_link is None:
            raise ValueError("Data link is not initialized")
        if not self.external_tool:
            raise ValueError("External tool is not connected")

        # Set the sample state on the data preprocessor so it can normalize the data
        sample_stats = self.data_link.get_stats()
        self.preprocessor.reset_state(sample_stats)

        # Counter for ticks processed
        index = 0

        # Process each tick from the data link
        try:
            logger.info("DataStreamer: Starting to process data")
            for result in self.data_link.serve_next_tick():
                if result is None or result[0] is None:
                    logger.debug("DataStreamer: Received None result, continuing")
                    continue

                # Unpack the result
                tick, tick_index, day_index = result

                # Skip if we received a None tick (end of episode marker)
                if tick is None:
                    logger.debug("DataStreamer: Received None tick (end of episode)")
                    # End of sample or day boundary
                    if self.reset_after_sample:
                        index = 0
                        for external_tool in self.external_tool:
                            external_tool.reset_next_sample()
                        self.preprocessor.reset_state(sample_stats)
                    continue

                # Ensure tick has a symbol
                if hasattr(self.data_link, 'symbols') and day_index < len(self.data_link.symbols):
                    symbol = self.data_link.symbols[day_index]
                    # If tick doesn't have symbol attribute or it's not set
                    if not hasattr(tick, 'symbol') or not tick.symbol:
                        try:
                            # Try to set symbol directly
                            tick.symbol = symbol
                        except AttributeError:
                            # If can't set directly, add it as an attribute
                            setattr(tick, 'symbol', symbol)

                logger.debug(f"DataStreamer: Processing tick {index} for symbol: {getattr(tick, 'symbol', 'Unknown')}")

                # Check if this is a completed candle
                is_completed_candle = (hasattr(tick, 'open') and hasattr(tick, 'high') and
                                       hasattr(tick, 'low') and hasattr(tick, 'close') and
                                       not getattr(tick, 'is_current', False))

                # Process the tick through the data pipeline
                self.preprocessor.next_tick(tick)
                feature_vector = self.feature_vector_calculator.next_tick(self.preprocessor)

                # Process indicators only for completed candles
                indicator_results = {}
                raw_indicators = None
                if is_completed_candle and self.indicators:
                    indicator_results, raw_indicators = self.indicators.next_tick(self.preprocessor)

                # Send feature vector to external tools if valid
                if feature_vector and None not in feature_vector:
                    for external_tool in self.external_tool:
                        external_tool.feature_vector(feature_vector, tick)

                    # Get and send sample data if available
                    sample, sample_index = self.get_present_sample()
                    if sample:
                        for external_tool in self.external_tool:
                            external_tool.present_sample(sample, sample_index)

                # Send indicator results to external tools if available (only for completed candles)
                if is_completed_candle and indicator_results:
                    for external_tool in self.external_tool:
                        external_tool.indicator_vector(indicator_results, tick, index, raw_indicators)

                index += 1

        except KeyboardInterrupt:
            logger.info("DataStreamer: Data streaming interrupted by user")
        except Exception as e:
            logger.error(f"DataStreamer: Error during data streaming: {e}")
            import traceback
            traceback.print_exc()
            raise

    def reset(self):
        self.data_link.reset_index()
        stats = self.data_link.get_stats()
        self.preprocessor.reset_state(stats)

    # Used for training of the RL Agents
    def get_next(self):
        if self.data_link is None:
            raise ValueError("Data link is not initialized")
        bad_fv = True
        while bad_fv:
            tick = self.data_link.get_next2()
            if tick is None:
                return [None], None
            self.preprocessor.next_tick(tick)
            fv = self.feature_vector_calculator.next_tick(self.preprocessor)
            bad_fv = None in fv
        return fv, tick

    def connect_tool(self, external_tool: ExternalTool) -> None:
        self.external_tool.append(external_tool)

    def replace_external_tools(self, et: ExternalTool) -> None:
        self.external_tool = [et]

    def get_present_sample(self) -> Tuple[dict, int]:
        if not isinstance(self.data_link, SampleTools):
            return None, None
        return self.data_link.get_present_sample_and_index()
