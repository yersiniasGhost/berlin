"""
Simple Schwab PIP Data Collector
Connects to Schwab streaming API and saves PIP data to individual text files per symbol.
Handles reconnection, token refresh, and robust file logging.
"""

import os
import sys
import json

import logging
import signal
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from threading import Event, Lock

from stock_analysis_ui.services.schwab_auth import SchwabAuthManager
from data_streamer.schwab_data_link import SchwabDataLink


class PIPDataCollector:
    """
    Collects PIP data from Schwab and saves to individual text files per symbol
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

        # Statistics
        self.stats: Dict[str, int] = {symbol: 0 for symbol in self.symbols}
        self.start_time: Optional[datetime] = None
        self.last_token_refresh: Optional[datetime] = None

        # Setup
        self._setup_directories()
        self._setup_logging()
        self._setup_signal_handlers()

    def _setup_directories(self) -> None:
        """Create output directory structure"""
        os.makedirs(self.output_dir, exist_ok=True)

        # Create subdirectories by date
        today = datetime.now().strftime("%Y-%m-%d")
        self.daily_dir = os.path.join(self.output_dir, today)
        os.makedirs(self.daily_dir, exist_ok=True)

        logging.info(f"Data will be saved to: {self.daily_dir}")

    def _setup_logging(self) -> None:
        """Configure logging"""
        log_file = os.path.join(self.output_dir, "collector.log")

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

        self.logger = logging.getLogger(__name__)

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown handlers"""

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def authenticate(self) -> bool:
        """Authenticate with Schwab API"""
        try:
            self.logger.info("Starting Schwab authentication...")
            self.auth_manager = SchwabAuthManager()

            if not self.auth_manager.authenticate():
                self.logger.error("Authentication failed")
                return False

            self.last_token_refresh = datetime.now()
            self.logger.info("Authentication successful")
            return True

        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            return False

    def _check_token_refresh(self) -> bool:
        """Check if token needs refreshing and refresh if needed"""
        if not self.last_token_refresh:
            return False

        # Refresh token every 6 hours to be safe (tokens last ~7 days)
        if datetime.now() - self.last_token_refresh > timedelta(hours=6):
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
        """Setup and connect to Schwab data stream"""
        try:
            self.data_link = SchwabDataLink()
            self.data_link.access_token = self.auth_manager.access_token
            self.data_link.refresh_token = self.auth_manager.refresh_token
            self.data_link.user_prefs = self.auth_manager.user_prefs

            if not self.data_link.connect_stream():
                self.logger.error("Failed to connect to Schwab streaming")
                return False

            # Register quote handler
            self.data_link.add_quote_handler(self._handle_pip_data)

            self.logger.info("Connected to Schwab streaming API")
            return True

        except Exception as e:
            self.logger.error(f"Data link setup error: {e}")
            return False

    def _handle_pip_data(self, pip_data: Dict) -> None:
        """Handle incoming PIP data and save to file"""
        try:
            symbol = pip_data.get('key')
            if not symbol or symbol not in self.symbols:
                return

            # Save ONLY the raw JSON data, one line per PIP
            data_line = f"{json.dumps(pip_data)}\n"

            # Save to file (thread-safe)
            with self.file_lock:
                filename = os.path.join(self.daily_dir, f"{symbol}_pip_data.txt")

                # Just append the JSON line - no headers
                with open(filename, 'a', encoding='utf-8') as f:
                    f.write(data_line)

                # Update statistics
                self.stats[symbol] += 1

        except Exception as e:
            self.logger.error(f"Error handling PIP data: {e}")

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
                    self.logger.error("Token refresh check failed, stopping collection")
                    break

                # Print statistics every 30 seconds
                self._print_statistics()

                # Wait 30 seconds or until shutdown
                if self.shutdown_event.wait(120):
                    break

        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            self.cleanup()

    def _print_statistics(self) -> None:
        """Print collection statistics"""
        if not self.start_time:
            return

        runtime = datetime.now() - self.start_time
        total_pips = sum(self.stats.values())

        self.logger.info(f"Runtime: {runtime}, Total PIPs: {total_pips}")
        for symbol, count in self.stats.items():
            if count > 0:
                self.logger.info(f"  {symbol}: {count} PIPs")

    def shutdown(self) -> None:
        """Graceful shutdown"""
        self.logger.info("Shutting down PIP data collector...")
        self.running = False
        self.shutdown_event.set()

    def cleanup(self) -> None:
        """Cleanup resources"""
        if self.data_link:
            try:
                self.data_link.disconnect()
                self.logger.info("Disconnected from Schwab streaming")
            except Exception as e:
                self.logger.error(f"Error disconnecting: {e}")

        # Final statistics
        self._print_statistics()
        self.logger.info("PIP data collector stopped")


def main():
    """Main entry point"""
    # Configuration
    SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "PLTR", "QBTS", "INTC", "SMCI", "COST",
               "F", "AMD", "PFE", "META", "WMT", "BABA", "CSCO", "CVX", "FSLR", "AMZN"]  # Modify as needed
    OUTPUT_DIR = "pip_data"  # Directory to save files

    print("Schwab PIP Data Collector")
    print(f"Symbols: {', '.join(SYMBOLS)}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    # Create collector and run
    collector = PIPDataCollector(SYMBOLS, OUTPUT_DIR)

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