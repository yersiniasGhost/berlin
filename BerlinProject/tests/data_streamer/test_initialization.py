# test_data_streamer_initialize.py
import time
from datetime import datetime
from typing import Dict, List, Optional

from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.data_streamer import DataStreamer
from data_streamer.external_tool import ExternalTool
from environments.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration


class IndicatorDebugTool(ExternalTool):
    """Debug tool that captures and displays indicator values"""

    def __init__(self):
        self.indicator_values = []

    def feature_vector(self, fv: list, tick: TickData) -> None:
        pass

    def indicator_vector(self, indicators: Dict[str, float], tick: TickData, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        # Store the indicator values
        self.indicator_values.append({
            'tick': tick,
            'indicators': indicators,
            'raw_indicators': raw_indicators
        })

    def present_sample(self, sample: dict, index: int):
        pass

    def reset_next_sample(self):
        pass

    def print_summary(self):
        """Print a summary of indicator calculations"""
        print(f"\nTotal indicator calculations: {len(self.indicator_values)}")

        if not self.indicator_values:
            print("No indicator data available.")
            return

        # Print first 3 entries
        print("\nFirst 3 indicator calculations:")
        for i, entry in enumerate(self.indicator_values[:3]):
            tick = entry['tick']
            print(f"Entry {i + 1}:")
            print(f"  Symbol: {tick.symbol} @ {tick.timestamp}")
            print(f"  OHLC: O:{tick.open:.2f} H:{tick.high:.2f} L:{tick.low:.2f} C:{tick.close:.2f}")
            print(f"  Indicators: {entry['indicators']}")

        # Print last 3 entries
        print("\nLast 3 indicator calculations:")
        for i, entry in enumerate(self.indicator_values[-3:]):
            tick = entry['tick']
            idx = len(self.indicator_values) - 3 + i
            print(f"Entry {idx + 1}:")
            print(f"  Symbol: {tick.symbol} @ {tick.timestamp}")
            print(f"  OHLC: O:{tick.open:.2f} H:{tick.high:.2f} L:{tick.low:.2f} C:{tick.close:.2f}")
            print(f"  Indicators: {entry['indicators']}")


def main():
    print("Testing DataStreamer initialize function...")

    # Create and authenticate SchwabDataLink
    print("Creating and authenticating SchwabDataLink...")
    data_link = SchwabDataLink()

    if not data_link.authenticate():
        print("Authentication failed, exiting")
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
        name="Test Monitor",
        indicators=[
            {
                "name": "SMA Crossover",
                "type": "Indicator",
                "function": "sma_crossover",
                "parameters": {
                    "period": 10,
                    "crossover_value": 0.01,
                    "trend": "bullish",
                    "lookback": 10
                }
            }
        ]
    )

    # Create DataStreamer
    print("Creating DataStreamer...")
    data_streamer = DataStreamer(
        data_link=data_link,
        model_configuration=model_config,
        indicator_configuration=indicator_config
    )

    # Create debug tool to capture indicator values
    debug_tool = IndicatorDebugTool()
    data_streamer.connect_tool(debug_tool)

    # Define symbols to initialize
    symbols = ["NVDA"]
    timeframe = "1m"

    # Call initialize function
    print(f"Initializing DataStreamer with historical data for {symbols}...")
    success = data_streamer.initialize(symbols, timeframe)

    # Print results
    if success:
        print("DataStreamer initialization successful!")
    else:
        print("DataStreamer initialization failed!")

    # Print information about the preprocessor's history
    history_size = len(data_streamer.preprocessor.history)

    print(f"\nPreprocessor history size: {history_size} ticks")

    if history_size > 0:
        print("\nHistory time range:")
        first_tick = data_streamer.preprocessor.history[0]
        last_tick = data_streamer.preprocessor.history[-1]
        print(f"  From: {first_tick.timestamp}")
        print(f"  To: {last_tick.timestamp}")
        print(f"  Duration: {last_tick.timestamp - first_tick.timestamp}")

    # Print information about calculated indicators
    debug_tool.print_summary()

    print("\nTest completed!")


if __name__ == "__main__":
    main()