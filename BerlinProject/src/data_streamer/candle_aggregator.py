from datetime import datetime
from typing import Dict, Optional, List
from environments.tick_data import TickData


class CandleAggregator:
    """
    Aggregates PIPs into OHLC candles for ONE symbol and ONE timeframe.
    Maintains history of completed candles and current open candle.
    """

    def __init__(self, symbol: str, timeframe: str):
        self.symbol = symbol
        self.timeframe = timeframe
        self.current_candle: TickData | None = None  # Current open candle
        self.history: List[TickData] = []  # List of completed candles as TickData objects

    def process_pip(self, pip_data: Dict) -> Optional[TickData]:
        """Process a PIP, return completed candle if timeframe ended"""
        # Extract and validate data from PIP
        try:
            timestamp_ms = int(pip_data.get('38', 0))
            price = float(pip_data.get('3', 0.0))
            volume = int(pip_data.get('8', 0))
        except (ValueError, TypeError):
            return None

        # Basic validation
        if timestamp_ms == 0 or price <= 0:
            return None

        timestamp = datetime.fromtimestamp(timestamp_ms / 1000)

        # Sanity check timestamp (must be after year 2000)
        if timestamp.year < 2000:
            return None

        # Get candle start time for this timeframe
        candle_start = self._get_candle_start_time(timestamp)

        # If no current candle or new candle period
        if self.current_candle is None or self.current_candle.timestamp != candle_start:
            # Save completed candle to return
            completed_candle = self.current_candle

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

            # Add completed candle to history if it exists
            if completed_candle:
                self.history.append(completed_candle)

            # Return completed candle (None for first candle)
            return completed_candle
        else:
            # Update existing candle
            self.current_candle.high = max(self.current_candle.high, price)
            self.current_candle.low = min(self.current_candle.low, price)
            self.current_candle.close = price
            self.current_candle.volume += volume

            # No completed candle
            return None

    def _get_candle_start_time(self, timestamp: datetime) -> datetime:
        """Get candle start time for this timeframe"""
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
            return timestamp.replace(second=0, microsecond=0)  # Default to 1m

    def get_current_candle(self) -> Optional[TickData]:
        """Get current open candle"""
        return self.current_candle

    def get_history(self) -> List[TickData]:
        """Get list of all completed candles"""
        return self.history

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
        # Load historical data for this symbol and timeframe
        historical_data = data_link.load_historical_data(self.symbol, self.timeframe)

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
