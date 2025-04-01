import json
from typing import Dict, List, Optional, Tuple, Iterator, Any, Callable
from datetime import datetime, timedelta
import time
import logging
import requests
from environments.tick_data import TickData
from data_streamer.data_link import DataLink

logger = logging.getLogger('SchwabDataLink')


class CandleAggregator:
    """
    Aggregates tick data into candles of specified timeframe.
    Provides real-time updating candles as ticks come in.
    """

    def __init__(self, user_prefs: dict, access_token: str, symbols: list,
                 timeframe: str = "1m", days_history: int = 5):
        # Existing code...

        # Initialize data structures
        for symbol in symbols:
            self.candle_data[symbol] = []
            self.latest_ticks[symbol] = None

        # Setup logging
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

        # Load historical data eagerly at initialization
        logger.info("Attempting to load historical data at initialization")
        self.load_historical_data()

    def _parse_timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes"""
        if timeframe.endswith('m'):
            return int(timeframe[:-1])
        elif timeframe.endswith('h'):
            return int(timeframe[:-1]) * 60
        elif timeframe.endswith('d'):
            return int(timeframe[:-1]) * 60 * 24
        else:
            logger.warning(f"Unknown timeframe format: {timeframe}, defaulting to 1 minute")
            return 1

    def _get_candle_start_time(self, timestamp: datetime) -> datetime:
        """
        Calculate the start time of the candle that should contain this timestamp
        """
        if self.timeframe == "1m":
            # For 1-minute candles, round down to the nearest minute
            return timestamp.replace(second=0, microsecond=0)
        elif self.timeframe == "5m":
            # For 5-minute candles, round down to the nearest 5 minutes
            minute = (timestamp.minute // 5) * 5
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif self.timeframe == "15m":
            # For 15-minute candles, round down to the nearest 15 minutes
            minute = (timestamp.minute // 15) * 15
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif self.timeframe == "30m":
            # For 30-minute candles, round down to the nearest 30 minutes
            minute = (timestamp.minute // 30) * 30
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif self.timeframe == "1h":
            # For 1-hour candles, round down to the nearest hour
            return timestamp.replace(minute=0, second=0, microsecond=0)
        elif self.timeframe == "1d":
            # For 1-day candles, round down to the beginning of the day
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # Default to 1-minute candles
            return timestamp.replace(second=0, microsecond=0)

    def _should_close_candle(self, candle: TickData, tick: TickData) -> bool:
        """
        Determine if the current candle should be closed and a new one started
        based on the timestamp of the new tick
        """
        candle_start = self._get_candle_start_time(candle.timestamp)
        tick_start = self._get_candle_start_time(tick.timestamp)

        # If the tick belongs to a different candle period, close the current candle
        return tick_start > candle_start

    def process_tick(self, tick: TickData) -> Tuple[TickData, Optional[TickData]]:
        """
        Process a new tick, updating or creating candles as needed

        Args:
            tick: The new tick data

        Returns:
            Tuple of (current_candle, completed_candle)
            completed_candle is None if no candle was completed
        """
        symbol = tick.symbol
        completed_candle = None

        # Initialize candle lists if this is the first tick for this symbol
        if symbol not in self.completed_candles:
            self.completed_candles[symbol] = []

        # If we don't have a current candle for this symbol, create one
        if symbol not in self.current_candles:
            # Create a new candle using this tick
            self.current_candles[symbol] = TickData(
                symbol=symbol,
                open=tick.close,
                high=tick.close,
                low=tick.close,
                close=tick.close,
                volume=tick.volume or 0,
                timestamp=self._get_candle_start_time(tick.timestamp)
            )
            logger.debug(f"Created new candle for {symbol} starting at {self.current_candles[symbol].timestamp}")
        else:
            # Check if we need to close the current candle
            current_candle = self.current_candles[symbol]

            if self._should_close_candle(current_candle, tick):
                # Close the current candle and store it
                completed_candle = current_candle
                self.completed_candles[symbol].append(completed_candle)
                logger.debug(f"Completed candle for {symbol} at {completed_candle.timestamp}")

                # Create a new candle
                self.current_candles[symbol] = TickData(
                    symbol=symbol,
                    open=tick.close,
                    high=tick.close,
                    low=tick.close,
                    close=tick.close,
                    volume=tick.volume or 0,
                    timestamp=self._get_candle_start_time(tick.timestamp)
                )
                logger.debug(f"Created new candle for {symbol} starting at {self.current_candles[symbol].timestamp}")
            else:
                # Update the current candle with this tick
                current_candle.high = max(current_candle.high, tick.close)
                current_candle.low = min(current_candle.low, tick.close)
                current_candle.close = tick.close
                current_candle.volume = (current_candle.volume or 0) + (tick.volume or 0)
                logger.debug(
                    f"Updated candle for {symbol}: close={tick.close}, high={current_candle.high}, low={current_candle.low}")

        return self.current_candles[symbol], completed_candle

    def get_candle_history(self, symbol: str) -> List[TickData]:
        """
        Get all completed candles for a symbol

        Args:
            symbol: The symbol to get candles for

        Returns:
            List of completed candles
        """
        return self.completed_candles.get(symbol, [])

    def get_all_candles(self, symbol: str) -> List[TickData]:
        """
        Get all candles (completed + current) for a symbol

        Args:
            symbol: The symbol to get candles for

        Returns:
            List of all candles including the current one
        """
        candles = self.get_candle_history(symbol).copy()
        if symbol in self.current_candles:
            candles.append(self.current_candles[symbol])
        return candles


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
            timeframe: Candle timeframe (1m, 5m, 15m, 30m, 1h, 1d)
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
        self.latest_ticks = {}  # Latest tick data by symbol
        self.candle_aggregator = CandleAggregator(timeframe)
        self.delay = 0  # Configurable delay for live data
        self.live_mode = False  # Whether we're in live streaming mode

        # Mapping of timeframe strings to API parameters for historical data
        self.timeframe_mapping = {
            "1m": {"periodType": "day", "period": 1, "frequencyType": "minute", "frequency": 1},
            "5m": {"periodType": "day", "period": 1, "frequencyType": "minute", "frequency": 5},
            "15m": {"periodType": "day", "period": 1, "frequencyType": "minute", "frequency": 15},
            "30m": {"periodType": "day", "period": 1, "frequencyType": "minute", "frequency": 30},
            "1h": {"periodType": "day", "period": 1, "frequencyType": "hour", "frequency": 1},
            "1d": {"periodType": "month", "period": 1, "frequencyType": "daily", "frequency": 1}
        }

        # Initialize data structures
        for symbol in symbols:
            self.candle_data[symbol] = []
            self.latest_ticks[symbol] = None

        # Setup logging
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    def connect(self) -> bool:
        """Connect to Schwab streaming API"""
        logger.info("Connecting to Schwab streaming API")

        try:
            # Import the streamer client
            from schwab_api.streamer_client import SchwabStreamerClient

            # Create and check if the streaming client is available
            logger.info("Creating streaming client")
            self.streaming_client = SchwabStreamerClient(
                user_prefs=self.user_prefs,
                access_token=self.access_token
            )

            # Print the user_prefs for debugging
            logger.info(f"User prefs for streaming: {self.user_prefs}")

            # Connect to the streaming API
            logger.info("Connecting to streaming API...")
            success = self.streaming_client.connect()

            if not success:
                logger.error("Failed to connect to streaming API")
                return False

            logger.info("Successfully connected to streaming API")

            # Subscribe to quotes
            logger.info(f"Subscribing to quotes for symbols: {self.symbols}")
            self.streaming_client.subscribe_quotes(self.symbols, self._handle_quote_data)

            logger.info("Successfully subscribed to quotes")
            return True

        except ImportError:
            logger.error("Could not import SchwabStreamerClient. Check your imports.", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Error connecting to Schwab API: {str(e)}", exc_info=True)
            return False

    def load_historical_data(self) -> bool:
        """
        Load historical data for all symbols using Schwab API
        """
        logger.info(f"Loading historical data for {self.symbols} with timeframe {self.timeframe}")

        # Get timeframe parameters
        tf_params = self.timeframe_mapping.get(self.timeframe,
                                               {"periodType": "day", "period": 1,
                                                "frequencyType": "minute", "frequency": 1})

        logger.info(f"Using API parameters: {tf_params}")

        # Try to load from API
        success = False

        for symbol in self.symbols:
            try:
                url = "https://api.schwabapi.com/marketdata/v1/pricehistory"

                params = {
                    'symbol': symbol,
                    'periodType': tf_params["periodType"],
                    'period': tf_params["period"],
                    'frequencyType': tf_params["frequencyType"],
                    'frequency': tf_params["frequency"],
                    'needExtendedHoursData': True
                }

                headers = {
                    'Authorization': f'Bearer {self.access_token}'
                }

                logger.info(f"Requesting historical data for {symbol} from {url}")
                logger.info(f"Request params: {params}")
                logger.info(f"Auth token: {self.access_token[:10]}... (truncated)")

                response = requests.get(url, headers=headers, params=params)

                logger.info(f"Response status code: {response.status_code}")

                # Check response headers
                logger.info(f"Response headers: {dict(response.headers)}")

                # Print a sample of the response content for debugging
                if response.text:
                    logger.info(f"Response content preview: {response.text[:200]}...")

                # Process the response
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logger.info(f"Successfully parsed JSON response")

                        if 'candles' in data:
                            candle_count = len(data['candles'])
                            logger.info(f"Found {candle_count} candles in response")

                            self.candle_data[symbol] = []

                            for candle in data['candles']:
                                timestamp = datetime.fromtimestamp(candle['datetime'] / 1000)

                                tick = TickData(
                                    symbol=symbol,
                                    open=candle['open'],
                                    high=candle['high'],
                                    low=candle['low'],
                                    close=candle['close'],
                                    volume=candle.get('volume', 0),
                                    timestamp=timestamp
                                )

                                self.candle_data[symbol].append(tick)

                            logger.info(f"Loaded {len(self.candle_data[symbol])} historical candles for {symbol}")

                            # Pre-load the candle aggregator with historical data
                            self.candle_aggregator.completed_candles[symbol] = self.candle_data[symbol].copy()

                            success = True
                        else:
                            logger.warning(f"No 'candles' key in API response")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse API response as JSON: {response.text[:100]}...")
                else:
                    logger.error(f"API returned error: {response.status_code} - {response.reason}")
                    logger.error(f"Error details: {response.text[:200]}...")
            except Exception as e:
                logger.error(f"Exception during historical data loading: {str(e)}", exc_info=True)

        # If no historical data loaded, create initial candles
        if not success:
            logger.warning("Failed to load historical data from Schwab API")

        return success

    def _handle_quote_data(self, data: List[Dict[str, Any]]) -> None:
        """
        Handle incoming quote data from Schwab API
        """
        logger.info(f"Received quote data: {len(data)} ticks")

        if not data:
            logger.debug("Empty quote data received")
            return

        for quote in data:
            try:
                # Extract the symbol from the 'key' field
                symbol = quote.get('key', '')

                if not symbol:
                    logger.warning(f"Quote missing symbol/key: {quote}")
                    continue

                if symbol not in self.symbols:
                    logger.debug(f"Ignoring quote for non-tracked symbol: {symbol}")
                    continue

                # Log the raw quote for debugging
                logger.info(f"Processing quote for {symbol}: {quote}")

                # Extract timestamp
                timestamp = datetime.now()
                if '35' in quote:  # Trade time field
                    trade_time = int(quote.get('35', 0))
                    if trade_time > 0:
                        timestamp = datetime.fromtimestamp(trade_time / 1000)

                # Extract price
                last_price = None
                if '3' in quote:  # Last price field
                    try:
                        last_price = float(quote.get('3', 0.0))
                    except ValueError:
                        logger.warning(f"Invalid price format: {quote.get('3')}")

                if last_price is None or last_price <= 0:
                    logger.warning(f"Invalid price in quote: {last_price}")
                    continue

                # Extract volume
                volume = 0
                if '8' in quote:  # Volume field
                    try:
                        volume = int(quote.get('8', 0))
                    except ValueError:
                        logger.warning(f"Invalid volume format: {quote.get('8')}")

                # Create tick
                tick = TickData(
                    symbol=symbol,
                    open=last_price,
                    high=last_price,
                    low=last_price,
                    close=last_price,
                    volume=volume,
                    timestamp=timestamp
                )

                logger.info(f"Created tick: {symbol} @ {last_price} [{timestamp}]")

                # Update latest tick
                self.latest_ticks[symbol] = tick

                # Process through candle aggregator if we're in live mode
                if self.live_mode:
                    logger.info(f"Processing tick through candle aggregator")
                    current_candle, completed_candle = self.candle_aggregator.process_tick(tick)

                    if current_candle:
                        logger.info(f"Updated current candle: O:{current_candle.open} H:{current_candle.high} "
                                    f"L:{current_candle.low} C:{current_candle.close}")

                    # If a candle was completed, notify the handlers
                    if completed_candle:
                        logger.info(f"Completed candle: {completed_candle.timestamp}")
                        self.notify_handlers(completed_candle, self.tick_index, self.symbols.index(symbol))
                        self.tick_index += 1

            except Exception as e:
                logger.error(f"Error processing quote: {str(e)}", exc_info=True)

    def serve_next_tick(self) -> Iterator[Tuple[TickData, int, int]]:
        """
        Serve next tick from either historical or live data.
        In both cases, we're returning complete candles.

        Yields:
            Tuple of (tick_data, tick_index, day_index)
        """
        logger.info(f"Starting serve_next_tick with {len(self.symbols)} symbols")

        # First serve historical data
        ticker_idx = 0
        for symbol in self.symbols:
            historical_candles = self.candle_data[symbol]
            logger.info(f"Serving {len(historical_candles)} historical candles for {symbol}")

            self.day_index = ticker_idx
            for idx, candle in enumerate(historical_candles):
                self.tick_index = idx
                # Notify handlers before yielding
                self.notify_handlers(candle, idx, ticker_idx)
                yield candle, idx, ticker_idx

                # Add configurable delay for historical data simulation
                if self.delay > 0:
                    time.sleep(self.delay)

            # End of symbol data
            logger.info(f"Finished serving historical data for {symbol}")
            yield None, -1, ticker_idx
            ticker_idx += 1

        # Switch to live mode
        logger.info("Switching to live data streaming mode")
        self.live_mode = True
        self.tick_index = 0

        # In live mode, we'll use the CandleAggregator to deliver candles
        # The _handle_quote_data method will process ticks through the aggregator
        # and notify handlers when candles are completed

        # We still need to yield from here to keep the iterator going
        try:
            while self.live_mode:
                # Check each symbol for a current candle to yield
                for idx, symbol in enumerate(self.symbols):
                    # Get the current in-progress candle
                    if symbol in self.candle_aggregator.current_candles:
                        current_candle = self.candle_aggregator.current_candles[symbol]
                        # Yield the current in-progress candle
                        yield current_candle, self.tick_index, idx
                        self.tick_index += 1

                # Sleep to avoid tight loops
                time.sleep(0.5)
        except GeneratorExit:
            logger.info("Generator exited, stopping live mode")
            self.live_mode = False
        except Exception as e:
            logger.error(f"Error in live streaming: {e}")
            self.live_mode = False
            raise

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
        # First check if we're in live mode
        if self.live_mode:
            # In live mode, return the current candle from the aggregator
            for symbol in self.symbols:
                if symbol in self.candle_aggregator.current_candles:
                    return self.candle_aggregator.current_candles[symbol]
            return None

        # If not in live mode, return the next historical candle
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

    def disconnect(self) -> None:
        """Disconnect from Schwab streaming API"""
        self.live_mode = False
        if self.streaming_client:
            if hasattr(self.streaming_client, 'disconnect'):
                self.streaming_client.disconnect()