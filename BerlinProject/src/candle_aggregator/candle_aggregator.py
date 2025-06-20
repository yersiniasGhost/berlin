from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Tuple
from models.tick_data import TickData


class CandleAggregator(ABC):
    """
    Abstract base class for candle aggregation.
    Handles timing and workflow, delegates calculation to subclasses.
    """

    def __init__(self, symbol: str, timeframe: str):
        self.symbol = symbol
        self.timeframe = timeframe
        self.current_candle: Optional[TickData] = None
        self.history: List[TickData] = []
        self.completed_candle: Optional[TickData] = None

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

    def process_tick(self, tick_data: TickData) -> Optional[TickData]:
        """Process tick and return completed candle if timeframe ended"""
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
        """Prepopulate with direct historical data"""
        if len(historical_data) > 1:
            self.history = historical_data[:-1]
        if historical_data:
            self.current_candle = historical_data[-1]
        return len(historical_data)

    def _prepopulate_processed(self, historical_data: List[TickData]) -> int:
        """Prepopulate by processing through aggregator"""
        for candle in historical_data:
            tick_data = self._convert_candle_to_tick(candle)
            self.process_tick(tick_data)
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