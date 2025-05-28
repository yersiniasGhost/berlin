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

    def process_tick(self, candle_aggregators: Dict[str, CandleAggregator]) -> None:
        if self.indicators:
            indicator_results, raw_indicators, bar_scores = self.indicators.next_tick(candle_aggregators)

            if indicator_results:
                # Get tick with symbol info from aggregators
                representative_tick: Optional[TickData] = None
                for aggregator in candle_aggregators.values():
                    current_candle: Optional[TickData] = aggregator.get_current_candle()
                    if current_candle:
                        representative_tick = current_candle
                        break

                for external_tool in self.external_tool:
                    external_tool.indicator_vector(
                        indicator_results,
                        representative_tick,
                        -1,
                        raw_indicators,
                        bar_scores
                    )

    def connect_tool(self, external_tool: ExternalTool) -> None:
        """Connect an external tool to the data streamer"""
        self.external_tool.append(external_tool)

    def replace_external_tools(self, et: ExternalTool) -> None:
        """Replace all external tools with a single tool"""
        self.external_tool = [et]
