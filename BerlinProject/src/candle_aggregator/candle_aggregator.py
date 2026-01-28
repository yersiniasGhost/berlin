from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Tuple
from models.tick_data import TickData
from mlf_utils.timezone_utils import is_market_hours, is_aware
import numpy as np


class CandleAggregator(ABC):
    """
    Abstract base class for candle aggregation.
    Handles timing and workflow, delegates calculation to subclasses.
    """

    def __init__(self, symbol: str, timeframe: str, include_extended_hours: bool = True):
        self.symbol = symbol
        self.timeframe = timeframe
        self.timeframe_minutes = self._calculate_timeframe_minutes()
        self.include_extended_hours = include_extended_hours
        self.current_candle: Optional[TickData] = None
        self.history: List[TickData] = []
        self.completed_candle: Optional[TickData] = None
        self.maximum_drawdown: Optional[float] = None
        self.volatility: Optional[float] = None
        self.volatility_adjusted: Optional[float] = None

    @abstractmethod
    def _get_aggregator_type(self) -> str:
        """Return aggregator type identifier"""
        pass

    @abstractmethod
    def _create_new_candle(self, tick_data: TickData, candle_start_time: datetime) -> TickData:
        """Create new candle from first tick"""
        pass

    @abstractmethod
    def _update_existing_candle(self, tick_data: TickData) -> None:
        """Update current candle with new tick"""
        pass

    def _calculate_timeframe_minutes(self) -> int:
        """Convert timeframe string to minutes (calculated once during init)
        Handles formats like '1m', '5m', '1m-normal', '5m-heiken'"""
        # Extract just the timeframe part (before '-' if present)
        base_timeframe = self.timeframe.split('-')[0] if '-' in self.timeframe else self.timeframe

        timeframe_map = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60
        }
        return timeframe_map.get(base_timeframe, 1)

    def get_timeframe_minutes(self) -> int:
        """Get timeframe in minutes"""
        return self.timeframe_minutes

    def _is_trading_hours(self, timestamp: datetime) -> bool:
        """
        Check if timestamp is during regular trading hours (9:30 AM - 4:00 PM ET).

        Regular market hours for NYSE/NASDAQ:
        - 9:30 AM - 4:00 PM ET (Eastern Time)

        Extended hours (filtered when include_extended_hours=False):
        - Pre-market: Before 9:30 AM ET
        - After-hours: 4:00 PM ET and later

        Args:
            timestamp: Timezone-aware datetime to check (any timezone accepted,
                      will be converted to ET internally)

        Returns:
            bool: True if during regular trading hours, False otherwise

        Note:
            This method now uses the centralized is_market_hours() function from
            timezone_utils, which properly handles timezone conversion and DST.
        """
        # Use centralized market hours check from timezone_utils
        # This handles any timezone-aware datetime by converting to ET internally
        if not is_aware(timestamp):
            # Log warning for naive datetimes (legacy compatibility)
            # In future, this should raise an error
            from mlf_utils.log_manager import LogManager
            logger = LogManager().get_logger("CandleAggregator")
            logger.warning(f"Naive datetime passed to _is_trading_hours: {timestamp}. "
                          f"This may cause incorrect market hours filtering. "
                          f"Please update data source to use timezone-aware datetimes.")
            # Fall back to old behavior for naive datetimes (assume ET)
            hour = timestamp.hour
            minute = timestamp.minute
            if hour < 9 or (hour == 9 and minute < 30):
                return False
            if hour >= 16:
                return False
            return True

        return is_market_hours(timestamp)

    def process_tick(self, tick_data: TickData) -> Optional[TickData]:
        """Process tick and return completed candle if timeframe ended"""
        # Filter extended hours if configured
        if not self.include_extended_hours and not self._is_trading_hours(tick_data.timestamp):
            return None  # Skip this tick - outside regular trading hours

        candle_start = self._get_candle_start_time(tick_data.timestamp)

        if self._should_start_new_candle(candle_start):
            return self._start_new_candle(tick_data, candle_start)
        else:
            self._update_existing_candle(tick_data)
            self.completed_candle = None
            return None

    def _should_start_new_candle(self, candle_start: datetime) -> bool:
        """Check if new candle should be started"""
        return self.current_candle is None or self.current_candle.timestamp != candle_start

    def _start_new_candle(self, tick_data: TickData, candle_start: datetime) -> Optional[TickData]:
        """Start new candle and return completed one"""
        completed_candle = self._complete_current_candle()
        self.current_candle = self._create_new_candle(tick_data, candle_start)
        self.completed_candle = completed_candle
        return completed_candle

    def _complete_current_candle(self) -> Optional[TickData]:
        """Move current candle to history"""
        if self.current_candle is None:
            return None

        self.history.append(self.current_candle)
        return self.current_candle

    def _get_candle_start_time(self, timestamp: datetime) -> datetime:
        """Get normalized candle start time for timeframe"""
        if self.timeframe == "1m":
            return timestamp.replace(second=0, microsecond=0)
        elif self.timeframe == "5m":
            minute = (timestamp.minute // 5) * 5
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif self.timeframe == "15m":
            minute = (timestamp.minute // 15) * 15
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif self.timeframe == "30m":
            minute = (timestamp.minute // 30) * 30
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif self.timeframe == "1h":
            return timestamp.replace(minute=0, second=0, microsecond=0)
        else:
            return timestamp.replace(second=0, microsecond=0)

    def get_current_candle(self) -> Optional[TickData]:
        """Get current open candle"""
        return self.current_candle

    def get_history(self) -> List[TickData]:
        """Get completed candles"""
        return self.history.copy()

    def get_latest_candle(self) -> Optional[TickData]:
        """Get most recent completed candle"""
        return self.history[-1] if self.history else None

    def prepopulate_data(self, data_link) -> int:
        """Load historical data into aggregator"""
        historical_data = data_link.load_historical_data(self.symbol, self.timeframe)

        if not historical_data:
            return 0

        historical_data.sort(key=lambda x: x.timestamp)

        if self._get_aggregator_type() == "normal":
            return self._prepopulate_normal(historical_data)
        else:
            return self._prepopulate_processed(historical_data)

    def _prepopulate_normal(self, historical_data: List[TickData]) -> int:
        """
        Prepopulate with direct historical data from current trading session.

        The data link is responsible for fetching the correct time range (today's session),
        so we use all provided data without additional filtering.
        """
        if not historical_data:
            return 0

        # Log the data range for debugging
        from mlf_utils.log_manager import LogManager
        logger = LogManager().get_logger("CandleAggregator")
        first_ts = historical_data[0].timestamp
        last_ts = historical_data[-1].timestamp
        logger.info(f"Prepopulating {self.symbol} {self.timeframe}: {len(historical_data)} candles "
                   f"from {first_ts.strftime('%Y-%m-%d %H:%M')} to {last_ts.strftime('%Y-%m-%d %H:%M')}")

        # Store history (all but last) and current candle (last one)
        if len(historical_data) > 1:
            self.history = historical_data[:-1]
        if historical_data:
            self.current_candle = historical_data[-1]

        # Calculate maximum drawdown after prepopulation
        self.calculate_maximum_drawdown()

        return len(historical_data)

    def _prepopulate_processed(self, historical_data: List[TickData]) -> int:
        """Prepopulate by processing through aggregator"""
        for candle in historical_data:
            tick_data = self._convert_candle_to_tick(candle)
            self.process_tick(tick_data)

        # Calculate maximum drawdown after prepopulation
        self.calculate_maximum_drawdown()

        return len(historical_data)

    def _convert_candle_to_tick(self, candle: TickData) -> TickData:
        """Convert historical candle to tick for processing"""
        return TickData(
            symbol=candle.symbol,
            timestamp=candle.timestamp,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
            time_increment="HISTORICAL"
        )

    def calculate_maximum_drawdown(self) -> float:
        """
        Calculate maximum drawdown from candle history.
        Maximum drawdown is the largest peak-to-trough decline in close prices.

        Returns:
            float: Maximum drawdown as a percentage (negative value), or 0.0 if insufficient data
        """
        if len(self.history) < 2:
            return 0.0

        # Extract close prices from history
        close_prices = [candle.close for candle in self.history]

        # Track running maximum and maximum drawdown
        running_max = close_prices[0]
        max_drawdown = 0.0

        for price in close_prices[1:]:
            # Update running maximum
            running_max = max(running_max, price)

            # Calculate drawdown from running maximum
            if running_max > 0:
                drawdown = ((price - running_max) / running_max) * 100
                max_drawdown = min(max_drawdown, drawdown)

        self.maximum_drawdown = max_drawdown
        return max_drawdown

    def get_market_return(self) -> float:
        d = self.history[-1].close - self.history[0].close
        return d

    def get_maximum_drawdown(self) -> float:
        if not self.maximum_drawdown:
            self.calculate_maximum_drawdown()
            # self.maximum_drawdown = self.get_market_return()
        return self.maximum_drawdown

    def get_volatility(self, net_profit: Optional[float] = None) -> Tuple[float, Optional[float]]:
        if not self.volatility:
            close_prices = [candle.close for candle in self.history]
            clses = np.array(close_prices)
            price_volatility = clses.std()
            minimum, maximum = clses.min(), clses.max()
            if minimum == maximum:
                print("WTF - volatility error")
            else:
                self.volatility = price_volatility / (maximum-minimum)
        volatility_adjusted = None
        if net_profit:
            volatility_adjusted = net_profit / self.volatility
        return self.volatility, volatility_adjusted
