import json
import threading
import time
import logging
from typing import Set, Dict, List, Optional
from datetime import datetime

from data_streamer.data_link import DataLink
from models.tick_data import TickData

logger = logging.getLogger('CSReplayDataLink')


class CSReplayDataLink(DataLink):
    """
    Clean CSReplayDataLink with minimal logging
    """

    def __init__(self, playback_speed: float = 1.0):
        super().__init__()
        self.playback_speed: float = playback_speed

        # State tracking
        self.is_streaming: bool = False
        self.streaming_thread: Optional[threading.Thread] = None
        self.subscribed_symbols: Set[str] = set()

        # File management
        self.symbol_files: Dict[str, str] = {}
        self.symbol_data: Dict[str, List[Dict]] = {}
        self.symbol_indices: Dict[str, int] = {}

        # Minimal tracking
        self.total_pips_processed: int = 0
        self.error_count: int = 0

    def add_symbol_file(self, symbol: str, file_path: str) -> bool:
        """Load symbol file with minimal logging"""
        try:
            pip_data = []
            error_count = 0

            with open(file_path, 'r') as file:
                for line in file:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        pip_entry = json.loads(line)

                        # Verify symbol match
                        entry_symbol = pip_entry.get('key')
                        if entry_symbol != symbol:
                            error_count += 1
                            continue

                        # Validate required fields
                        if not self._validate_pip_entry(pip_entry):
                            error_count += 1
                            continue

                        pip_data.append(pip_entry)

                    except json.JSONDecodeError:
                        error_count += 1
                        continue

            if not pip_data:
                return False

            # Sort by timestamp
            pip_data.sort(key=lambda x: x.get('38', 0))

            # Store the data
            self.symbol_files[symbol] = file_path
            self.symbol_data[symbol] = pip_data
            self.symbol_indices[symbol] = 0

            return True

        except Exception:
            return False

    def _validate_pip_entry(self, pip_entry: Dict) -> bool:
        """Validate PIP entry has required fields"""
        required_fields = ['key', '38', '3']  # symbol, timestamp, price

        for field in required_fields:
            if field not in pip_entry:
                return False

        try:
            timestamp = int(pip_entry['38'])
            price = float(pip_entry['3'])

            if timestamp <= 0 or price <= 0:
                return False

        except (ValueError, TypeError):
            return False

        return True

    def start_streaming(self) -> bool:
        """Start streaming with minimal logging"""
        if self.is_streaming:
            return True

        if not self.symbol_data:
            return False

        # Reset state
        self.is_streaming = True
        self.total_pips_processed = 0
        self.error_count = 0

        # Reset all indices
        for symbol in self.symbol_indices:
            self.symbol_indices[symbol] = 0

        # Start streaming thread
        self.streaming_thread = threading.Thread(target=self._stream_data, daemon=True)
        self.streaming_thread.start()

        return True

    def _stream_data(self) -> None:
        """Clean streaming with no debug output"""
        try:
            # Build merged timeline
            all_pips = []
            for symbol, pip_data in self.symbol_data.items():
                for pip_entry in pip_data:
                    timestamp = pip_entry.get('38', 0)
                    all_pips.append({
                        'symbol': symbol,
                        'timestamp': timestamp,
                        'data': pip_entry
                    })

            # Sort chronologically
            all_pips.sort(key=lambda x: x['timestamp'])

            if not all_pips:
                return

            # Stream the data
            last_timestamp = None

            for pip_item in all_pips:
                if not self.is_streaming:
                    break

                try:
                    symbol = pip_item['symbol']
                    pip_entry = pip_item['data']
                    current_timestamp = pip_item['timestamp']

                    # Only process subscribed symbols
                    if symbol not in self.subscribed_symbols:
                        continue

                    # Calculate and apply delay
                    if last_timestamp is not None and current_timestamp > last_timestamp:
                        delay_ms = current_timestamp - last_timestamp
                        delay_seconds = (delay_ms / 1000.0) / self.playback_speed
                        delay_seconds = min(delay_seconds, 5.0)  # Cap at 5 seconds

                        if delay_seconds > 0:
                            time.sleep(delay_seconds)

                    last_timestamp = current_timestamp

                    # Convert to TickData
                    tick_data = self._pip_to_tick_data(pip_entry)
                    if tick_data is None:
                        self.error_count += 1
                        continue

                    # Update tracking
                    self.total_pips_processed += 1

                    # Send to DataStreamers
                    if symbol in self.data_streamers:
                        for data_streamer in self.data_streamers[symbol]:
                            try:
                                data_streamer.process_tick(tick_data)
                            except Exception:
                                self.error_count += 1

                except Exception:
                    self.error_count += 1
                    continue

        except Exception:
            pass
        finally:
            self.is_streaming = False

    def _pip_to_tick_data(self, pip_data: Dict) -> Optional[TickData]:
        """Clean PIP to TickData conversion"""
        try:
            # Get required fields
            symbol = pip_data.get('key')
            timestamp_ms = pip_data.get('38')
            close_price = pip_data.get('3')

            # Validation
            if not symbol or not timestamp_ms or not close_price:
                return None

            # Convert types
            timestamp_ms = int(timestamp_ms)
            price = float(close_price)

            # Validate values
            if timestamp_ms <= 0 or price <= 0:
                return None

            # Convert timestamp
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000)

            # Sanity check timestamp
            if timestamp.year < 2000 or timestamp.year > 2030:
                return None

            volume = int(pip_data.get('8', 0))

            # Create TickData
            return TickData(
                symbol=symbol,
                timestamp=timestamp,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
                time_increment="PIP"
            )

        except Exception:
            return None

    def add_symbol_subscription(self, symbol: str) -> None:
        """Add symbol subscription"""
        self.subscribed_symbols.add(symbol)

    def stop_streaming(self) -> None:
        """Stop streaming"""
        self.is_streaming = False

        if self.streaming_thread and self.streaming_thread.is_alive():
            self.streaming_thread.join(timeout=2.0)

    def load_historical_data(self, symbol: str, timeframe: str = "1m") -> List[TickData]:
        """
        CSReplayDataLink doesn't provide separate historical data since the replay files
        contain the "live" data we're streaming. Return empty list.
        """
        return []

    def connect_stream(self) -> bool:
        """Connect and start streaming"""
        return self.start_streaming()

    def is_authenticated(self) -> bool:
        """Replay data link is always 'authenticated'"""
        return True

    def authenticate(self) -> bool:
        """Replay data link doesn't need authentication"""
        return True