# test_chart_handler.py
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

    # Create indicator configuration with all required parameters
    indicator_config = MonitorConfiguration(
        name="Simple Monitor",
        indicators=[
            {
                "name": "SMA Crossover",
                "type": "Indicator",
                "function": "sma_crossover",
                "parameters": {
                    "period": 10,
                    "crossover_value": 0.01,  # Added this required parameter
                    "trend": "bullish",       # Added this required parameter
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

    # # Initialize the preprocessor
    # data_streamer.preprocessor = DataPreprocessor(model_config)
    #
    # # Set the indicators processor
    # data_streamer.indicators = IndicatorProcessor(indicator_config)

    # Create and connect our printing tool
    printing_tool = PrintingTool()
    data_streamer.connect_tool(printing_tool)

    # First subscription (1-minute data)
    symbols = ["NVDA"]
    timeframe = "1m"
    logger.info(f"Subscribing to charts for {symbols} with timeframe {timeframe}")
    data_link.subscribe_charts(symbols, timeframe)

    # Second subscription (5-minute data)
    symbols2 = ["NVDA"]
    timeframe2 = "5m"  # Change this to "5m" for 5-minute data
    logger.info(f"Subscribing to charts for {symbols2} with timeframe {timeframe2}")
    data_link.subscribe_charts(symbols2, timeframe2)


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