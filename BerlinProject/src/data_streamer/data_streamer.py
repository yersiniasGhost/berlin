from datetime import datetime
from typing import List, Dict, Optional, Tuple, Union

from mongo_tools.tick_history_tools_copy import TickHistoryTools
from .feature_vector_calculator import FeatureVectorCalculator
from mongo_tools.sample_tools import SampleTools
from .data_preprocessor import DataPreprocessor
from .indicator_processor_historical import IndicatorProcessorHistorical
from .indicator_processor import IndicatorProcessor
from models.monitor_configuration import MonitorConfiguration
from data_streamer.external_tool import ExternalTool
from .schwab_data_link import SchwabDataLink


class DataStreamer:
    def __init__(self, data_configuration: dict, model_configuration: dict,
                 indicator_configuration: Optional[MonitorConfiguration] = None):
        self.preprocessor = DataPreprocessor(model_configuration)
        self.feature_vector_calculator = FeatureVectorCalculator(model_configuration)
        self.indicators: Optional[IndicatorProcessor] = IndicatorProcessor(
            indicator_configuration) if indicator_configuration else None
        self.data_link: Optional[Union[TickHistoryTools, SampleTools]] = None
        self.configure_data(data_configuration)
        self.external_tool: List[ExternalTool] = []
        self.reset_after_sample: bool = False

    def replace_monitor_configuration(self, monitor: MonitorConfiguration, historical: bool = True):
        if historical:
            self.indicators = IndicatorProcessorHistorical(monitor, self.data_link)
        else:
            self.indicators = IndicatorProcessor(monitor)

    def configure_data(self, data_config: dict) -> None:
        """
        Configure the data source based on the provided configuration.

        Args:
            data_config: Configuration dictionary for the data source
        """
        data_type = data_config.get('type', None)

        if data_type == "TickHistory":
            ticker = data_config.get('ticker')
            start_date_str = data_config.get('start_date')
            end_date_str = data_config.get('end_date')
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            time_increments = data_config.get('time_increment')

            self.data_link = TickHistoryTools.get_tools(ticker, start_date, end_date, time_increments)

        elif data_type == "CharlesSchwab":
            # Extract Schwab specific configuration
            user_prefs = data_config.get('user_prefs', {})
            access_token = data_config.get('access_token', '')
            symbols = data_config.get('symbols', [])

            if not user_prefs or not access_token or not symbols:
                raise ValueError("Missing required CharlesSchwab configuration parameters")

            self.data_link = SchwabDataLink(user_prefs, access_token, symbols)

        elif data_type == "Sample":
            # If data_config is a dictionary with 'samples' key
            if isinstance(data_config, dict) and 'samples' in data_config:
                self.data_link = SampleTools.get_samples2(data_config.get('samples'))
            # If data_config is or contains a list to be passed directly
            elif isinstance(data_config, list):
                self.data_link = SampleTools.get_samples2(data_config)
            elif isinstance(data_config, dict) and isinstance(data_config.get(0), dict):
                self.data_link = SampleTools.get_samples2(data_config[0])
            else:
                raise ValueError(f"Invalid Sample data configuration format: {data_config}")
        else:
            raise ValueError(f"Unknown data source type: {data_type}")

    def prepare_historical_processors(self):
        # for indicator in self.indicators:
        #     indicator.prepare_historical_processor(self.data_link)
        self.indicators.prepare_historical_processor(self.data_link)

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
            for result in self.data_link.serve_next_tick():
                if result is None:
                    # Handle None result (WebSocket might return None)
                    continue

                # Unpack the result
                tick, tick_index, day_index = result

                # Skip if we received a None tick (end of episode marker)
                if tick is None:
                    # End of sample or day boundary
                    if self.reset_after_sample:
                        index = 0
                        for external_tool in self.external_tool:
                            external_tool.reset_next_sample()
                        self.preprocessor.reset_state(sample_stats)
                    continue

                # Process the tick through the data pipeline
                self.preprocessor.next_tick(tick)
                feature_vector = self.feature_vector_calculator.next_tick(self.preprocessor)

                # Process indicators if available
                indicator_results = {}
                raw_indicators = None
                if self.indicators:
                    indicator_results, raw_indicators = self.indicators.next_tick(self.preprocessor)

                # Send feature vector to external tools if valid
                if None not in feature_vector and feature_vector:
                    for external_tool in self.external_tool:
                        external_tool.feature_vector(feature_vector, tick)

                    # Get and send sample data if available
                    sample, sample_index = self.get_present_sample()
                    if sample:
                        for external_tool in self.external_tool:
                            external_tool.present_sample(sample, sample_index)

                # Send indicator results to external tools if available
                if indicator_results:
                    for external_tool in self.external_tool:
                        external_tool.indicator_vector(indicator_results, tick, index, raw_indicators)

                index += 1

        except KeyboardInterrupt:
            self.logger.info("Data streaming interrupted by user")
            print("\nData streaming interrupted by user")
        except Exception as e:
            self.logger.error(f"Error during data streaming: {e}")
            print(f"\nError during data streaming: {e}")
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
