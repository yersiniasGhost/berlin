"""
MongoReplayDataLink - Streams historical tick data from MongoDB with playback controls.

Supports:
- Configurable playback speed (0.5x to 10x)
- Pause/Resume functionality
- Stop and restart capabilities
- Single ticker, single date streaming
"""

import threading
import time
from typing import Set, Dict, List, Optional
from datetime import datetime

from pymongo import MongoClient
from data_streamer.data_link import DataLink
from models.tick_data import TickData
from mlf_utils.env_vars import EnvVars
from mlf_utils.timezone_utils import assume_et
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("MongoReplayDataLink")


class MongoReplayDataLink(DataLink):
    """
    DataLink that streams historical tick data from MongoDB TickHistory.
    Designed for replay mode in stock_analysis_ui.
    """

    # Valid playback speeds
    VALID_SPEEDS = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 100.0]

    def __init__(self, playback_speed: float = 1.0):
        super().__init__()
        self.playback_speed: float = playback_speed

        # State tracking
        self.is_streaming: bool = False
        self.is_paused: bool = False
        self.streaming_thread: Optional[threading.Thread] = None
        self.subscribed_symbols: Set[str] = set()

        # Data management
        self.ticker: Optional[str] = None
        self.date: Optional[datetime] = None
        self.tick_data: List[TickData] = []
        self.current_index: int = 0

        # Threading control
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        self._stop_event = threading.Event()

        # Callbacks for UI updates
        self.on_replay_complete: Optional[callable] = None
        self.on_tick_processed: Optional[callable] = None

        # Statistics
        self.total_ticks_processed: int = 0
        self.error_count: int = 0

    def load_data(self, ticker: str, date: datetime) -> bool:
        """
        Load tick data for a specific ticker and date from MongoDB.
        Uses direct MongoDB query approach (same as MongoDBConnect).

        Args:
            ticker: Stock symbol (e.g., 'NVDA')
            date: The date to load data for

        Returns:
            True if data loaded successfully, False otherwise
        """
        try:
            self.ticker = ticker.upper()
            self.date = date

            # Connect to MongoDB directly (like MongoDBConnect does)
            env = EnvVars()
            client = MongoClient(env.mongo_host, env.mongo_port, serverSelectionTimeoutMS=5000)
            db = client[env.mongo_database]
            collection = db[env.mongo_collection]

            # Query for the specific month containing the date
            query = {
                'ticker': self.ticker,
                'year': date.year,
                'month': date.month
            }

            doc = collection.find_one(query)
            client.close()

            if not doc:
                logger.error(f"No data found for {self.ticker} on {date.strftime('%Y-%m-%d')}")
                return False

            # Extract tick data for the specific day
            data_dict = doc.get('data', {})
            day_str = str(date.day)

            if day_str not in data_dict:
                logger.error(f"No data for day {day_str} in month {date.month}")
                return False

            day_data = data_dict[day_str]

            # Convert raw OHLC dicts to TickData objects
            self.tick_data = []
            for timestamp_str, ohlc in day_data.items():
                timestamp_seconds = int(timestamp_str)

                # Convert timestamp (stored as seconds-since-midnight in ET)
                hours = timestamp_seconds // 3600
                minutes = (timestamp_seconds % 3600) // 60
                seconds = timestamp_seconds % 60

                # Create ET-aware datetime since MongoDB stores market time (Eastern)
                naive_dt = datetime(date.year, date.month, date.day, hours, minutes, seconds)
                dt = assume_et(naive_dt)

                # Parse OHLC values (may be stored as floats or strings)
                tick = TickData(
                    symbol=self.ticker,
                    timestamp=dt,
                    open=self._parse_float(ohlc.get('open', 0)),
                    high=self._parse_float(ohlc.get('high', 0)),
                    low=self._parse_float(ohlc.get('low', 0)),
                    close=self._parse_float(ohlc.get('close', 0)),
                    volume=ohlc.get('volume', 0),
                    time_increment="RAW"
                )
                self.tick_data.append(tick)

            # Sort by timestamp
            self.tick_data.sort(key=lambda t: t.timestamp)

            if not self.tick_data:
                logger.error(f"No tick data found for {self.ticker} on {date.strftime('%Y-%m-%d')}")
                return False

            logger.info(f"Loaded {len(self.tick_data)} ticks for {self.ticker} on {date.strftime('%Y-%m-%d')}")
            return True

        except Exception as e:
            logger.error(f"Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _parse_float(self, value) -> float:
        """Parse float values that may be stored as strings with 'float: ' prefix"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            if value.startswith("float: "):
                return float(value[7:])
            return float(value)
        return 0.0

    def start_streaming(self) -> bool:
        """Start streaming the loaded tick data."""
        if self.is_streaming:
            logger.warning("Already streaming")
            return True

        if not self.tick_data:
            logger.error("No data loaded. Call load_data() first.")
            return False

        # Reset state
        self.is_streaming = True
        self.is_paused = False
        self.current_index = 0
        self.total_ticks_processed = 0
        self.error_count = 0

        # Clear stop event
        self._stop_event.clear()
        self._pause_event.set()

        # Start streaming thread
        self.streaming_thread = threading.Thread(target=self._stream_data, daemon=True)
        self.streaming_thread.start()

        logger.info(f"Started streaming {self.ticker} at {self.playback_speed}x speed")
        return True

    def _stream_data(self) -> None:
        """Internal method to stream data in a separate thread."""
        try:
            last_timestamp = None

            while self.current_index < len(self.tick_data):
                # Check for stop signal
                if self._stop_event.is_set():
                    logger.info("Streaming stopped by user")
                    break

                # Wait if paused
                self._pause_event.wait()

                # Check stop again after resume
                if self._stop_event.is_set():
                    break

                try:
                    tick = self.tick_data[self.current_index]
                    current_timestamp = tick.timestamp

                    # Calculate and apply delay based on playback speed
                    if last_timestamp is not None and current_timestamp > last_timestamp:
                        delay_seconds = (current_timestamp - last_timestamp).total_seconds()
                        adjusted_delay = delay_seconds / self.playback_speed
                        adjusted_delay = min(adjusted_delay, 5.0)  # Cap at 5 seconds

                        if adjusted_delay > 0:
                            # Sleep in small increments to check for pause/stop
                            sleep_increment = 0.1
                            elapsed = 0
                            while elapsed < adjusted_delay:
                                if self._stop_event.is_set():
                                    break
                                self._pause_event.wait()
                                if self._stop_event.is_set():
                                    break
                                time.sleep(min(sleep_increment, adjusted_delay - elapsed))
                                elapsed += sleep_increment

                    last_timestamp = current_timestamp

                    # Only process subscribed symbols
                    if self.ticker in self.subscribed_symbols:
                        # Send to DataStreamers
                        if self.ticker in self.data_streamers:
                            for data_streamer in self.data_streamers[self.ticker]:
                                try:
                                    data_streamer.process_tick(tick)
                                except Exception as e:
                                    logger.error(f"Error processing tick: {e}")
                                    self.error_count += 1

                    self.total_ticks_processed += 1
                    self.current_index += 1

                    # Callback for progress tracking
                    if self.on_tick_processed:
                        try:
                            progress = (self.current_index / len(self.tick_data)) * 100
                            self.on_tick_processed(self.current_index, len(self.tick_data), progress)
                        except Exception:
                            pass

                except Exception as e:
                    logger.error(f"Error streaming tick {self.current_index}: {e}")
                    self.error_count += 1
                    self.current_index += 1

            # Streaming complete
            if not self._stop_event.is_set():
                logger.info(f"Replay complete: {self.total_ticks_processed} ticks processed")
                if self.on_replay_complete:
                    try:
                        self.on_replay_complete()
                    except Exception as e:
                        logger.error(f"Error in replay complete callback: {e}")

        except Exception as e:
            logger.error(f"Streaming thread error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_streaming = False
            self.is_paused = False

    def pause(self) -> bool:
        """Pause streaming."""
        if not self.is_streaming:
            return False

        self._pause_event.clear()
        self.is_paused = True
        logger.info("Streaming paused")
        return True

    def resume(self) -> bool:
        """Resume streaming after pause."""
        if not self.is_streaming:
            return False

        self._pause_event.set()
        self.is_paused = False
        logger.info("Streaming resumed")
        return True

    def stop_streaming(self) -> None:
        """Stop streaming completely."""
        self._stop_event.set()
        self._pause_event.set()  # Release pause if paused
        self.is_streaming = False
        self.is_paused = False

        if self.streaming_thread and self.streaming_thread.is_alive():
            self.streaming_thread.join(timeout=2.0)

        logger.info("Streaming stopped")

    def set_playback_speed(self, speed: float) -> bool:
        """
        Set the playback speed.

        Args:
            speed: Playback speed multiplier (0.5, 1.0, 2.0, 5.0, 10.0)

        Returns:
            True if speed was set, False if invalid
        """
        if speed not in self.VALID_SPEEDS:
            logger.warning(f"Invalid speed {speed}. Valid: {self.VALID_SPEEDS}")
            return False

        self.playback_speed = speed
        logger.info(f"Playback speed set to {speed}x")
        return True

    def restart(self) -> bool:
        """Restart streaming from the beginning."""
        self.stop_streaming()
        self.current_index = 0
        return self.start_streaming()

    def add_symbol_subscription(self, symbol: str) -> None:
        """Add symbol to subscription list."""
        self.subscribed_symbols.add(symbol.upper())

    def remove_symbol_subscription(self, symbol: str) -> None:
        """Remove symbol from subscription list."""
        self.subscribed_symbols.discard(symbol.upper())

    def connect_stream(self) -> bool:
        """Connect and start streaming (DataLink interface)."""
        return self.start_streaming()

    def is_authenticated(self) -> bool:
        """Replay data link is always 'authenticated'."""
        return True

    def authenticate(self) -> bool:
        """Replay data link doesn't need authentication."""
        return True

    def load_historical_data(self, symbol: str, timeframe: str = "1m") -> List[TickData]:
        """
        MongoReplayDataLink streams its data; historical data is the stream itself.
        Return empty list as the data is provided through streaming.
        """
        return []

    def get_status(self) -> dict:
        """Get current replay status for UI."""
        return {
            'ticker': self.ticker,
            'date': self.date.strftime('%Y-%m-%d') if self.date else None,
            'is_streaming': self.is_streaming,
            'is_paused': self.is_paused,
            'playback_speed': self.playback_speed,
            'current_index': self.current_index,
            'total_ticks': len(self.tick_data),
            'progress': (self.current_index / len(self.tick_data) * 100) if self.tick_data else 0,
            'ticks_processed': self.total_ticks_processed,
            'errors': self.error_count
        }
