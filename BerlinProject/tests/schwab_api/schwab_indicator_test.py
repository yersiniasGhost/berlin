import logging
import time
from datetime import datetime
from typing import Dict, Optional
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SchwabTool')


class SchwabIndicatorAnalyzer:
    def __init__(self):
        from src.schwab_api.authentication import SchwabClient
        from src.data_streamer.external_tool import ExternalTool
        from src.environments.tick_data import TickData
        from src.models.monitor_configuration import MonitorConfiguration
        from src.config.types import INDICATOR_TYPE

        # Create UI Tool for displaying indicator signals
        class IndicatorMonitor(ExternalTool):
            def __init__(self):
                self.indicator_history = {}
                self.price_history = []
                self.timestamps = []
                self.raw_values = {}

            def indicator_vector(self, indicators: Dict[str, float], tick: TickData,
                                 index: int, raw_indicators: Optional[Dict[str, float]] = None):
                # Store price and timestamp
                self.price_history.append(tick.close)
                timestamp = tick.timestamp or datetime.now()
                self.timestamps.append(timestamp)

                # Format timestamp for display
                time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if isinstance(timestamp, datetime) else timestamp

                # Store indicator values
                for name, value in indicators.items():
                    if name not in self.indicator_history:
                        self.indicator_history[name] = []
                    self.indicator_history[name].append(value)

                    # Store raw values if available
                    if raw_indicators and name in raw_indicators:
                        if name not in self.raw_values:
                            self.raw_values[name] = []
                        self.raw_values[name].append(raw_indicators[name])

                # Print current values
                print(f"\nTick {index}: {time_str} | Price: ${tick.close:.2f}")

                for name, value in indicators.items():
                    trigger_status = "🔴 TRIGGERED" if value > 0 else "⚪ inactive"
                    raw_value = raw_indicators.get(name, None) if raw_indicators else None
                    raw_info = f" (Raw: {raw_value})" if raw_value is not None else ""
                    print(f"  {name}: {value:.4f} {trigger_status}{raw_info}")

                print("-" * 50)

            def feature_vector(self, fv: np.array, tick: TickData):
                # Process feature vector data (SMA, MACD calculations)
                if fv is not None and len(fv) > 0 and tick is not None:
                    pass

        # Authentication setup
        logger.info("Setting up authentication...")
        self.client = SchwabClient(
            app_key="QtfsQiLHpno726ZFgRDtvHA3ZItCAkcQ",
            app_secret="RmwUJyBGGgW2r2C7",
            redirect_uri="https://127.0.0.1",
            token_path="schwab_tokens.json"
        )

        # Try to use existing tokens first, refresh if needed
        if not self.client.access_token:
            logger.info("No token found, authenticating...")
            self.client.authenticate(use_local_server=False)
        else:
            logger.info("Found existing token, checking validity...")
            # First try to refresh the token
            if hasattr(self.client, 'refresh_token') and self.client.refresh_token:
                logger.info("Attempting to refresh token...")
                refresh_success = self.client.refresh_auth_token()
                if refresh_success:
                    logger.info("Token refreshed successfully")
                else:
                    logger.info("Token refresh failed, re-authenticating...")
                    self.client.authenticate(use_local_server=False)
            else:
                # If no refresh token, just re-authenticate
                logger.info("No refresh token available, re-authenticating...")
                self.client.authenticate(use_local_server=False)

        # Create indicator definitions
        self.indicator_config = MonitorConfiguration(
            name="trading_signals",
            indicators=[
                {
                    "name": "sma_crossover",
                    "type": INDICATOR_TYPE,
                    "function": "sma_crossover",
                    "parameters": {
                        "period": 20,
                        "crossover_value": 0.002,
                        "trend": "bullish",
                        "lookback": 10
                    }
                },
                {
                    "name": "macd_signal",
                    "type": INDICATOR_TYPE,
                    "function": "macd_histogram_crossover",
                    "parameters": {
                        "fast": 12,
                        "slow": 26,
                        "signal": 9,
                        "histogram_threshold": 0.1,
                        "trend": "bullish",
                        "lookback": 15
                    }
                }
            ]
        )

        # Create UI tool
        self.ui_tool = IndicatorMonitor()

    def process_data_directly(self):
        """Process historical data directly using SchwabDataLink and indicators"""
        from src.data_streamer.schwab_data_link import SchwabDataLink
        from src.data_streamer.indicator_processor import IndicatorProcessor
        from src.data_streamer.data_preprocessor import DataPreprocessor

        # Create model configuration
        model_config = {
            "feature_vector": [
                {"name": "close"},
                {"name": "SMA", "parameters": {"sma": 20}},
                {"name": "MACD", "parameters": {
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9
                }}
            ]
        }

        # Initialize data processors
        preprocessor = DataPreprocessor(model_config)
        indicator_processor = IndicatorProcessor(self.indicator_config)

        # Initialize SchwabDataLink
        logger.info("Creating SchwabDataLink...")
        data_link = SchwabDataLink(
            user_prefs=self.client.user_prefs,
            access_token=self.client.access_token,
            symbols=["NVDA"],
            timeframe="5m",
            days_history=3
        )

        # Load historical data
        logger.info("Loading historical data...")
        success = data_link.load_historical_data()

        # Handle potential 401 error by re-authenticating and trying again
        if not success:
            logger.warning("Failed to load historical data, attempting re-authentication...")
            self.client.authenticate(use_local_server=False)

            # Re-create data link with new token
            data_link = SchwabDataLink(
                user_prefs=self.client.user_prefs,
                access_token=self.client.access_token,
                symbols=["NVDA"],
                timeframe="5m",
                days_history=3
            )

            # Try again
            logger.info("Retrying loading historical data...")
            success = data_link.load_historical_data()

            if not success:
                logger.error("Failed to load historical data after re-authentication")
                return

        # Print data summary
        for symbol in data_link.symbols:
            count = len(data_link.candle_data.get(symbol, []))
            logger.info(f"Loaded {count} historical candles for {symbol}")

        # Process historical data
        logger.info("Processing historical data with indicators...")
        index = 0

        # Get stats for normalization
        stats = data_link.get_stats()
        preprocessor.reset_state(stats)

        # Process each tick
        for symbol in data_link.symbols:
            for tick in data_link.candle_data[symbol]:
                # Process through preprocessor
                preprocessor.next_tick(tick)

                # Calculate indicators
                indicator_results = indicator_processor.next_tick(preprocessor)

                # Send to UI tool
                self.ui_tool.indicator_vector(indicator_results, tick, index, None)

                index += 1

        # Display summary
        logger.info(f"Processed {index} ticks from historical data")
        print("\n===== INDICATOR ANALYSIS SUMMARY =====")

        # Calculate trigger counts
        for name, values in self.ui_tool.indicator_history.items():
            trigger_count = sum(1 for v in values if v > 0)
            if trigger_count > 0:
                trigger_pct = (trigger_count / len(values)) * 100
                print(f"{name}: {trigger_count} triggers ({trigger_pct:.1f}% of candles)")
            else:
                print(f"{name}: No triggers detected")

        print("======================================")


if __name__ == "__main__":
    analyzer = SchwabIndicatorAnalyzer()
    analyzer.process_data_directly()