# test_data_streamer_run.py
import time
from datetime import datetime
from typing import Dict, List, Optional

from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.data_streamer import DataStreamer
from data_streamer.external_tool import ExternalTool
from environments.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration


class HistoryMonitorTool(ExternalTool):
    """Simple external tool that monitors history and indicator values"""

    def __init__(self):
        self.indicator_values = []

    def feature_vector(self, fv: list, tick: TickData) -> None:
        # We don't care about feature vectors for this test
        pass

    def indicator_vector(self, indicators: Dict[str, float], tick: TickData, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        # Store the indicator values with timestamp
        self.indicator_values.append({
            'tick': tick,
            'indicators': indicators,
            'timestamp': datetime.now()
        })

        # Print a simple notification
        print(f"New indicator calculation: {tick.symbol} @ {tick.timestamp} - {indicators}")

    def present_sample(self, sample: dict, index: int):
        pass

    def reset_next_sample(self):
        pass

    def print_summary(self, data_streamer):
        """Print a summary of the history and indicator values"""
        history = data_streamer.preprocessor.history

        print("\n" + "=" * 60)
        print(f"SUMMARY at {datetime.now()}")
        print("=" * 60)

        # History summary
        print(f"History size: {len(history)} ticks")
        if history:
            first_tick = history[0]
            last_tick = history[-1]
            print(f"Time range: {first_tick.timestamp} to {last_tick.timestamp}")
            print(f"Duration: {last_tick.timestamp - first_tick.timestamp}")

        # Indicator summary
        print(f"\nIndicator calculations: {len(self.indicator_values)}")
        if self.indicator_values:
            # Count occurrences of each indicator value
            indicator_counts = {}
            for item in self.indicator_values:
                for indicator_name, value in item['indicators'].items():
                    # Check for NaN without using pandas
                    if isinstance(value, float) and value != value:  # NaN check
                        rounded_value = "NaN"
                    else:
                        try:
                            rounded_value = round(value, 2)
                        except:
                            rounded_value = value

                    key = f"{indicator_name}:{rounded_value}"
                    indicator_counts[key] = indicator_counts.get(key, 0) + 1
            # Print most common indicator values
            print("Most common indicator values:")
            for key, count in sorted(indicator_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  {key}: {count} occurrences")

        # Latest data
        if history:
            print("\nLatest 3 ticks in history:")
            for tick in history[-3:]:
                print(f"  {tick.symbol} @ {tick.timestamp}: "
                      f"OHLC({tick.open:.2f},{tick.high:.2f},{tick.low:.2f},{tick.close:.2f})")

        print("=" * 60)


def main():
    print("Testing DataStreamer with initialize and run...")

    # Create and authenticate SchwabDataLink
    print("Creating and authenticating SchwabDataLink...")
    data_link = SchwabDataLink()

    if not data_link.authenticate():
        print("Authentication failed, exiting")
        return

    # Connect to streaming API
    print("Connecting to streaming API...")
    if not data_link.connect_stream():
        print("Failed to connect to streaming API")
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

    # Create and connect our monitoring tool
    monitor = HistoryMonitorTool()
    data_streamer.connect_tool(monitor)

    # Define symbols to track
    symbols = ["NVDA"]
    timeframe = "1m"

    # Step 1: Initialize with historical data
    print(f"Initializing DataStreamer with historical data for {symbols}...")
    success = data_streamer.initialize(symbols, timeframe)

    if not success:
        print("Initialization failed, exiting")
        return

    print(f"Initialization successful! Loaded {len(data_streamer.preprocessor.history)} historical ticks")

    # Print initial summary
    print("\nInitial state after initialization:")
    monitor.print_summary(data_streamer)

    # Step 2: Subscribe to real-time data
    print(f"\nSubscribing to {symbols} with {timeframe} timeframe...")
    data_link.subscribe_charts(symbols, timeframe)

    # Step 3: Run the DataStreamer
    print("\nStarting DataStreamer run...")

    # Start the run in a non-blocking way
    try:
        # We'll run for a fixed time period, then print final summary
        run_duration = 60  # seconds
        print(f"Will run for {run_duration} seconds to collect real-time data...")

        # Start running in a way that doesn't block
        import threading
        run_thread = threading.Thread(target=data_streamer.run)
        run_thread.daemon = True
        run_thread.start()

        # Wait for the specified duration
        time.sleep(run_duration)

        # Print final summary
        print("\nFinal state after running:")
        monitor.print_summary(data_streamer)

    except KeyboardInterrupt:
        print("\nTest stopped by user")

    print("\nTest completed!")


if __name__ == "__main__":
    main()