# test_schwab_data_processing.py
import time
import logging
from typing import Dict, Optional, List

from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.data_streamer import DataStreamer
from data_streamer.data_preprocessor import DataPreprocessor
from data_streamer.indicator_processor import IndicatorProcessor
from data_streamer.external_tool import ExternalTool
from environments.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TestSchwabProcessing')


# Simple external tool that just prints data
class PrintingTool(ExternalTool):
    def feature_vector(self, fv: list, tick: TickData) -> None:
        # We're skipping feature vector output
        pass

    def indicator_vector(self, indicators: Dict[str, float], tick: TickData, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        print("\n=== INDICATORS ===")
        print(f"Tick: {tick.symbol} @ {tick.timestamp}")
        print(f"OHLC: O:{tick.open:.2f} H:{tick.high:.2f} L:{tick.low:.2f} C:{tick.close:.2f} V:{tick.volume}")
        print(f"Processed indicators: {indicators}")
        if raw_indicators:
            print(f"Raw indicators: {raw_indicators}")
        print("=================\n")

    def present_sample(self, sample: dict, index: int):
        pass

    def reset_next_sample(self):
        pass


def main():
    # Create and authenticate SchwabDataLink
    logger.info("Creating and authenticating SchwabDataLink...")
    data_link = SchwabDataLink()

    if not data_link.authenticate():
        logger.error("Authentication failed, exiting")
        return

    # Connect to streaming API
    logger.info("Connecting to streaming API...")
    if not data_link.connect_stream():
        logger.error("Failed to connect to streaming API")
        return

    # Create model configuration
    model_config = {
        "feature_vector": [
            {"name": "open"},
            {"name": "high"},
            {"name": "low"},
            {"name": "close"},
        ],
        "normalization": None
    }

    # Create indicator configuration
    indicator_config = MonitorConfiguration(
        name="Simple Monitor",
        indicators=[
            {
                "name": "SMA Crossover",
                "type": "Indicator",
                "function": "sma_crossover",
                "parameters": {
                    "period": 10,
                    "fast_period": 5,
                    "slow_period": 20,
                    "lookback": 10
                }
            }
        ]
    )

    # Create the DataStreamer with the components
    logger.info("Creating DataStreamer...")
    data_streamer = DataStreamer(
        data_link=data_link,
        model_configuration=model_config,
        indicator_configuration=indicator_config
    )

    # Initialize the preprocessor
    data_streamer.preprocessor = DataPreprocessor(model_config)

    # Don't set feature_vector_calculator since it's commented out
    # data_streamer.feature_vector_calculator = FeatureVectorCalculator(model_config)

    data_streamer.indicators = IndicatorProcessor(indicator_config)

    # Create and connect our printing tool
    printing_tool = PrintingTool()
    data_streamer.connect_tool(printing_tool)

    # Subscribe to charts
    symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "SPY"]
    timeframe = "1m"

    logger.info(f"Subscribing to charts for: {symbols}")
    data_link.subscribe_charts(symbols, timeframe)

    try:
        # Keep running until interrupted
        logger.info("Waiting for chart data...")
        logger.info("Press Ctrl+C to stop")
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Stopping...")
        data_link.disconnect()


if __name__ == "__main__":
    main()