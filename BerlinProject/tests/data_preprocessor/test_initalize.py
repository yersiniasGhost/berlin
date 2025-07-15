# test_initialize.py
from datetime import datetime

from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.data_preprocessor import DataPreprocessor


def main():
    print("Starting initialization test...")

    # Create model configuration (simple, without normalization)
    model_config = {
        "feature_vector": [
            {"name": "open"},
            {"name": "high"},
            {"name": "low"},
            {"name": "close"},
        ],
        "normalization": None
    }

    # Create DataPreprocessor
    preprocessor = DataPreprocessor(model_config)

    # Create and authenticate SchwabDataLink
    print("Creating and authenticating SchwabDataLink...")
    data_link = SchwabDataLink()

    if not data_link.authenticate():
        print("Authentication failed, exiting")
        return

    # Define symbols to track
    symbols = ["NVDA"]
    timeframe = "1m"

    # Initialize DataPreprocessor with historical data
    print(f"Initializing DataPreprocessor with historical data for {symbols}...")
    success = preprocessor.initialize(data_link, symbols, timeframe)

    # Print result
    if success:
        print("Initialization successful!")
    else:
        print("Initialization failed!")

    # Print history information
    print(f"\nHistory size: {len(preprocessor.history)} ticks")

    if preprocessor.history:
        # Print first 3 ticks
        print("\nFirst 3 ticks:")
        for i, tick in enumerate(preprocessor.history[:3]):
            print(f"Tick {i + 1}:")
            print(f"  Symbol: {tick.symbol}")
            print(f"  Timestamp: {tick.timestamp}")
            print(f"  OHLC: O:{tick.open:.2f} H:{tick.high:.2f} L:{tick.low:.2f} C:{tick.close:.2f}")
            print(f"  Volume: {tick.volume}")

        # Print last 3 ticks
        print("\nLast 3 ticks:")
        for i, tick in enumerate(preprocessor.history[-3:]):
            print(f"Tick {len(preprocessor.history) - 2 + i}:")
            print(f"  Symbol: {tick.symbol}")
            print(f"  Timestamp: {tick.timestamp}")
            print(f"  OHLC: O:{tick.open:.2f} H:{tick.high:.2f} L:{tick.low:.2f} C:{tick.close:.2f}")
            print(f"  Volume: {tick.volume}")

    # Get current time
    current_time = datetime.now()
    print(f"\nCurrent time: {current_time}")

    # Calculate time range of historical data
    if preprocessor.history:
        earliest_time = preprocessor.history[0].timestamp
        latest_time = preprocessor.history[-1].timestamp
        print(f"Historical data range: {earliest_time} to {latest_time}")
        print(f"Total time span: {latest_time - earliest_time}")

    print("\nTest completed!")


if __name__ == "__main__":
    main()