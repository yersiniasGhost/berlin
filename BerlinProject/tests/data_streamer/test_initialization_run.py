import time
from datetime import datetime
from typing import Dict, List, Optional
from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.data_streamer import DataStreamer
from data_streamer.external_tool import ExternalTool
from environments.tick_data import TickData
from models.monitor_configuration import MonitorConfiguration, IndicatorDefinition
from config.types import INDICATOR_TYPE


class DebugMonitorTool(ExternalTool):
    """Debug external tool that monitors history and indicator values"""

    def __init__(self):
        self.indicator_values = []
        self.indicator_calls = 0
        self.feature_calls = 0

    def feature_vector(self, fv: list, tick: TickData) -> None:
        self.feature_calls += 1
        print(f"Feature vector called: {self.feature_calls} times")

    def indicator_vector(
        self,
        indicators: Dict[str, float],
        tick: TickData,
        index: int,
        raw_indicators: Optional[Dict[str, float]] = None
    ) -> None:
        self.indicator_calls += 1

        call_data = {
            'index': index,
            'timestamp': tick.timestamp if hasattr(tick, 'timestamp') else None,
            'price': tick.close if hasattr(tick, 'close') else None,
            'indicators': indicators.copy() if indicators else {},
            'raw_indicators': raw_indicators.copy() if raw_indicators else None
        }

        self.indicator_values.append(call_data)

        print(f"\n===== INDICATOR CALL #{self.indicator_calls} =====")
        print(f"Tick Index: {index}")
        print(f"Timestamp: {call_data['timestamp']}")
        print(f"Close Price: {call_data['price']}")

        if indicators:
            print("\nINDICATOR VALUES:")
            for name, value in indicators.items():
                print(f"  {name}: {value}")

            if raw_indicators:
                print("\nRAW INDICATOR VALUES:")
                for name, value in raw_indicators.items():
                    print(f"  {name}: {value}")
        else:
            print("No indicator values received")

        print("=" * 40)

    def present_sample(self, sample: dict, index: int):
        pass

    def reset_next_sample(self):
        pass

    def print_summary(self, data_streamer):
        """Print a summary of the history and indicator values"""
        history = data_streamer.preprocessor.history

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)

        print(f"History size: {len(history)} ticks")
        if history:
            first_tick = history[0]
            last_tick = history[-1]
            print(f"Time range: {first_tick.timestamp} to {last_tick.timestamp}")
            if hasattr(last_tick, 'timestamp') and hasattr(first_tick, 'timestamp'):
                print(f"Duration: {last_tick.timestamp - first_tick.timestamp}")

        print(f"\nIndicator calculations: {len(self.indicator_values)}")
        print(f"Feature vector calls: {self.feature_calls}")

        if self.indicator_values:
            trigger_counts = {}
            for item in self.indicator_values:
                for indicator_name, value in item['indicators'].items():
                    if value > 0:
                        trigger_counts[indicator_name] = trigger_counts.get(indicator_name, 0) + 1

            print("\nTRIGGER COUNTS (values > 0):")
            for name, count in trigger_counts.items():
                percentage = (count / self.indicator_calls) * 100 if self.indicator_calls else 0
                print(f"  {name}: {count} triggers ({percentage:.1f}%)")

            print("\nINDICATOR VALUE RANGES:")
            value_ranges = {}
            for item in self.indicator_values:
                for indicator_name, value in item['indicators'].items():
                    if indicator_name not in value_ranges:
                        value_ranges[indicator_name] = {'min': value, 'max': value}
                    else:
                        value_ranges[indicator_name]['min'] = min(value_ranges[indicator_name]['min'], value)
                        value_ranges[indicator_name]['max'] = max(value_ranges[indicator_name]['max'], value)

            for name, range_data in value_ranges.items():
                print(f"  {name}: Min={range_data['min']:.4f}, Max={range_data['max']:.4f}")

        if history:
            print("\nLatest 3 ticks in history:")
            for tick in history[-3:]:
                if hasattr(tick, 'close'):
                    print(
                        f"  {getattr(tick, 'symbol', 'Unknown')} @ {getattr(tick, 'timestamp', 'Unknown')}: "
                        f"OHLC({getattr(tick, 'open', 0):.2f},{getattr(tick, 'high', 0):.2f},"
                        f"{getattr(tick, 'low', 0):.2f},{getattr(tick, 'close', 0):.2f})"
                    )

        print("=" * 60)


def main():
    print("==== INDICATOR PROCESSOR DEBUG TEST ====")
    print("Testing DataStreamer with initialize and run...")

    print("Creating and authenticating SchwabDataLink...")
    data_link = SchwabDataLink()

    if not data_link.authenticate():
        print("Authentication failed, exiting")
        return

    # Load historical data
    print("Connecting to streaming API...")
    if not data_link.connect_stream():
        print("Failed to connect to streaming API")
        return

    model_config = {
        "feature_vector": [
            {"name": "open"},
            {"name": "high"},
            {"name": "low"},
            {"name": "close"},
        ],
        "normalization": None
    }

    indicator_config = MonitorConfiguration(
        name="Test Monitor",
        indicators=[
            {
                "name": "SMA Crossover",
                "type": INDICATOR_TYPE,
                "function": "sma_crossover",
                "parameters": {
                    "period": 10,
                    "crossover_value": 0.0002,
                    "trend": "bullish",
                    "lookback": 10
                }
            },
            {
                "name": "MACD Histogram",
                "type": INDICATOR_TYPE,
                "function": "macd_histogram_crossover",
                "parameters": {
                    "fast": 12,
                    "slow": 26,
                    "signal": 9,
                    "histogram_threshold": 0.05,
                    "lookback": 10,
                    "trend": "bullish"
                }
            }
        ]
    )

    print("Creating DataStreamer...")
    data_streamer = DataStreamer(
        data_link=data_link,  # Pass data_link directly
        model_configuration=model_config,
        indicator_configuration=indicator_config
    )

    data_streamer.data_link = data_link

    monitor = DebugMonitorTool()
    data_streamer.connect_tool(monitor)

    symbols = ["NVDA"]
    interval = "1m"

    print(f"Initializing DataStreamer with historical data for {symbols}...")
    data_streamer.initialize(symbols, interval)

    data_link.subscribe_charts(symbols, interval)

    print("\nStarting DataStreamer run...")

    try:
        run_duration = 120  # seconds
        print(f"Will run for {run_duration} seconds to collect real-time data...")

        data_streamer.run()


        time.sleep(run_duration)

        print("\nFinal state after running:")
        monitor.print_summary(data_streamer)

    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        print(f"\nError during run: {e}")
        import traceback
        traceback.print_exc()

    print("\nTest completed!")


if __name__ == "__main__":
    main()
