from typing import Dict, List, Optional, Tuple, Iterator, Any
from datetime import datetime
import logging
from environments.tick_data import TickData
from data_streamer.external_tool import ExternalTool

logger = logging.getLogger('SchwabDataLink')


class SchwabDataLink:
    """
    Data link implementation for Schwab API.

    This class provides an interface to access Schwab streaming data
    and historical data in a format compatible with the DataStreamer.
    """

    def __init__(self, schwab_client, symbols: List[str]):
        """
        Initialize the Schwab data link

        Args:
            schwab_client: Authenticated Schwab client
            symbols: List of symbols to track
        """
        self.schwab_client = schwab_client
        self.symbols = symbols
        self.streaming_client = None
        self.tick_data = {}  # Stores the latest tick data by symbol
        self.candle_data = {}  # Stores candle data by symbol
        self.current_index = 0
        self.adapter = None

        # Setup logging
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    def connect(self):
        """Connect to Schwab streaming API"""
        if not self.schwab_client:
            logger.error("No Schwab client provided")
            return False

        try:
            # Create streaming client
            self.streaming_client = self.schwab_client.create_streaming_session()

            if not self.streaming_client:
                logger.error("Failed to create streaming session")
                return False

            # Create adapter and subscribe to data streams
            from schwab_data_stream import SchwabDataStreamAdapter
            self.adapter = SchwabDataStreamAdapter(self.symbols)

            # Subscribe to quotes
            self.streaming_client.subscribe_quotes(self.symbols, self.adapter.handle_quote_data)
            logger.info(f"Subscribed to quotes for {self.symbols}")

            # Subscribe to charts
            self.streaming_client.subscribe_charts(self.symbols, self.adapter.handle_chart_data)
            logger.info(f"Subscribed to charts for {self.symbols}")

            return True
        except Exception as e:
            logger.error(f"Error connecting to Schwab streaming API: {e}")
            return False

    def get_stats(self) -> dict:
        """
        Get statistics for the current data

        Returns:
            Dictionary of statistics
        """
        # Fetch historical data to compute statistics
        stats = {
            'open': {
                'min': 99.0,
                'max': 105.0,
                'sd': 1.2
            },
            'high': {
                'min': 100.0,
                'max': 106.0,
                'sd': 1.1
            },
            'low': {
                'min': 98.0,
                'max': 104.0,
                'sd': 1.1
            },
            'close': {
                'min': 99.0,
                'max': 104.0,
                'sd': 1.0
            }
        }

        # If we have historical data, compute actual statistics
        if self.adapter and self.adapter.latest_data:
            # Compute stats from historical data
            for symbol, tick_data in self.adapter.latest_data.items():
                if hasattr(tick_data, 'close_price'):
                    # Update the statistics based on actual data
                    stats['close']['min'] = min(stats['close']['min'], tick_data.close_price * 0.9)
                    stats['close']['max'] = max(stats['close']['max'], tick_data.close_price * 1.1)

                    stats['open']['min'] = min(stats['open']['min'], tick_data.open_price * 0.9)
                    stats['open']['max'] = max(stats['open']['max'], tick_data.open_price * 1.1)

                    stats['high']['min'] = min(stats['high']['min'], tick_data.high_price * 0.9)
                    stats['high']['max'] = max(stats['high']['max'], tick_data.high_price * 1.1)

                    stats['low']['min'] = min(stats['low']['min'], tick_data.low_price * 0.9)
                    stats['low']['max'] = max(stats['low']['max'], tick_data.low_price * 1.1)

        return stats

    def fetch_historical_data(self, symbol: str, days: int = 5) -> List[TickData]:
        """
        Fetch historical data for a symbol

        Args:
            symbol: Stock symbol
            days: Number of days of history to fetch

        Returns:
            List of TickData objects
        """
        if not self.schwab_client:
            logger.error("No Schwab client provided")
            return []

        try:
            # Fetch historical data
            response = self.schwab_client.price_history(
                symbol=symbol,
                periodType="day",
                period=days,
                frequencyType="minute",
                frequency=1,
                needExtendedHoursData=True
            )

            if hasattr(response, 'status_code') and response.status_code == 200:
                data = response.json()

                # Convert to TickData format
                tick_data_list = []
                if 'candles' in data:
                    for candle in data['candles']:
                        timestamp = datetime.fromtimestamp(candle['datetime'] / 1000)

                        tick = TickData(
                            symbol=symbol,
                            timestamp=timestamp,
                            price=candle['close'],
                            volume=candle['volume'],
                            bid=candle['close'],  # Use close as bid
                            ask=candle['close'],  # Use close as ask
                            open_price=candle['open'],
                            high_price=candle['high'],
                            low_price=candle['low'],
                            close_price=candle['close']
                        )

                        tick_data_list.append(tick)

                logger.info(f"Retrieved {len(tick_data_list)} historical data points for {symbol}")
                return tick_data_list
            else:
                logger.error(f"Error fetching historical data: {getattr(response, 'text', 'No response text')}")
                return []
        except Exception as e:
            logger.exception(f"Exception fetching historical data: {e}")
            return []

    def serve_next_tick(self) -> Iterator[Tuple[TickData, int, int]]:
        """
        Generator to serve the next tick

        Yields:
            Tuple of (TickData, tick_index, day_index)
        """
        # If no adapter or no data, yield None
        if not self.adapter or not self.adapter.latest_data:
            yield None, 0, 0
            return

        # Continuously yield the latest tick data
        while True:
            for symbol in self.symbols:
                if symbol in self.adapter.latest_data:
                    tick_data = self.adapter.latest_data[symbol]
                    yield tick_data, self.current_index, 0
                    self.current_index += 1

            # Yield None to mark the end of a batch
            yield None, 0, 0

    def reset_index(self):
        """Reset the tick index"""
        self.current_index = 0

    def get_next2(self):
        """Get the next tick"""
        # If no adapter or no data, return None
        if not self.adapter or not self.adapter.latest_data:
            return None

        # Get the next symbol's data
        if self.current_index < len(self.symbols):
            symbol = self.symbols[self.current_index]
            self.current_index += 1

            if symbol in self.adapter.latest_data:
                return self.adapter.latest_data[symbol]

        # Reset index if we've gone through all symbols
        self.current_index = 0
        return None

    def get_present_sample_and_index(self) -> Tuple[dict, int]:
        """
        Get the current sample and index

        Returns:
            Tuple of (sample_dict, index)
        """
        # If no adapter or no data, return None
        if not self.adapter or not self.adapter.latest_data:
            return None, None

        # Create a sample from the latest data
        sample = {}
        for symbol in self.symbols:
            if symbol in self.adapter.latest_data:
                tick_data = self.adapter.latest_data[symbol]
                sample[symbol] = {
                    'timestamp': tick_data.timestamp,
                    'price': tick_data.price,
                    'volume': tick_data.volume,
                    'open': tick_data.open_price,
                    'high': tick_data.high_price,
                    'low': tick_data.low_price,
                    'close': tick_data.close_price
                }

        return sample, self.current_index

    @classmethod
    def get_schwab_data_link(cls, schwab_client, symbols: List[str]):
        """
        Create and connect a Schwab data link

        Args:
            schwab_client: Authenticated Schwab client
            symbols: List of symbols to track

        Returns:
            Connected SchwabDataLink instance
        """
        data_link = cls(schwab_client, symbols)
        connected = data_link.connect()

        if connected:
            logger.info(f"Created Schwab data link for {symbols}")
            return data_link
        else:
            logger.error(f"Failed to create Schwab data link for {symbols}")
            return None