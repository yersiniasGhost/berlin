from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Tuple
import logging
from environments.tick_data import TickData


class CandleAggregator:
    """
    Aggregates tick-by-tick (PIP) data into OHLC candles of specified timeframe.
    Works with both historical and real-time streaming data.
    """

    def __init__(self, timeframe: str = "1m"):
        """
        Initialize the candle aggregator.

        Args:
            timeframe: Candle timeframe (1m, 5m, 15m, 30m, 1h, etc.)
        """
        self.timeframe = timeframe
        self.current_candles = {}  # Symbol -> current open candle
        self.completed_candles = {}  # Symbol -> list of completed candles
        self.candle_handlers = []  # Handlers to call when a candle completes

        # Set up logging
        self.logger = logging.getLogger(f'CandleAggregator')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        self.logger.info(f"Initialized CandleAggregator with timeframe {timeframe}")

        # Convert timeframe to minutes for calculations
        self.minutes = self._parse_timeframe_to_minutes()

    def _parse_timeframe_to_minutes(self) -> int:
        """Convert timeframe string to minutes"""
        if self.timeframe.endswith('m'):
            return int(self.timeframe[:-1])
        elif self.timeframe.endswith('h'):
            return int(self.timeframe[:-1]) * 60
        elif self.timeframe.endswith('d'):
            return int(self.timeframe[:-1]) * 60 * 24
        else:
            self.logger.warning(f"Unknown timeframe format: {self.timeframe}, defaulting to 1 minute")
            return 1

    def _get_candle_start_time(self, timestamp: datetime) -> datetime:
        """
        Calculate the start time of the candle that should contain this timestamp
        based on the timeframe.

        Args:
            timestamp: The timestamp to get the candle start time for

        Returns:
            Datetime representing the start of the candle
        """
        minutes = self.minutes

        if minutes == 1:
            # For 1-minute candles, round down to the nearest minute
            return timestamp.replace(second=0, microsecond=0)
        elif minutes == 5:
            # For 5-minute candles, round down to the nearest 5 minutes
            minute = (timestamp.minute // 5) * 5
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif minutes == 15:
            # For 15-minute candles, round down to the nearest 15 minutes
            minute = (timestamp.minute // 15) * 15
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif minutes == 30:
            # For 30-minute candles, round down to the nearest 30 minutes
            minute = (timestamp.minute // 30) * 30
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif minutes == 60:
            # For 1-hour candles, round down to the nearest hour
            return timestamp.replace(minute=0, second=0, microsecond=0)
        elif minutes == 60 * 24:
            # For daily candles, round down to the start of the day
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # Calculate based on the number of minutes
            total_minutes = timestamp.hour * 60 + timestamp.minute
            candle_minute = (total_minutes // minutes) * minutes

            candle_hour = candle_minute // 60
            candle_minute = candle_minute % 60

            return timestamp.replace(hour=candle_hour, minute=candle_minute, second=0, microsecond=0)

    def add_candle_handler(self, handler: Callable[[str, TickData], None]) -> None:
        """
        Add a handler that will be called when a candle is completed.

        Args:
            handler: Function that takes (symbol, candle_data)
        """
        self.candle_handlers.append(handler)

    def process_pip(self, quote: Dict) -> Optional[TickData]:
        """
        Process a new PIP data point, updating the current candle.
        Returns the completed candle if the time period has elapsed.

        Args:
            quote: PIP data dictionary from data source

        Returns:
            Completed candle as TickData or None if no candle was completed
        """
        # Extract symbol from quote
        symbol = quote.get('key', '')
        if not symbol:
            self.logger.warning("Quote missing symbol key")
            return None

        # Extract timestamp
        if '38' in quote:
            timestamp_ms = int(quote.get('38'))
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
        else:
            # For quotes without timestamps, use current time
            timestamp = datetime.now()
            self.logger.warning(f"Quote missing timestamp, using current time: {timestamp}")

        # Extract price - field '3' is typically last price
        price = float(quote.get('3', 0.0))
        if price == 0.0:
            self.logger.warning(f"Quote has zero price for {symbol}")
            return None

        # Extract volume if available
        volume = int(quote.get('8', 0))

        # Initialize data structures for new symbols
        if symbol not in self.current_candles:
            self.current_candles[symbol] = None

        if symbol not in self.completed_candles:
            self.completed_candles[symbol] = []

        # Determine candle start time for this timestamp
        candle_start_time = self._get_candle_start_time(timestamp)

        # Get the current candle for this symbol
        current_candle = self.current_candles[symbol]

        # If no current candle exists, create a new one
        if current_candle is None:
            self.current_candles[symbol] = TickData(
                symbol=symbol,
                timestamp=candle_start_time,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
                time_increment=self.timeframe
            )
            self.logger.debug(f"Created new {self.timeframe} candle for {symbol} @ {candle_start_time}")
            return None

        # If the quote belongs to the current candle, update it
        if candle_start_time == self._get_candle_start_time(current_candle.timestamp):
            # Update high and low
            current_candle.high = max(current_candle.high, price)
            current_candle.low = min(current_candle.low, price)

            # Update close price and volume
            current_candle.close = price
            current_candle.volume += volume

            self.logger.debug(f"Updated {self.timeframe} candle for {symbol}: {current_candle}")
            return None

        # Quote belongs to a new candle period - complete the current candle and start a new one
        completed_candle = current_candle

        # Create a new candle for the new period
        self.current_candles[symbol] = TickData(
            symbol=symbol,
            timestamp=candle_start_time,
            open=price,
            high=price,
            low=price,
            close=price,
            volume=volume,
            time_increment=self.timeframe
        )

        # Store the completed candle
        self.completed_candles[symbol].append(completed_candle)

        # Keep a limited history to avoid memory issues
        max_history = 1000
        if len(self.completed_candles[symbol]) > max_history:
            self.completed_candles[symbol] = self.completed_candles[symbol][-max_history:]

        # Notify all handlers about the completed candle
        for handler in self.candle_handlers:
            handler(symbol, completed_candle)

        self.logger.info(f"Completed {self.timeframe} candle for {symbol} @ {completed_candle.timestamp}: "
                         f"O:{completed_candle.open:.2f} H:{completed_candle.high:.2f} "
                         f"L:{completed_candle.low:.2f} C:{completed_candle.close:.2f} V:{completed_candle.volume}")

        return completed_candle

    def process_tick(self, tick: TickData) -> Tuple[Optional[TickData], Optional[TickData]]:
        """
        Process a tick (OHLC data), which can be from historical data or a completed lower-timeframe candle.
        Returns the current in-progress candle and any completed candle.

        Args:
            tick: Tick data to process

        Returns:
            Tuple of (current_candle, completed_candle) where either may be None
        """
        if not hasattr(tick, 'symbol') or not tick.symbol:
            self.logger.warning("Tick missing symbol")
            return None, None

        symbol = tick.symbol
        timestamp = tick.timestamp

        # Create a quote-like structure to reuse the process_pip logic
        quote = {
            'key': symbol,
            '38': int(timestamp.timestamp() * 1000),
            '3': tick.close,
            '8': tick.volume
        }

        # Process through the regular pip processing
        completed_candle = self.process_pip(quote)

        # Return the current and any completed candle
        return self.current_candles.get(symbol), completed_candle

    def get_candle_history(self, symbol: str) -> List[TickData]:
        """
        Get all completed candles for a symbol.

        Args:
            symbol: The symbol to get candles for

        Returns:
            List of completed candles in chronological order
        """
        return self.completed_candles.get(symbol, [])

    def get_latest_candle(self, symbol: str) -> Optional[TickData]:
        """
        Get the latest completed candle for a symbol.

        Args:
            symbol: The symbol to get the candle for

        Returns:
            The latest completed candle, or None if no candles exist
        """
        candles = self.get_candle_history(symbol)
        if candles:
            return candles[-1]
        return None

    def get_current_candle(self, symbol: str) -> Optional[TickData]:
        """
        Get the current in-progress candle for a symbol.

        Args:
            symbol: The symbol to get the candle for

        Returns:
            The current in-progress candle, or None if no candle exists
        """
        return self.current_candles.get(symbol)

    def get_all_candles(self, symbol: str) -> List[TickData]:
        """
        Get all candles (completed + current) for a symbol.

        Args:
            symbol: The symbol to get candles for

        Returns:
            List of all candles including the current one
        """
        candles = self.get_candle_history(symbol).copy()
        current = self.get_current_candle(symbol)

        if current:
            candles.append(current)

        return candles

    def clear_data(self) -> None:
        """Clear all candle data."""
        self.current_candles = {}
        self.completed_candles = {}
        self.logger.info("Cleared all candle data")

    def handle_completed_candle(self, symbol: str, candle: TickData) -> None:
        """
        Manually add a completed candle from an external source.

        Args:
            symbol: The symbol for the candle
            candle: The completed candle to add
        """
        if symbol not in self.completed_candles:
            self.completed_candles[symbol] = []

        # Make sure the candle has the correct timeframe
        if not hasattr(candle, 'time_increment') or candle.time_increment != self.timeframe:
            candle.time_increment = self.timeframe

        # Add to completed candles
        self.completed_candles[symbol].append(candle)

        # Notify handlers of the new candle
        for handler in self.candle_handlers:
            handler(symbol, candle)

        self.logger.info(f"Added external completed {self.timeframe} candle for {symbol} at {candle.timestamp}")
