"""
Improved Schwab PIP Data Collector with better error handling and recovery
"""

import os
import sys
import json
import logging
import signal
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from threading import Event, Lock, Timer
import websocket

from stock_analysis_ui.services.schwab_auth import SchwabAuthManager
from data_streamer.schwab_data_link import SchwabDataLink


class ImprovedPIPDataCollector:
    """
    Enhanced PIP data collector with better error handling and recovery
    """

    def __init__(self, symbols: List[str], output_dir: str = "pip_data"):
        self.symbols: List[str] = [s.upper() for s in symbols]
        self.output_dir: str = output_dir
        self.data_link: Optional[SchwabDataLink] = None
        self.auth_manager: Optional[SchwabAuthManager] = None

        # Control flags
        self.running: bool = False
        self.shutdown_event: Event = Event()
        self.file_lock: Lock = Lock()

        # Statistics and monitoring
        self.stats: Dict[str, int] = {symbol: 0 for symbol in self.symbols}
        self.start_time: Optional[datetime] = None
        self.last_token_refresh: Optional[datetime] = None
        self.last_data_received: Optional[datetime] = None
        self.connection_attempts: int = 0
        self.max_connection_attempts: int = 5

        # Heartbeat monitoring
        self.heartbeat_timer: Optional[Timer] = None
        self.heartbeat_interval: int = 300  # 5 minutes
        self.data_timeout: int = 600  # 10 minutes without data = problem

        # Setup - logging must come first!
        self._setup_logging()
        self._setup_directories()
        self._setup_signal_handlers()

    def _setup_directories(self) -> None:
        """Create output directory structure"""
        os.makedirs(self.output_dir, exist_ok=True)

        # Create subdirectories by date
        today = datetime.now().strftime("%Y-%m-%d")
        self.daily_dir = os.path.join(self.output_dir, today)
        os.makedirs(self.daily_dir, exist_ok=True)

        # Logger is now available since _setup_logging() was called first
        self.logger.info(f"Data will be saved to: {self.daily_dir}")

    def _setup_logging(self) -> None:
        """Configure logging with more detail"""
        log_file = os.path.join(self.output_dir, "collector.log")

        # Create logger
        self.logger = logging.getLogger("PIPCollector")
        self.logger.setLevel(logging.INFO)

        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown handlers"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _test_tokens_with_streaming(self) -> bool:
        """Test if tokens work by attempting a streaming connection"""
        try:
            self.logger.info("Testing tokens with streaming connection...")

            # Create a test data link
            test_link = SchwabDataLink()
            test_link.access_token = self.auth_manager.access_token
            test_link.refresh_token = self.auth_manager.refresh_token
            test_link.user_prefs = self.auth_manager.user_prefs

            # Try to connect
            if test_link.connect_stream():
                self.logger.info("Token test successful - streaming connection works")
                test_link.disconnect()
                return True
            else:
                self.logger.warning("Token test failed - streaming connection failed")
                return False

        except Exception as e:
            self.logger.warning(f"Token test failed with error: {e}")
            return False

    def authenticate(self) -> bool:
        """Authenticate with Schwab API with proper fallback logic"""
        try:
            self.logger.info("Starting Schwab authentication...")
            self.auth_manager = SchwabAuthManager()

            # Try to load existing tokens first
            if self.auth_manager.load_tokens():
                self.logger.info("Loaded existing tokens, testing validity...")

                # Test if tokens actually work by trying streaming connection
                if self._test_tokens_with_streaming():
                    self.last_token_refresh = datetime.now()
                    self.logger.info("Existing tokens are valid and working")
                    return True
                else:
                    self.logger.warning("Existing tokens failed streaming test")
            else:
                self.logger.info("No existing tokens found")

            # If we get here, existing tokens failed or don't exist
            self.logger.info("Performing fresh interactive authentication...")
            print("\n" + "="*60)
            print("SCHWAB AUTHENTICATION REQUIRED")
            print("Your existing tokens are invalid or expired.")
            print("Please complete the authentication process in your browser.")
            print("="*60 + "\n")

            if not self.auth_manager.authenticate():
                self.logger.error("Interactive authentication failed")
                return False

            self.last_token_refresh = datetime.now()
            self.logger.info("Fresh authentication successful")
            return True

        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            return False

    def _check_token_refresh(self) -> bool:
        """Check if token needs refreshing and refresh if needed"""
        if not self.last_token_refresh:
            return False

        # Refresh token every 4 hours to be extra safe
        if datetime.now() - self.last_token_refresh > timedelta(hours=4):
            self.logger.info("Refreshing authentication token...")

            try:
                if self.auth_manager.refresh_auth_token():
                    self.last_token_refresh = datetime.now()

                    # Update data link with new token
                    if self.data_link:
                        self.data_link.access_token = self.auth_manager.access_token
                        self.data_link.refresh_token = self.auth_manager.refresh_token

                    self.logger.info("Token refresh successful")
                    return True
                else:
                    self.logger.error("Token refresh failed")
                    return False

            except Exception as e:
                self.logger.error(f"Token refresh error: {e}")
                return False

        return True

    def _setup_data_link(self) -> bool:
        """Setup and connect to Schwab data stream with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Setting up data link (attempt {attempt + 1}/{max_retries})")

                self.data_link = SchwabDataLink()
                self.data_link.access_token = self.auth_manager.access_token
                self.data_link.refresh_token = self.auth_manager.refresh_token
                self.data_link.user_prefs = self.auth_manager.user_prefs

                if not self.data_link.connect_stream():
                    self.logger.error(f"Failed to connect to Schwab streaming (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        time.sleep(5 * (attempt + 1))  # Exponential backoff
                        continue
                    return False

                # Register quote handler
                self.data_link.add_quote_handler(self._handle_pip_data)

                self.logger.info("Connected to Schwab streaming API")
                return True

            except Exception as e:
                self.logger.error(f"Data link setup error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue

        return False

    def _handle_pip_data(self, pip_data: Dict) -> None:
        """Handle incoming PIP data and save to file"""
        try:
            symbol = pip_data.get('key')

            # Debug: Print what we received
            if symbol in self.symbols:
                timestamp = pip_data.get('38')
                price = pip_data.get('3')
                self.logger.debug(f"Received PIP for {symbol}: timestamp={timestamp}, price={price}")

            if not symbol or symbol not in self.symbols:
                return

            # Update last data received timestamp
            self.last_data_received = datetime.now()

            # Save ONLY the raw JSON data, one line per PIP
            data_line = f"{json.dumps(pip_data)}\n"

            # Save to file (thread-safe)
            with self.file_lock:
                filename = os.path.join(self.daily_dir, f"{symbol}_pip_data.txt")

                with open(filename, 'a', encoding='utf-8') as f:
                    f.write(data_line)

                # Update statistics
                self.stats[symbol] += 1

                # Log every 10th PIP for this symbol
                if self.stats[symbol] % 10 == 0:
                    self.logger.info(f"Saved {self.stats[symbol]} PIPs for {symbol}")

        except Exception as e:
            self.logger.error(f"Error handling PIP data: {e}")
            import traceback
            traceback.print_exc()

    def _start_heartbeat_monitor(self) -> None:
        """Start heartbeat monitoring with market hours awareness"""
        def check_connection():
            if not self.running:
                return

            now = datetime.now()
            is_market_hours = self._is_market_hours()

            # Check if we've received data recently
            if self.last_data_received:
                time_since_data = now - self.last_data_received

                # Different timeout behavior based on market hours
                if is_market_hours:
                    # During market hours (including after-hours), expect some data
                    timeout_threshold = self.data_timeout  # 10 minutes

                    # But be more lenient during after-hours
                    current_time = datetime.now()
                    hour = current_time.hour
                    if hour >= 16:  # After 4 PM, extend timeout for after-hours
                        timeout_threshold = self.data_timeout * 2  # 20 minutes

                    if time_since_data.total_seconds() > timeout_threshold:
                        self.logger.warning(f"No data received for {time_since_data} during market hours, attempting reconnection...")
                        self._attempt_reconnection()
                else:
                    # During non-market hours, be very lenient
                    extended_timeout = self.data_timeout * 6  # 60 minutes instead of 10
                    if time_since_data.total_seconds() > extended_timeout:
                        self.logger.info(f"No data for {time_since_data} (market closed - this is normal)")
                        # Only reconnect if connection is actually broken
                        if self.data_link and not self.data_link.is_connected:
                            self.logger.warning("WebSocket disconnected during off-hours, attempting reconnection...")
                            self._attempt_reconnection()

            # Always check WebSocket connection status
            if self.data_link and hasattr(self.data_link, 'ws'):
                if not self.data_link.is_connected:
                    self.logger.warning("WebSocket disconnected, attempting reconnection...")
                    self._attempt_reconnection()

            # Schedule next check
            if self.running:
                self.heartbeat_timer = Timer(self.heartbeat_interval, check_connection)
                self.heartbeat_timer.start()

        self.heartbeat_timer = Timer(self.heartbeat_interval, check_connection)
        self.heartbeat_timer.start()

    def _attempt_reconnection(self) -> bool:
        """Attempt to reconnect to the data stream with token refresh and fallback authentication"""
        if self.connection_attempts >= self.max_connection_attempts:
            self.logger.error("Max reconnection attempts reached, giving up")
            self.shutdown()
            return False

        self.connection_attempts += 1
        self.logger.info(f"Reconnection attempt {self.connection_attempts}/{self.max_connection_attempts}")

        try:
            # Disconnect existing connection
            if self.data_link:
                try:
                    self.data_link.disconnect()
                except:
                    pass

            # Wait a bit
            time.sleep(10)

            # ALWAYS try to refresh tokens before reconnecting
            self.logger.info("Refreshing tokens before reconnection attempt...")
            if not self.auth_manager.refresh_auth_token():
                self.logger.warning("Token refresh failed!")

                # If we're on attempt 3+, try full re-authentication
                if self.connection_attempts >= 3:
                    self.logger.info("Multiple failures - attempting full re-authentication...")
                    print("\n" + "="*60)
                    print("TOKEN REFRESH FAILED - INTERACTIVE LOGIN REQUIRED")
                    print("Please complete authentication in your browser.")
                    print("="*60 + "\n")

                    if self.auth_manager.authenticate():
                        self.logger.info("Re-authentication successful")
                        self.last_token_refresh = datetime.now()
                    else:
                        self.logger.error("Re-authentication failed")
                        return False
                else:
                    self.logger.info("Trying with existing tokens...")
            else:
                self.logger.info("Token refresh successful")
                self.last_token_refresh = datetime.now()

            # Attempt new connection
            if self._setup_data_link():
                # Re-subscribe to quotes
                if self.data_link.subscribe_quotes(self.symbols):
                    self.logger.info("Reconnection successful")
                    self.connection_attempts = 0  # Reset counter on success
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Reconnection error: {e}")
            return False

    def start_collection(self) -> bool:
        """Start collecting data"""
        try:
            if not self.authenticate():
                return False

            if not self._setup_data_link():
                return False

            # Subscribe to quotes for all symbols
            if not self.data_link.subscribe_quotes(self.symbols):
                self.logger.error("Failed to subscribe to quotes")
                return False

            self.running = True
            self.start_time = datetime.now()
            self.last_data_received = datetime.now()

            # Start heartbeat monitoring
            self._start_heartbeat_monitor()

            self.logger.info(f"Started collecting data for symbols: {', '.join(self.symbols)}")
            self.logger.info("Press Ctrl+C to stop collection gracefully")

            return True

        except Exception as e:
            self.logger.error(f"Error starting collection: {e}")
            return False

    def run(self) -> None:
        """Main collection loop"""
        if not self.start_collection():
            return

        try:
            # Main loop - just keep the process alive
            while self.running and not self.shutdown_event.is_set():
                # Check token refresh every 5 minutes
                if not self._check_token_refresh():
                    self.logger.error("Token refresh check failed, attempting reconnection...")
                    if not self._attempt_reconnection():
                        break

                # Print statistics every 2 minutes
                self._print_statistics()

                # Wait 2 minutes or until shutdown
                if self.shutdown_event.wait(120):
                    break

        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            self.cleanup()

    def _is_market_hours(self) -> bool:
        """Check if we're in market hours (including extended hours)"""
        now = datetime.now()

        # Check if weekday (Monday = 0, Sunday = 6)
        if now.weekday() >= 5:  # Saturday or Sunday
            return False

        # Check for major holidays (simplified)
        if self._is_market_holiday(now):
            return False

        # Market hours in ET (approximate - doesn't handle DST perfectly)
        # Pre-market: 4:00 AM - 9:30 AM
        # Regular: 9:30 AM - 4:00 PM
        # After-hours: 4:00 PM - 8:00 PM

        hour = now.hour
        minute = now.minute
        current_minutes = hour * 60 + minute

        # Extended market hours: 4:00 AM to 8:00 PM ET
        market_start = 4 * 60      # 4:00 AM
        market_end = 20 * 60       # 8:00 PM

        return market_start <= current_minutes <= market_end

    def _is_market_holiday(self, date: datetime) -> bool:
        """Simple check for major market holidays"""
        # This is a simplified version - you'd want a proper holiday calendar
        month, day = date.month, date.day

        # Major holidays when market is closed
        holidays = [
            (1, 1),   # New Year's Day
            (7, 4),   # Independence Day
            (12, 25), # Christmas Day
        ]

        return (month, day) in holidays

    def _get_market_status_description(self) -> str:
        """Get detailed market status"""
        now = datetime.now()

        if now.weekday() >= 5:
            return "WEEKEND"

        if self._is_market_holiday(now):
            return "HOLIDAY"

        hour = now.hour
        minute = now.minute
        current_minutes = hour * 60 + minute

        # Market periods
        pre_market_start = 4 * 60      # 4:00 AM
        regular_start = 9 * 60 + 30    # 9:30 AM
        regular_end = 16 * 60          # 4:00 PM
        after_hours_end = 20 * 60      # 8:00 PM

        if current_minutes < pre_market_start:
            return "CLOSED (Overnight)"
        elif current_minutes < regular_start:
            return "PRE-MARKET"
        elif current_minutes < regular_end:
            return "REGULAR HOURS"
        elif current_minutes < after_hours_end:
            return "AFTER-HOURS"
        else:
            return "CLOSED (Evening)"

    def _print_statistics(self) -> None:
        """Print collection statistics with more detail"""
        if not self.start_time:
            return

        runtime = datetime.now() - self.start_time
        total_pips = sum(self.stats.values())

        # Calculate recent activity
        time_since_last_data = "N/A"
        if self.last_data_received:
            time_since_last_data = str(datetime.now() - self.last_data_received)

        # Check market hours
        market_status = self._get_market_status_description()

        self.logger.info(f"Runtime: {runtime}, Total PIPs: {total_pips}, Last data: {time_since_last_data}, Market: {market_status}")

        # Log individual symbol stats
        active_symbols = [symbol for symbol, count in self.stats.items() if count > 0]
        if active_symbols:
            for symbol in active_symbols:
                self.logger.info(f"  {symbol}: {self.stats[symbol]} PIPs")
        else:
            if self._is_market_hours():
                self.logger.warning("  No PIPs received for any symbol during market hours!")
            else:
                self.logger.info(f"  No PIPs received ({market_status} - this is normal)")

        # Log connection status
        if self.data_link:
            self.logger.info(f"  Connection status: {self.data_link.is_connected}")

        # Weekend/holiday behavior notification
        if not self._is_market_hours():
            current_time = datetime.now()
            if current_time.weekday() >= 5:  # Weekend
                self.logger.info("  Note: Running during weekend - minimal data expected")
            elif self._is_market_holiday(current_time):
                self.logger.info("  Note: Market holiday - no data expected")

    def shutdown(self) -> None:
        """Graceful shutdown"""
        self.logger.info("Shutting down PIP data collector...")
        self.running = False
        self.shutdown_event.set()

        # Stop heartbeat timer
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()

    def cleanup(self) -> None:
        """Cleanup resources"""
        if self.data_link:
            try:
                self.data_link.disconnect()
                self.logger.info("Disconnected from Schwab streaming")
            except Exception as e:
                self.logger.error(f"Error disconnecting: {e}")

        # Stop heartbeat timer
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()

        # Final statistics
        self._print_statistics()
        self.logger.info("PIP data collector stopped")


def main():
    """Main entry point"""
    # Configuration
    SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "PLTR", "QBTS", "INTC", "SMCI", "COST",
               "F", "AMD", "PFE", "META", "WMT", "BABA", "CSCO", "CVX", "FSLR", "AMZN"]
    OUTPUT_DIR = "pip_data"

    print("Improved Schwab PIP Data Collector")
    print(f"Symbols: {', '.join(SYMBOLS)}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    # Create collector and run
    collector = ImprovedPIPDataCollector(SYMBOLS, OUTPUT_DIR)

    try:
        collector.run()
    except KeyboardInterrupt:
        print("\nReceived Ctrl+C, shutting down...")
        collector.shutdown()
    except Exception as e:
        print(f"Unexpected error: {e}")
        collector.shutdown()


if __name__ == "__main__":
    main()