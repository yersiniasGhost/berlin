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

        # Store reference to self for routing purposes
        self.instance_id = id(self)

    def process_tick(self, candle_aggregators: Dict[str, CandleAggregator]) -> None:
        """Process indicators for the given candle aggregators"""
        logger.info(f"DataStreamer.process_tick() called with {len(candle_aggregators)} aggregators")

        if self.indicators:
            logger.info(
                f"DataStreamer {self.instance_id}: Processing indicators with {len(candle_aggregators)} timeframes")

            try:
                indicator_results, raw_indicators, bar_scores = self.indicators.next_tick(candle_aggregators)
                logger.info(
                    f"DataStreamer {self.instance_id}: Got results - indicators: {len(indicator_results)}, bars: {len(bar_scores or {})}")
            except Exception as e:
                logger.error(f"Error in indicators.next_tick(): {e}")
                import traceback
                traceback.print_exc()
                return

            if indicator_results:
                # Get tick with symbol info from aggregators
                representative_tick: Optional[TickData] = None
                for timeframe, aggregator in candle_aggregators.items():
                    current_candle: Optional[TickData] = aggregator.get_current_candle()
                    if current_candle and hasattr(current_candle, 'symbol'):
                        representative_tick = current_candle
                        logger.info(
                            f"Using representative tick from {timeframe}: {current_candle.symbol} @ ${current_candle.close:.2f}")
                        break

                if not representative_tick:
                    logger.warning("No representative tick found")
                    return

                logger.info(f"Calling external tools: {len(self.external_tool)} tools")

                # Call external tools with routing information
                for i, external_tool in enumerate(self.external_tool):
                    # Check if this is our special UIExternalTool that needs routing
                    if hasattr(external_tool, 'indicator_vector_with_streamer'):
                        logger.info(f"Calling UIExternalTool #{i} with streamer reference")
                        # Call with streamer reference for routing
                        external_tool.indicator_vector_with_streamer(
                            indicators=indicator_results,
                            tick=representative_tick,
                            index=-1,
                            raw_indicators=raw_indicators,
                            bar_scores=bar_scores,
                            data_streamer=self
                        )
                    else:
                        logger.info(f"Calling standard external tool #{i}")
                        # Standard call for other external tools
                        external_tool.indicator_vector(
                            indicator_results,
                            representative_tick,
                            -1,
                            raw_indicators,
                            bar_scores
                        )
            else:
                logger.warning("No indicator results to process")
        else:
            logger.warning("No indicators processor configured")

    def connect_tool(self, external_tool: ExternalTool) -> None:
        """Connect an external tool to the data streamer"""
        self.external_tool.append(external_tool)

    def replace_external_tools(self, et: ExternalTool) -> None:
        """Replace all external tools with a single tool"""
        self.external_tool = [et]