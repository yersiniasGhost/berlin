# Enhanced CSReplayDataLink with debugging and recovery mechanisms

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
    Enhanced CSReplayDataLink with debugging and recovery for random stopping issues
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

        # Enhanced debugging and monitoring
        self.total_pips_processed: int = 0
        self.last_pip_time: Optional[datetime] = None
        self.last_activity_time: float = time.time()
        self.streaming_start_time: Optional[float] = None
        self.error_count: int = 0
        self.max_errors: int = 50  # Stop after too many errors

        # Health monitoring
        self.health_check_interval: float = 10.0  # Check every 10 seconds
        self.max_silence_duration: float = 30.0  # Alert if no activity for 30 seconds

        logger.info(f"Enhanced CSReplayDataLink initialized with speed: {playback_speed}x")

    def add_symbol_file(self, symbol: str, file_path: str) -> bool:
        """Enhanced file loading with better error handling"""
        try:
            pip_data = []
            line_count = 0
            error_count = 0

            logger.info(f"Loading file for {symbol}: {file_path}")

            with open(file_path, 'r') as file:
                for line_num, line in enumerate(file, 1):
                    line_count += 1
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        pip_entry = json.loads(line)

                        # Verify symbol match
                        entry_symbol = pip_entry.get('key')
                        if entry_symbol != symbol:
                            error_count += 1
                            if error_count <= 5:  # Only log first 5 mismatches
                                logger.warning(f"Line {line_num}: Expected {symbol}, found {entry_symbol}")
                            continue

                        # Validate required fields
                        if not self._validate_pip_entry(pip_entry, line_num):
                            error_count += 1
                            continue

                        pip_data.append(pip_entry)

                    except json.JSONDecodeError as e:
                        error_count += 1
                        if error_count <= 5:  # Only log first 5 JSON errors
                            logger.warning(f"Invalid JSON in {file_path} line {line_num}: {e}")
                        continue

            if not pip_data:
                logger.error(f"No valid PIP data found for {symbol} in {file_path}")
                return False

            # Sort by timestamp to ensure chronological order within symbol
            pip_data.sort(key=lambda x: x.get('38', 0))

            # Store the data
            self.symbol_files[symbol] = file_path
            self.symbol_data[symbol] = pip_data
            self.symbol_indices[symbol] = 0

            logger.info(f"✅ Loaded {len(pip_data)} valid PIPs for {symbol} from {line_count} lines "
                        f"(errors: {error_count})")

            # Log timestamp range
            if pip_data:
                first_ts = pip_data[0].get('38', 0)
                last_ts = pip_data[-1].get('38', 0)
                first_time = datetime.fromtimestamp(first_ts / 1000) if first_ts else "Unknown"
                last_time = datetime.fromtimestamp(last_ts / 1000) if last_ts else "Unknown"
                logger.info(f"  Time range: {first_time} to {last_time}")

            return True

        except Exception as e:
            logger.error(f"Critical error loading {file_path}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _validate_pip_entry(self, pip_entry: Dict, line_num: int) -> bool:
        """Validate PIP entry has required fields"""
        required_fields = ['key', '38', '3']  # symbol, timestamp, price
        for field in required_fields:
            if field not in pip_entry:
                logger.warning(f"Line {line_num}: Missing required field '{field}'")
                return False

        # Validate timestamp and price
        try:
            timestamp = int(pip_entry['38'])
            price = float(pip_entry['3'])

            if timestamp <= 0:
                logger.warning(f"Line {line_num}: Invalid timestamp {timestamp}")
                return False

            if price <= 0:
                logger.warning(f"Line {line_num}: Invalid price {price}")
                return False

        except (ValueError, TypeError):
            logger.warning(f"Line {line_num}: Invalid timestamp or price format")
            return False

        return True

    def start_streaming(self) -> bool:
        """Enhanced streaming startup - allow starting without subscriptions"""
        if self.is_streaming:
            logger.warning("Already streaming")
            return True

        if not self.symbol_data:
            logger.error("No symbol files loaded")
            return False

        logger.info(f"🎬 STARTING STREAMING - Subscribed symbols: {list(self.subscribed_symbols)}")
        logger.info(f"🎬 Available symbols in data: {list(self.symbol_data.keys())}")

        # FIXED: Allow starting even without subscriptions (they'll be added later)
        if not self.subscribed_symbols:
            logger.info("⏳ No subscriptions yet - streaming will begin when symbols are subscribed")
        else:
            # Check if we have any subscribed symbols with data
            subscribed_with_data = []
            for symbol in self.subscribed_symbols:
                if symbol in self.symbol_data:
                    subscribed_with_data.append(symbol)
                    logger.info(f"✅ {symbol}: {len(self.symbol_data[symbol])} PIPs ready")
                else:
                    logger.warning(f"❌ {symbol}: Subscribed but no data loaded!")

            if not subscribed_with_data:
                logger.warning("⚠️  Subscribed symbols have no data - will process when data available")

        # Reset counters
        self.is_streaming = True
        self.total_pips_processed = 0
        self.error_count = 0
        self.streaming_start_time = time.time()
        self.last_activity_time = time.time()

        # Reset all indices
        for symbol in self.symbol_indices:
            self.symbol_indices[symbol] = 0

        logger.info(f"🚀 Starting background threads...")

        # Start monitoring thread
        self.monitoring_thread = threading.Thread(target=self._health_monitor, daemon=True)
        self.monitoring_thread.start()

        # Start streaming thread
        self.streaming_thread = threading.Thread(target=self._enhanced_stream_data, daemon=True)
        self.streaming_thread.start()

        logger.info(f"🚀 Threads started - will process PIPs when symbols are subscribed")

        return True

    def _health_monitor(self) -> None:
        """Monitor streaming health and detect issues"""
        while self.is_streaming:
            try:
                time.sleep(self.health_check_interval)

                current_time = time.time()
                silence_duration = current_time - self.last_activity_time

                if silence_duration > self.max_silence_duration:
                    logger.warning(f"⚠️  No streaming activity for {silence_duration:.1f} seconds!")
                    logger.warning(f"   Processed PIPs: {self.total_pips_processed}")
                    logger.warning(f"   Error count: {self.error_count}")
                    logger.warning(
                        f"   Thread alive: {self.streaming_thread.is_alive() if self.streaming_thread else 'None'}")

                # Log periodic status
                if self.total_pips_processed > 0 and self.total_pips_processed % 1000 == 0:
                    elapsed = current_time - (self.streaming_start_time or current_time)
                    rate = self.total_pips_processed / elapsed if elapsed > 0 else 0
                    logger.info(f"📊 Streaming status: {self.total_pips_processed} PIPs processed, "
                                f"{rate:.1f} PIPs/sec, {self.error_count} errors")

            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    def _enhanced_stream_data(self) -> None:
        """Enhanced streaming with comprehensive error handling and logging"""
        logger.info(f"🎬 Starting enhanced data stream")

        try:
            # Build merged timeline
            all_pips = []
            for symbol, pip_data in self.symbol_data.items():
                logger.info(f"Adding {len(pip_data)} PIPs for {symbol}")
                for pip_entry in pip_data:
                    timestamp = pip_entry.get('38', 0)
                    all_pips.append({
                        'symbol': symbol,
                        'timestamp': timestamp,
                        'data': pip_entry
                    })

            # Sort chronologically
            all_pips.sort(key=lambda x: x['timestamp'])
            logger.info(f"📈 Created timeline with {len(all_pips)} total PIPs")

            if not all_pips:
                logger.error("No PIPs to stream!")
                return

            # Log timeline info
            first_ts = all_pips[0]['timestamp']
            last_ts = all_pips[-1]['timestamp']
            first_time = datetime.fromtimestamp(first_ts / 1000)
            last_time = datetime.fromtimestamp(last_ts / 1000)
            logger.info(f"⏰ Timeline: {first_time} to {last_time}")

            # Stream the data
            last_timestamp = None
            processed_count = 0
            skipped_count = 0

            for pip_item in all_pips:
                if not self.is_streaming:
                    logger.info("🛑 Streaming stopped by request")
                    break

                try:
                    symbol = pip_item['symbol']
                    pip_entry = pip_item['data']
                    current_timestamp = pip_item['timestamp']

                    # Update activity time
                    self.last_activity_time = time.time()

                    # Only process subscribed symbols
                    if symbol not in self.subscribed_symbols:
                        skipped_count += 1
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
                    processed_count += 1
                    self.total_pips_processed += 1

                    # Log milestone PIPs
                    if processed_count % 100 == 0:
                        pip_time = datetime.fromtimestamp(current_timestamp / 1000)
                        logger.debug(f"📍 Processed {processed_count} PIPs, current time: {pip_time}")

                    # Send to DataStreamers
                    if symbol in self.data_streamers:
                        for data_streamer in self.data_streamers[symbol]:
                            try:
                                data_streamer.process_tick(tick_data)
                            except Exception as ds_error:
                                self.error_count += 1
                                logger.error(f"DataStreamer error for {symbol}: {ds_error}")

                                # Stop if too many errors
                                if self.error_count > self.max_errors:
                                    logger.error(f"🚨 Too many errors ({self.error_count}), stopping stream")
                                    self.is_streaming = False
                                    break

                except Exception as pip_error:
                    self.error_count += 1
                    logger.error(f"Error processing PIP {processed_count}: {pip_error}")

                    # Stop if too many errors
                    if self.error_count > self.max_errors:
                        logger.error(f"🚨 Too many errors ({self.error_count}), stopping stream")
                        break

                    continue

            # Final statistics
            elapsed = time.time() - (self.streaming_start_time or time.time())
            logger.info(f"✅ Streaming completed!")
            logger.info(f"   Processed: {processed_count} PIPs")
            logger.info(f"   Skipped: {skipped_count} PIPs (unsubscribed symbols)")
            logger.info(f"   Errors: {self.error_count}")
            logger.info(f"   Duration: {elapsed:.1f} seconds")
            logger.info(f"   Rate: {processed_count / elapsed:.1f} PIPs/sec")

        except Exception as e:
            logger.error(f"🚨 Critical error in stream_data: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_streaming = False

    def _pip_to_tick_data(self, pip_data: Dict) -> Optional[TickData]:
        """Enhanced PIP to TickData conversion with better error handling"""
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

        except Exception as e:
            logger.debug(f"Error converting PIP: {e}")
            return None

    def add_symbol_subscription(self, symbol: str) -> None:
        """Add symbol subscription with logging"""
        self.subscribed_symbols.add(symbol)
        logger.info(f"✅ Subscribed to {symbol} (total subscriptions: {len(self.subscribed_symbols)})")

    def stop_streaming(self) -> None:
        """Enhanced stop with cleanup"""
        logger.info("🛑 Stopping streaming...")
        self.is_streaming = False

        if self.streaming_thread and self.streaming_thread.is_alive():
            self.streaming_thread.join(timeout=2.0)

        if hasattr(self, 'monitoring_thread') and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=1.0)

        logger.info(
            f"✅ Streaming stopped. Final stats: {self.total_pips_processed} PIPs processed, {self.error_count} errors")

    def get_debug_info(self) -> Dict:
        """Get comprehensive debug information"""
        return {
            'is_streaming': self.is_streaming,
            'total_pips_processed': self.total_pips_processed,
            'error_count': self.error_count,
            'subscribed_symbols': list(self.subscribed_symbols),
            'loaded_symbols': list(self.symbol_data.keys()),
            'symbol_data_counts': {s: len(data) for s, data in self.symbol_data.items()},
            'last_activity': datetime.fromtimestamp(
                self.last_activity_time).isoformat() if self.last_activity_time else None,
            'streaming_duration': time.time() - self.streaming_start_time if self.streaming_start_time else 0,
            'thread_alive': self.streaming_thread.is_alive() if self.streaming_thread else False
        }

    def load_historical_data(self, symbol: str, timeframe: str = "1m") -> List[TickData]:
        """
        CSReplayDataLink doesn't provide separate historical data since the replay files
        contain the "live" data we're streaming. Return empty list instead of None.

        Args:
            symbol: Stock symbol
            timeframe: Timeframe (ignored for replay)

        Returns:
            Empty list (no historical data for replay mode)
        """
        logger.debug(f"CSReplayDataLink: No separate historical data for {symbol} {timeframe} - using replay stream")
        return []  # Return empty list instead of None

    def connect_stream(self) -> bool:
        """Connect and start streaming (matches SchwabDataLink interface)"""
        logger.info("🔗 CSReplayDataLink.connect_stream() called")
        return self.start_streaming()

    def is_authenticated(self) -> bool:
        """Replay data link is always 'authenticated'"""
        return True

    def authenticate(self) -> bool:
        """Replay data link doesn't need authentication"""
        return True