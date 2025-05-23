from datetime import datetime
import time
from typing import List, Optional, Tuple, Dict
import logging
from data_streamer.candle_aggregator import CandleAggregator

from environments.tick_data import TickData

# Configure at module level
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DataStreamer')

from mongo_tools.sample_tools import SampleTools
from data_streamer.indicator_processor import IndicatorProcessor
from models.monitor_configuration import MonitorConfiguration
from data_streamer.external_tool import ExternalTool


class DataStreamer:
    def __init__(self, model_configuration: dict,
                 indicator_configuration: Optional[MonitorConfiguration] = None):
        # self.feature_vector_calculator = FeatureVectorCalculator(model_configuration)
        self.indicators: Optional[IndicatorProcessor] = IndicatorProcessor(
            indicator_configuration) if indicator_configuration else None
        self.external_tool: List[ExternalTool] = []
        self.reset_after_sample: bool = False

    def process_tick(self, candle_aggregators: Dict[str, CandleAggregator]):
        if self.indicators:
            # Calculate indicators for this tick
            indicator_results, raw_indicators = self.indicators.next_tick(candle_aggregators)
            if indicator_results:
                # Use the full history length as the index
                for external_tool in self.external_tool:
                    external_tool.indicator_vector(indicator_results, None, -1, raw_indicators)

    def connect_tool(self, external_tool: ExternalTool) -> None:
        """Connect an external tool to the data streamer"""
        self.external_tool.append(external_tool)

    def replace_external_tools(self, et: ExternalTool) -> None:
        """Replace all external tools with a single tool"""
        self.external_tool = [et]
