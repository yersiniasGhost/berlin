from datetime import datetime
from typing import Dict, Optional, List, Tuple, Any
from models.tick_data import TickData


class CandleAggregator:
    """
    Aggregates PIPs into OHLC candles for ONE symbol and ONE timeframe.
    Maintains history of completed candles and current open candle.
    """

    def __init__(self, symbol: str, timeframe: str):
        self.symbol = symbol
        self.timeframe = timeframe
        self.current_candle: Optional[TickData] = None
        self.history: List[TickData] = []
        self.completed_candle: Optional[TickData] = None

    def process_tick(self, tick_data: TickData) -> Optional[TickData]:
        """
        Process a TickData object, return completed candle if timeframe ended

        Args:
            tick_data: TickData object from data source (already validated)

        Returns:
            TickData object if candle completed, None otherwise
        """
        if not tick_data.timestamp:
            return None

        timestamp = tick_data.timestamp
        price = tick_data.close
        volume = tick_data.volume

        # Get candle start time for this timeframe
        candle_start = self._get_candle_start_time(timestamp)

        # Check if we need a new candle
        if self.current_candle is None or self.current_candle.timestamp != candle_start:
            # Save completed candle to return
            completed_candle_to_return = self.current_candle

            # Add completed candle to history if it exists
            if self.current_candle is not None:
                self.history.append(self.current_candle)

            # Start new candle
            self.current_candle = TickData(
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
                timestamp=candle_start,
                symbol=self.symbol,
                time_increment=self.timeframe
            )

            # Set completed candle for external access
            self.completed_candle = completed_candle_to_return

            # Return completed candle (None for first candle)
            return completed_candle_to_return
        else:
            # Update existing candle
            self.current_candle.high = max(self.current_candle.high, price)
            self.current_candle.low = min(self.current_candle.low, price)
            self.current_candle.close = price
            self.current_candle.volume += volume
            self.completed_candle = None

            # No completed candle
            return None

    def _get_candle_start_time(self, timestamp: datetime) -> datetime:
        """Get candle start time for this timeframe"""
        try:
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
                # Default to 1m for unknown timeframes
                return timestamp.replace(second=0, microsecond=0)
        except Exception:
            # Fallback to original timestamp
            return timestamp

    def get_current_candle(self) -> Optional[TickData]:
        """Get current open candle"""
        return self.current_candle

    def get_history(self) -> List[TickData]:
        """Get list of all completed candles"""
        return self.history

    def get_data(self) -> Tuple[TickData, List[TickData]]:
        return self.current_candle, self.history

    def get_latest_candle(self) -> Optional[TickData]:
        """Get most recent completed candle from history"""
        if self.history:
            return self.history[-1]
        return None

    def prepopulate_data(self, data_link):
        """
        Prepopulate history for this aggregator's symbol and timeframe.

        Args:
            data_link: Data link object with load_historical_data method

        Returns:
            Number of candles loaded
        """
        try:
            # Load historical data for this symbol and timeframe
            historical_data = data_link.load_historical_data(self.symbol, self.timeframe)

            # Handle CSReplayDataLink which returns None or empty list
            if not historical_data:
                return 0

            # Sort by timestamp to ensure chronological order
            historical_data.sort(key=lambda x: x.timestamp)

            # Store all but the last candle in history
            if len(historical_data) > 1:
                self.history = historical_data[:-1]

            # Set current candle to the most recent one
            if historical_data:
                self.current_candle = historical_data[-1]

            return len(historical_data)

        except Exception:
            return 0