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
        self.current_candle: Optional[TickData] = None  # Current open candle
        self.history: List[TickData] = []  # List of completed candles as TickData objects
        self.completed_candle: Optional[TickData] = None

    def process_pip(self, pip_data: Dict[str, Any]) -> Optional[TickData]:
        """
        Process a PIP, return completed candle if timeframe ended

        Args:
            pip_data: Dictionary containing PIP data from Schwab

        Returns:
            TickData object if candle completed, None otherwise
        """
        try:
            # Extract and validate data from PIP
            timestamp_ms: int = int(pip_data.get('38', 0))
            price: float = float(pip_data.get('3', 0.0))
            volume: int = int(pip_data.get('8', 0))

            # Basic validation
            if timestamp_ms == 0 or price <= 0:
                print(f"AGGREGATOR {self.timeframe}: Invalid PIP data - timestamp: {timestamp_ms}, price: {price}")
                return None

            timestamp: datetime = datetime.fromtimestamp(timestamp_ms / 1000)

            # Sanity check timestamp (must be after year 2000)
            if timestamp.year < 2000:
                print(f"AGGREGATOR {self.timeframe}: Invalid timestamp year: {timestamp.year}")
                return None

            # Get candle start time for this timeframe
            candle_start: datetime = self._get_candle_start_time(timestamp)

            # Debug logging
            print(
                f"AGGREGATOR {self.timeframe}: PIP at {timestamp.strftime('%H:%M:%S')} -> candle start {candle_start.strftime('%H:%M:%S')}")

            # If no current candle or new candle period
            if self.current_candle is None or self.current_candle.timestamp != candle_start:
                print(f"AGGREGATOR {self.timeframe}: NEW CANDLE PERIOD DETECTED!")

                # Save completed candle to return
                self.completed_candle = self.current_candle

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

                print(
                    f"AGGREGATOR {self.timeframe}: Created new candle at {candle_start.strftime('%H:%M:%S')} with price ${price}")

                # Add completed candle to history if it exists
                if self.completed_candle:
                    self.history.append(self.completed_candle)
                    print(
                        f"AGGREGATOR {self.timeframe}: CANDLE COMPLETED! Added to history (total: {len(self.history)})")
                    print(
                        f"AGGREGATOR {self.timeframe}: Completed candle - O:{self.completed_candle.open} H:{completed_candle.high} L:{completed_candle.low} C:{completed_candle.close}")

                # Return completed candle (None for first candle)
                return self.completed_candle
            else:
                # Update existing candle
                self.current_candle.high = max(self.current_candle.high, price)
                self.current_candle.low = min(self.current_candle.low, price)
                self.current_candle.close = price
                self.current_candle.volume += volume
                self.completed_candle = None

                print(
                    f"AGGREGATOR {self.timeframe}: Updated existing candle - H:{self.current_candle.high} L:{self.current_candle.low} C:{self.current_candle.close}")

                # No completed candle
                return None

        except (ValueError, TypeError) as e:
            print(f"AGGREGATOR {self.timeframe}: Error processing PIP data: {e}")
            return None
        except Exception as e:
            print(f"AGGREGATOR {self.timeframe}: Unexpected error: {e}")
            import traceback
            traceback.print_exc()
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
        # Load historical data for this symbol and timeframe
        historical_data = data_link.load_historical_data(self.symbol, self.timeframe)

        # Sort by timestamp to ensure chronological order
        historical_data.sort(key=lambda x: x.timestamp)

        # Store all but the last candle in history
        if len(historical_data) > 1:
            self.history = historical_data[:-1]

        # Set current candle to the most recent one
        if historical_data:
            self.current_candle = historical_data[-1]

        return len(historical_data)

