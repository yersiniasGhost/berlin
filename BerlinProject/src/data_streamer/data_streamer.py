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
    def __init__(self, combination_id: str, model_configuration: dict,
                 indicator_configuration: Optional[MonitorConfiguration] = None):
        # Store the combination_id - this is the routing key!
        self.combination_id = combination_id

        # Rest of the initialization stays the same
        self.indicators: Optional[IndicatorProcessor] = IndicatorProcessor(
            indicator_configuration) if indicator_configuration else None
        self.external_tools: List[ExternalTool] = []
        self.reset_after_sample: bool = False

        # Store reference to self for routing purposes
        self.instance_id = id(self)

        logger.info(f"Created DataStreamer with combination_id: {combination_id}")

    def process_tick(self, candle_aggregators: Dict[str, CandleAggregator]) -> None:
        """Process indicators for the given candle aggregators"""
        logger.debug(
            f"DataStreamer.process_tick() called for {self.combination_id} with {len(candle_aggregators)} aggregators")

        if self.indicators:
            logger.debug(
                f"DataStreamer {self.instance_id} ({self.combination_id}): Processing indicators with {len(candle_aggregators)} timeframes")

            try:
                indicator_results, raw_indicators, bar_scores = self.indicators.next_tick(candle_aggregators)
                logger.debug(
                    f"DataStreamer {self.instance_id} ({self.combination_id}): Got results - indicators: {len(indicator_results)}, bars: {len(bar_scores or {})}")
            except Exception as e:
                logger.error(f"Error in indicators.next_tick() for {self.combination_id}: {e}")
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
                        logger.debug(
                            f"Using representative tick from {timeframe}: {current_candle.symbol} @ ${current_candle.close:.2f}")
                        break

                if not representative_tick:
                    logger.warning(f"No representative tick found for {self.combination_id}")
                    return

                logger.debug(f"Calling external tools for {self.combination_id}: {len(self.external_tools)} tools")

                # Call external tools with combination_id - THE KEY CHANGE!
                for i, external_tool in enumerate(self.external_tools):
                    try:
                        logger.debug(f"Calling external tool #{i} for {self.combination_id}")
                        external_tool.indicator_vector(
                            combination_id=self.combination_id,  # Pass the ID explicitly
                            indicators=indicator_results,
                            tick=representative_tick,
                            raw_indicators=raw_indicators,
                            bar_scores=bar_scores
                        )
                    except Exception as e:
                        logger.error(f"Error calling external tool #{i} for {self.combination_id}: {e}")
                        import traceback
                        traceback.print_exc()
            else:
                logger.warning(f"No indicator results to process for {self.combination_id}")
        else:
            logger.warning(f"No indicators processor configured for {self.combination_id}")

    def connect_tool(self, external_tool: ExternalTool) -> None:
        """Connect an external tool to the data streamer"""
        self.external_tools.append(external_tool)
        logger.info(f"Connected external tool to DataStreamer {self.combination_id}")

    def replace_external_tools(self, et: ExternalTool) -> None:
        """Replace all external tools with a single tool"""
        self.external_tools = [et]
        logger.info(f"Replaced external tools for DataStreamer {self.combination_id}")