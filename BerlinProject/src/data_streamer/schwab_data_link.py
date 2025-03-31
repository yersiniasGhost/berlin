# /home/warnd/devel/berlin/BerlinProject/src/data_streamer/schwab_data_link.py
import logging
import time
from typing import Dict, List, Optional, Tuple, Iterator, Any
from datetime import datetime, timedelta
import requests
from environments.tick_data import TickData
from data_streamer.data_link import DataLink


class SchwabDataLink(DataLink):
    """
    Data link for Schwab API that provides both historical and live data.
    Inherits from DataLink base class to integrate with the overall data flow.
    """

    def __init__(self, user_prefs: dict, access_token: str, symbols: list,
                 timeframe: str = "1m", days_history: int = 1):
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

        # Set up logger
        self.logger = logging.getLogger('SchwabDataLink')
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        # Load historical data immediately
        self.load_historical_data()

    def load_historical_data(self) -> bool:
        """
        Load historical data for all symbols using Schwab API

        Returns:
            True if data was loaded successfully, False otherwise
        """
        self.logger.info(f"Loading historical data for {len(self.symbols)} symbols")

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

                self.logger.info(f"Requesting data for {symbol}")
                response = requests.get(url, headers=headers, params=params)

                self.logger.info(f"Got response {response.status_code} for {symbol}")

                if response.status_code == 200:
                    data = response.json()
                    self.logger.info(f"Parsed JSON data for {symbol}")

                    # Process candles from response
                    if 'candles' in data and data['candles']:
                        self.candle_data[symbol] = []

                        for candle in data['candles']:
                            # Create timestamp from datetime field
                            timestamp = datetime.fromtimestamp(candle['datetime'] / 1000)

                            # Create tick data with symbol information
                            tick = TickData(
                                close=candle['close'],
                                open=candle['open'],
                                high=candle['high'],
                                low=candle['low'],
                                volume=candle.get('volume', 0),
                                timestamp=timestamp
                            )

                            # Manually add symbol since TickData might not support it
                            try:
                                tick.symbol = symbol
                            except AttributeError:
                                # If we can't set symbol as an attribute, continue anyway
                                pass

                            self.candle_data[symbol].append(tick)

                        self.logger.info(f"Loaded {len(self.candle_data[symbol])} historical candles for {symbol}")
                    else:
                        self.logger.warning(f"No candles data found for {symbol}")
                        success = False
                elif response.status_code == 401:
                    self.logger.error(f"Authentication error (401) loading data for {symbol}: {response.text}")
                    success = False
                else:
                    self.logger.error(
                        f"Error loading historical data for {symbol}: {response.status_code} - {response.text}")
                    success = False

            except Exception as e:
                self.logger.error(f"Exception loading historical data for {symbol}: {e}")
                import traceback
                traceback.print_exc()
                success = False

        return success

    def connect(self) -> bool:
        """
        Connect to Schwab streaming API

        Returns:
            bool: True if connection was successful, False otherwise
        """
        self.logger.info("Connecting to Schwab streaming API")
        try:
            # If streamer client already exists and is connected, use it
            if self.streaming_client and hasattr(self.streaming_client,
                                                 'is_connected') and self.streaming_client.is_connected:
                self.logger.info("Already connected to Schwab streaming API")
                return True

            # Try to import the streaming client class
            try:
                from schwab_api.streamer_client import SchwabStreamerClient
            except ImportError:
                self.logger.warning("Could not import SchwabStreamerClient, using basic implementation")
                # Set live_mode to true anyway to allow simulated data
                self.live_mode = True
                return True

            # Create streaming client
            self.streaming_client = SchwabStreamerClient(
                user_prefs=self.user_prefs,
                access_token=self.access_token
            )

            # Connect to streaming API
            success = self.streaming_client.connect()
            if not success:
                self.logger.error("Failed to connect to Schwab streaming API")
                return False

            # Subscribe to real-time data for our symbols
            self.logger.info(f"Subscribing to real-time data for symbols: {self.symbols}")

            # Subscribe to quotes
            self.streaming_client.subscribe_quotes(
                self.symbols,
                self._handle_quote_data
            )

            # Subscribe to charts
            self.streaming_client.subscribe_charts(
                self.symbols,
                self._handle_chart_data
            )

            self.live_mode = True
            self.logger.info("Successfully connected to Schwab streaming API")
            return True

        except Exception as e:
            self.logger.error(f"Error connecting to Schwab API: {e}")
            # Set live_mode to true anyway to allow the process to continue
            self.live_mode = True
            return False

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
                    bid = float(quote.get('1', 0.0))  # Bid price
                    ask = float(quote.get('2', 0.0))  # Ask price
                    last_price = float(quote.get('3', 0.0))  # Last price
                    volume = int(quote.get('8', 0))  # Volume

                    # Create timestamp
                    current_time = datetime.now()

                    # Create TickData
                    tick = TickData(
                        open=last_price,  # Use last price as placeholder
                        high=last_price,
                        low=last_price,
                        close=last_price,
                        volume=volume,
                        timestamp=current_time
                    )

                    # Set symbol
                    try:
                        tick.symbol = symbol
                    except AttributeError:
                        pass

                    # Store in latest_data
                    self.latest_data[symbol] = tick
                    self.logger.debug(f"Updated latest data for {symbol} with quote")

                except Exception as e:
                    self.logger.error(f"Error processing quote for {symbol}: {e}")

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
                    timestamp = datetime.fromtimestamp(timestamp_ms / 1000) if timestamp_ms else datetime.now()

                    # Extract OHLCV data
                    open_price = float(chart_entry.get('2', 0.0))
                    high_price = float(chart_entry.get('3', 0.0))
                    low_price = float(chart_entry.get('4', 0.0))
                    close_price = float(chart_entry.get('5', 0.0))
                    volume = int(chart_entry.get('6', 0))

                    # Create TickData
                    tick = TickData(
                        open=open_price,
                        high=high_price,
                        low=low_price,
                        close=close_price,
                        volume=volume,
                        timestamp=timestamp
                    )

                    # Set symbol
                    try:
                        tick.symbol = symbol
                    except AttributeError:
                        pass

                    # Store in latest_data
                    self.latest_data[symbol] = tick
                    self.logger.debug(f"Updated latest data for {symbol} with chart data")

                except Exception as e:
                    self.logger.error(f"Error processing chart data for {symbol}: {e}")

    def get_stats(self) -> dict:
        """
        Get statistics for data normalization

        Returns:
            Dict of statistics
        """
        # Default stats if no data available
        default_stats = {
            'open': {'min': 100.0, 'max': 200.0, 'sd': 10.0},
            'high': {'min': 110.0, 'max': 210.0, 'sd': 10.0},
            'low': {'min': 90.0, 'max': 190.0, 'sd': 10.0},
            'close': {'min': 100.0, 'max': 200.0, 'sd': 10.0}
        }

        # If we have data, calculate actual stats
        all_ticks = []
        for symbol in self.symbols:
            all_ticks.extend(self.candle_data.get(symbol, []))

        if not all_ticks:
            self.logger.warning("No data available for statistics calculation")
            return default_stats

        # Calculate statistics
        opens = [tick.open for tick in all_ticks if hasattr(tick, 'open') and tick.open is not None]
        highs = [tick.high for tick in all_ticks if hasattr(tick, 'high') and tick.high is not None]
        lows = [tick.low for tick in all_ticks if hasattr(tick, 'low') and tick.low is not None]
        closes = [tick.close for tick in all_ticks if hasattr(tick, 'close') and tick.close is not None]

        # Calculate standard deviation safely
        def safe_std(values):
            if not values:
                return 1.0
            import numpy as np
            return float(np.std(values))

        stats = {
            'open': {
                'min': min(opens) if opens else 100.0,
                'max': max(opens) if opens else 200.0,
                'sd': safe_std(opens)
            },
            'high': {
                'min': min(highs) if highs else 110.0,
                'max': max(highs) if highs else 210.0,
                'sd': safe_std(highs)
            },
            'low': {
                'min': min(lows) if lows else 90.0,
                'max': max(lows) if lows else 190.0,
                'sd': safe_std(lows)
            },
            'close': {
                'min': min(closes) if closes else 100.0,
                'max': max(closes) if closes else 200.0,
                'sd': safe_std(closes)
            }
        }

        return stats

    def serve_next_tick(self) -> Iterator[Tuple[TickData, int, int]]:
        """
        Serve next tick from either historical data, gap-filling data, or live data
        Implements the DataLink method

        Yields:
            Tuple of (tick_data, tick_index, day_index)
        """
        self.logger.info(f"Starting to serve ticks for symbols: {self.symbols}")

        # First serve historical data
        ticker_idx = 0
        for symbol in self.symbols:
            self.logger.info(f"Processing symbol {symbol}")
            self.day_index = ticker_idx

            if symbol not in self.candle_data or not self.candle_data[symbol]:
                self.logger.warning(f"No historical data for {symbol}")
                ticker_idx += 1
                continue

            for idx, tick in enumerate(self.candle_data[symbol]):
                self.logger.debug(f"Yielding historical tick {idx} for {symbol}")
                self.tick_index = idx

                # Ensure tick has symbol attribute
                try:
                    tick.symbol = symbol
                except AttributeError:
                    # If we can't set the attribute, it's okay, we'll use day_index
                    pass

                # Notify handlers before yielding
                self.notify_handlers(tick, idx, ticker_idx)
                yield tick, idx, ticker_idx

                # Add configurable delay for historical data simulation
                if self.delay > 0:
                    time.sleep(self.delay)

            # Get the timestamp of the last historical data point
            if self.candle_data[symbol]:
                last_tick = self.candle_data[symbol][-1]
                last_timestamp = getattr(last_tick, 'timestamp', None)

                # If we have a valid timestamp, fill the gap between history and now
                if last_timestamp and isinstance(last_timestamp, datetime):
                    self.logger.info(f"Filling gap between historical data and now for {symbol}")

                    # Get current market time
                    current_time = datetime.now()

                    # Start from the next minute after last historical data
                    gap_start = last_timestamp + timedelta(minutes=1)
                    gap_start = gap_start.replace(second=0, microsecond=0)  # Start at exact minute

                    # End at the current time, rounded down to the nearest minute
                    gap_end = current_time.replace(second=0, microsecond=0)

                    # Generate ticks for every minute in the gap
                    gap_time = gap_start
                    while gap_time < gap_end:
                        # Create gap-filling tick based on last historical data
                        gap_tick = TickData(
                            open=last_tick.close,
                            high=last_tick.close,
                            low=last_tick.close,
                            close=last_tick.close,
                            volume=0,  # No volume for gap-filling ticks
                            timestamp=gap_time
                        )

                        # Set symbol
                        try:
                            gap_tick.symbol = symbol
                        except AttributeError:
                            pass

                        self.logger.debug(f"Yielding gap-filling tick for {symbol} at {gap_time}")
                        # Notify handlers and yield
                        self.notify_handlers(gap_tick, self.tick_index, ticker_idx)
                        yield gap_tick, self.tick_index, ticker_idx
                        self.tick_index += 1

                        # Increment time by 1 minute
                        gap_time += timedelta(minutes=1)

                # Update last_tick to be the last generated tick
                if 'gap_tick' in locals():
                    last_tick = gap_tick

            # End of symbol data
            self.logger.info(f"End of historical and gap-filling data for {symbol}")
            yield None, -1, ticker_idx
            ticker_idx += 1

        # Switch to live mode
        self.logger.info("Switching to live mode")
        self.live_mode = True
        self.tick_index = 0

        # Connect to streaming API
        self.connect()

        # Setup variables for minute-based ticks
        last_minute_ticks = {}  # Store the last tick data for each symbol for each minute
        last_tick_times = {}  # Store the last time we generated a tick for each symbol

        # Initialize with current minute
        current_minute = datetime.now().replace(second=0, microsecond=0)
        for symbol in self.symbols:
            last_tick_times[symbol] = current_minute

        # Then stream live data with 1-minute candles
        while self.live_mode:
            current_time = datetime.now()
            current_minute = current_time.replace(second=0, microsecond=0)

            # Process each symbol
            for idx, symbol in enumerate(self.symbols):
                # Check if a new minute has started since our last tick
                if symbol in last_tick_times and current_minute > last_tick_times[symbol]:
                    # Get real-time data if available
                    if symbol in self.latest_data and self.latest_data[symbol]:
                        tick = self.latest_data[symbol]
                        self.latest_data[symbol] = None
                    else:
                        # If no real-time data, use the last known tick
                        if symbol in self.candle_data and self.candle_data[symbol]:
                            last_historical_tick = self.candle_data[symbol][-1]

                            # Create a new tick based on last historical or the last minute tick
                            if symbol in last_minute_ticks:
                                base_tick = last_minute_ticks[symbol]
                            else:
                                base_tick = last_historical_tick

                            # Create a new tick with the same values
                            tick = TickData(
                                open=base_tick.close,
                                high=base_tick.close,
                                low=base_tick.close,
                                close=base_tick.close,
                                volume=0,  # No volume for gap ticks
                                timestamp=last_tick_times[symbol]
                            )
                        else:
                            # No historical data to base on
                            continue

                    # Ensure tick has correct timestamp (use last minute)
                    tick.timestamp = last_tick_times[symbol]

                    # Ensure tick has symbol attribute
                    try:
                        tick.symbol = symbol
                    except AttributeError:
                        pass

                    self.logger.debug(f"Yielding 1-minute tick for {symbol} at {tick.timestamp}")
                    # Store this tick for the next minute if needed
                    last_minute_ticks[symbol] = tick

                    # Update the last tick time to the current minute
                    last_tick_times[symbol] = current_minute

                    # Notify handlers and yield
                    self.notify_handlers(tick, self.tick_index, idx)
                    yield tick, self.tick_index, idx
                    self.tick_index += 1

            # Add delay between live checks
            time.sleep(0.1)  # Smaller delay to be more responsive

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

    def disconnect(self) -> None:
        """Disconnect from Schwab streaming API"""
        self.live_mode = False
        if self.streaming_client:
            # Call disconnect method if available
            if hasattr(self.streaming_client, 'disconnect'):
                self.streaming_client.disconnect()