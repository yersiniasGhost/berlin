from typing import Iterator, Tuple, Optional, Dict, List, Any
from datetime import datetime, timedelta
import time
import logging
from src.environments.tick_data import TickData
from data_streamer.data_link import DataLink

logger = logging.getLogger('SchwabDataLink')


class SchwabDataLink(DataLink):
    """
    Data link for Schwab API that provides both historical and live data.
    Inherits from DataLink base class to integrate with the overall data flow.
    """

    def __init__(self, user_prefs: dict, access_token: str, symbols: list,
                 timeframe: str = "1m", days_history: int = 5):
        """
        Initialize the Schwab data link

        Args:
            user_prefs: User preferences from Schwab API
            access_token: OAuth access token
            symbols: List of stock symbols to track
            timeframe: Candle timeframe (1m, 5m, 15m, etc.)
            days_history: Number of days of historical data to load
        """
        super().__init__()
        self.user_prefs = user_prefs
        self.access_token = access_token
        self.symbols = symbols
        self.timeframe = timeframe
        self.days_history = days_history
        self.streaming_client = None
        self.tick_index = 0
        self.day_index = 0
        self.candle_data = {}  # Historical data by symbol
        self.latest_data = {}  # Latest live data by symbol
        self.delay = 0  # Configurable delay for live data
        self.live_mode = False  # Whether we're in live streaming mode

        # Mapping of timeframe strings to API parameters
        self.timeframe_mapping = {
            "1m": {"frequencyType": "minute", "frequency": 1},
            "5m": {"frequencyType": "minute", "frequency": 5},
            "15m": {"frequencyType": "minute", "frequency": 15},
            "30m": {"frequencyType": "minute", "frequency": 30},
            "1h": {"frequencyType": "hour", "frequency": 1},
            "1d": {"frequencyType": "daily", "frequency": 1}
        }

        # Initialize data structures
        for symbol in symbols:
            self.candle_data[symbol] = []
            self.latest_data[symbol] = None

        # Setup logging
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    def connect(self) -> bool:
        """
        Connect to Schwab streaming API with improved error handling

        Returns:
            bool: True if connection and login are successful, False otherwise
        """
        if not self.load_historical_data():
            logger.error("Failed to load historical data")
            return False

        try:
            from src.schwab_api.streamer_client import SchwabStreamerClient

            # Create streaming client
            self.streaming_client = SchwabStreamerClient(
                user_prefs=self.user_prefs,
                access_token=self.access_token
            )

            # Connect and login
            if not self.streaming_client.connect():
                logger.error("Failed to connect to streaming API")
                return False

            # Subscribe to quotes and charts
            self.streaming_client.subscribe_quotes(
                self.symbols,
                self._handle_quote_data
            )
            self.streaming_client.subscribe_charts(
                self.symbols,
                self._handle_chart_data
            )

            return True

        except Exception as e:
            logger.error(f"Error connecting to Schwab API: {e}")
            return False

    def load_historical_data(self) -> bool:
        """
        Load historical data for all symbols using Schwab API

        Returns:
            True if data was loaded successfully, False otherwise
        """
        import requests

        # Get timeframe parameters
        tf_params = self.timeframe_mapping.get(self.timeframe,
                                               {"frequencyType": "minute", "frequency": 1})

        success = True

        for symbol in self.symbols:
            try:
                url = "https://api.schwabapi.com/marketdata/v1/pricehistory"

                params = {
                    'symbol': symbol,
                    'periodType': "day",
                    'period': self.days_history,
                    'frequencyType': tf_params["frequencyType"],
                    'frequency': tf_params["frequency"],
                    'needExtendedHoursData': True
                }

                headers = {
                    'Authorization': f'Bearer {self.access_token}'
                }

                response = requests.get(url, headers=headers, params=params)

                if response.status_code == 200:
                    data = response.json()

                    # Process candles from response
                    if 'candles' in data:
                        self.candle_data[symbol] = []

                        for candle in data['candles']:
                            timestamp = datetime.fromtimestamp(candle['datetime'] / 1000)

                            tick = TickData(
                                close=candle['close'],
                                open=candle['open'],
                                high=candle['high'],
                                low=candle['low'],
                                volume=candle.get('volume', 0),
                                timestamp=timestamp
                            )

                            self.candle_data[symbol].append(tick)

                        logger.info(f"Loaded {len(self.candle_data[symbol])} historical candles for {symbol}")
                    else:
                        logger.warning(f"No candles data found for {symbol}")
                        success = False
                else:
                    logger.error(
                        f"Error loading historical data for {symbol}: {response.status_code} - {response.text}")
                    success = False

            except Exception as e:
                logger.error(f"Exception loading historical data for {symbol}: {e}")
                success = False

        return success

    def _handle_quote_data(self, data: List[Dict[str, Any]]) -> None:
        """
        Handle incoming quote data from Schwab API

        Args:
            data: List of quote data dictionaries
        """
        for quote in data:
            symbol = quote.get('key', '')

            if symbol in self.symbols:
                try:
                    # Extract relevant fields
                    last_price = float(quote.get('3', 0.0))  # Last price
                    bid = float(quote.get('1', 0.0))  # Bid price
                    ask = float(quote.get('2', 0.0))  # Ask price
                    volume = int(quote.get('8', 0))  # Volume

                    # Use the current price as all OHLC values for quotes
                    # (These will be properly updated by chart data)
                    tick_data = TickData(
                        open=last_price,
                        high=last_price,
                        low=last_price,
                        close=last_price,
                        volume=volume,
                        timestamp=datetime.now()
                    )

                    # Update latest data
                    self.latest_data[symbol] = tick_data

                except Exception as e:
                    logger.error(f"Error processing quote for {symbol}: {e}")

    def _handle_chart_data(self, data: List[Dict[str, Any]]) -> None:
        """
        Handle incoming chart data from Schwab API

        Args:
            data: List of chart data dictionaries
        """
        for chart_entry in data:
            symbol = chart_entry.get('key', '')

            if symbol in self.symbols:
                try:
                    # Extract timestamp
                    timestamp_ms = int(chart_entry.get('7', 0))
                    timestamp = datetime.fromtimestamp(timestamp_ms / 1000)

                    # Extract OHLCV data
                    open_price = float(chart_entry.get('2', 0.0))
                    high_price = float(chart_entry.get('3', 0.0))
                    low_price = float(chart_entry.get('4', 0.0))
                    close_price = float(chart_entry.get('5', 0.0))
                    volume = int(chart_entry.get('6', 0))

                    # Create TickData object
                    tick_data = TickData(
                        open=open_price,
                        high=high_price,
                        low=low_price,
                        close=close_price,
                        volume=volume,
                        timestamp=timestamp
                    )

                    # Update latest data
                    self.latest_data[symbol] = tick_data

                    # If we're in live mode, add to historical data as well
                    if self.live_mode:
                        self.candle_data[symbol].append(tick_data)

                    # Notify any registered handlers
                    self.notify_handlers(tick_data, self.tick_index, self.day_index)
                    self.tick_index += 1

                except Exception as e:
                    logger.error(f"Error processing chart data for {symbol}: {e}")

    def get_stats(self) -> dict:
        """
        Get statistics for all historical data (for normalization)

        Returns:
            Dictionary of statistics
        """
        # Calculate stats from historical data
        all_ticks = []
        for symbol in self.symbols:
            all_ticks.extend(self.candle_data[symbol])

        if not all_ticks:
            # Return default stats if no data available
            return {
                'open': {'min': 90.0, 'max': 110.0, 'sd': 5.0},
                'high': {'min': 90.0, 'max': 110.0, 'sd': 5.0},
                'low': {'min': 90.0, 'max': 110.0, 'sd': 5.0},
                'close': {'min': 90.0, 'max': 110.0, 'sd': 5.0}
            }

        # Calculate actual stats
        opens = [tick.open for tick in all_ticks]
        highs = [tick.high for tick in all_ticks]
        lows = [tick.low for tick in all_ticks]
        closes = [tick.close for tick in all_ticks]

        # Calculate statistics
        stats = {
            'open': {
                'min': min(opens),
                'max': max(opens),
                'sd': self._std_dev(opens)
            },
            'high': {
                'min': min(highs),
                'max': max(highs),
                'sd': self._std_dev(highs)
            },
            'low': {
                'min': min(lows),
                'max': max(lows),
                'sd': self._std_dev(lows)
            },
            'close': {
                'min': min(closes),
                'max': max(closes),
                'sd': self._std_dev(closes)
            }
        }

        return stats

    def _std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        import numpy as np
        return float(np.std(values)) if values else 1.0

    def serve_next_tick(self) -> Iterator[Tuple[TickData, int, int]]:
        """
        Serve next tick from either historical or live data
        Implements the DataLink method

        Yields:
            Tuple of (tick_data, tick_index, day_index)
        """
        # First serve historical data
        ticker_idx = 0
        for symbol in self.symbols:
            self.day_index = ticker_idx
            for idx, tick in enumerate(self.candle_data[symbol]):
                self.tick_index = idx
                # Notify handlers before yielding
                self.notify_handlers(tick, idx, ticker_idx)
                yield tick, idx, ticker_idx

                # Add configurable delay for historical data simulation
                if self.delay > 0:
                    time.sleep(self.delay)

            # End of symbol data
            yield None, -1, ticker_idx
            ticker_idx += 1

        # Switch to live mode
        self.live_mode = True
        self.tick_index = 0

        # Then stream live data
        while self.live_mode:
            # Process each symbol
            for idx, symbol in enumerate(self.symbols):
                if symbol in self.latest_data and self.latest_data[symbol]:
                    tick = self.latest_data[symbol]
                    # Don't yield the same tick twice
                    self.latest_data[symbol] = None

                    # Notify handlers and yield
                    self.notify_handlers(tick, self.tick_index, idx)
                    yield tick, self.tick_index, idx
                    self.tick_index += 1

            # Add delay between live checks
            if self.delay > 0:
                time.sleep(self.delay)
            else:
                # Default delay to avoid tight loops
                time.sleep(0.1)

    def get_history(self) -> Dict[int, List[TickData]]:
        """
        Get historical data in a format compatible with IndicatorProcessorHistorical

        Returns:
            Dictionary of day index to list of ticks
        """
        history = {}
        for idx, symbol in enumerate(self.symbols):
            history[idx] = self.candle_data[symbol]
        return history

    def reset_index(self) -> None:
        """Reset tick index and day index"""
        self.tick_index = 0
        self.day_index = 0

    def get_next2(self) -> Optional[TickData]:
        """
        Get the next tick without using the iterator pattern
        For compatibility with DataLink interface

        Returns:
            Next TickData or None if no more data
        """
        # Determine which symbol and which tick to return
        if self.day_index >= len(self.symbols):
            return None

        symbol = self.symbols[self.day_index]

        if self.tick_index >= len(self.candle_data[symbol]):
            self.day_index += 1
            self.tick_index = 0
            return self.get_next2()

        tick = self.candle_data[symbol][self.tick_index]
        self.tick_index += 1
        return tick

    def set_timeframe(self, timeframe: str) -> None:
        """
        Set the timeframe and reload historical data

        Args:
            timeframe: Timeframe string (1m, 5m, 15m, etc.)
        """
        if timeframe != self.timeframe and timeframe in self.timeframe_mapping:
            self.timeframe = timeframe
            self.load_historical_data()

    def disconnect(self) -> None:
        """Disconnect from Schwab streaming API"""
        self.live_mode = False
        if self.streaming_client:
            # Call disconnect method if available
            if hasattr(self.streaming_client, 'disconnect'):
                self.streaming_client.disconnect()