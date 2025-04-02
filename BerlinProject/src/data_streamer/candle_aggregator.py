from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
from environments.tick_data import TickData

logger = logging.getLogger('CandleAggregator')


class CandleAggregator:
    """
    Aggregates tick data into OHLC candles of specified timeframe.
    Works with both historical and real-time data.
    """

    def __init__(self, timeframe: str = "1m"):
        """
        Initialize the candle aggregator.

        Args:
            timeframe: Candle timeframe (1m, 5m, 15m, 30m, 1h, 1d)
        """
        self.timeframe = timeframe
        self.current_candles = {}  # Symbol -> current open candle
        self.completed_candles = {}  # Symbol -> list of completed candles

        # Set up logging
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

        logger.info(f"Initialized CandleAggregator with timeframe {timeframe}")

    def _parse_timeframe_to_minutes(self) -> int:
        """Convert timeframe string to minutes"""
        if self.timeframe.endswith('m'):
            return int(self.timeframe[:-1])
        elif self.timeframe.endswith('h'):
            return int(self.timeframe[:-1]) * 60
        elif self.timeframe.endswith('d'):
            return int(self.timeframe[:-1]) * 60 * 24
        else:
            logger.warning(f"Unknown timeframe format: {self.timeframe}, defaulting to 1 minute")
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
        based on the timestamp of the new tick.

        Args:
            candle: The current open candle
            tick: The new tick data

        Returns:
            Boolean indicating if the candle should be closed
        """
        candle_start = self._get_candle_start_time(candle.timestamp)
        tick_start = self._get_candle_start_time(tick.timestamp)

        # If the tick belongs to a different candle period, close the current candle
        return tick_start > candle_start

    def process_tick(self, tick: TickData) -> Tuple[TickData, Optional[TickData]]:
        """
        Process a new tick, updating or creating candles as needed.

        Args:
            tick: The new tick data

        Returns:
            Tuple of (current_candle, completed_candle)
            completed_candle is None if no candle was completed
        """
        if not hasattr(tick, 'symbol') or tick.symbol is None:
            logger.warning(f"Tick missing symbol attribute: {tick}")
            return None, None

        symbol = tick.symbol
        completed_candle = None

        # Initialize data structures for new symbols
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
        Get all completed candles for a symbol.

        Args:
            symbol: The symbol to get candles for

        Returns:
            List of completed candles
        """
        return self.completed_candles.get(symbol, [])

    def get_all_candles(self, symbol: str) -> List[TickData]:
        """
        Get all candles (completed + current) for a symbol.

        Args:
            symbol: The symbol to get candles for

        Returns:
            List of all candles including the current one
        """
        candles = self.get_candle_history(symbol).copy()
        if symbol in self.current_candles:
            candles.append(self.current_candles[symbol])
        return candles

    def process_historical_candles(self, symbol: str, historical_candles: List[TickData]) -> None:
        """
        Process a list of historical candles for a symbol.

        Args:
            symbol: The symbol to process candles for
            historical_candles: List of historical candles
        """
        self.completed_candles[symbol] = historical_candles.copy()
        logger.info(f"Loaded {len(historical_candles)} historical candles for {symbol}")

    def clear_data(self) -> None:
        """Clear all candle data."""
        self.current_candles = {}
        self.completed_candles = {}
        logger.info("Cleared all candle data")