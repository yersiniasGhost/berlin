"""
Pip Saver Service - Writes pip (tick) data to local files for all active cards
"""

import os
import csv
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from mlf_utils.log_manager import LogManager
from mlf_utils.timezone_utils import now_utc, isoformat_et
from mlf_utils.env_vars import EnvVars

logger = LogManager().get_logger("PipSaver")


class PipSaver:
    """
    Saves pip (tick) data to local CSV files for all active cards.
    Each card gets its own file with timestamped naming.
    """

    def __init__(self, output_dir: str = None, session_id: str = None):
        """
        Initialize PipSaver.

        Args:
            output_dir: Directory to save pip files. Uses PIP_DATA_PATH env var,
                        or defaults to 'pip_data' in current working directory.
            session_id: Optional session ID for file naming.
        """
        self.session_id = session_id
        self.is_enabled = False
        self._lock = threading.Lock()

        # Set up output directory (priority: arg > env var > default)
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            env_path = EnvVars().pip_data_path
            if env_path:
                self.output_dir = Path(env_path).expanduser()
            else:
                self.output_dir = Path.cwd() / "pip_data"

        # Track file handles and writers per card
        self._file_handles: Dict[str, Any] = {}
        self._csv_writers: Dict[str, csv.writer] = {}
        self._pip_counts: Dict[str, int] = {}

        # Session start time for file naming
        self._session_start: Optional[datetime] = None

        logger.info(f"PipSaver initialized. Output dir: {self.output_dir}")

    def enable(self) -> bool:
        """Enable pip saving. Creates output directory and prepares for writing."""
        with self._lock:
            if self.is_enabled:
                logger.info("PipSaver already enabled")
                return True

            try:
                # Create output directory if it doesn't exist
                self.output_dir.mkdir(parents=True, exist_ok=True)

                self._session_start = now_utc()
                self.is_enabled = True

                logger.info(f"PipSaver enabled. Saving to: {self.output_dir}")
                return True

            except Exception as e:
                logger.error(f"Failed to enable PipSaver: {e}")
                return False

    def disable(self) -> bool:
        """Disable pip saving. Closes all file handles."""
        with self._lock:
            if not self.is_enabled:
                logger.info("PipSaver already disabled")
                return True

            try:
                # Close all file handles
                self._close_all_files()

                self.is_enabled = False
                self._session_start = None

                logger.info("PipSaver disabled. All files closed.")
                return True

            except Exception as e:
                logger.error(f"Failed to disable PipSaver: {e}")
                return False

    def toggle(self) -> bool:
        """Toggle pip saving state. Returns new state."""
        if self.is_enabled:
            self.disable()
        else:
            self.enable()
        return self.is_enabled

    def save_pip(self, card_id: str, symbol: str, tick_data: Any,
                 indicators: Dict[str, float] = None, raw_indicators: Dict[str, float] = None,
                 bar_scores: Dict[str, float] = None) -> bool:
        """
        Save a pip (tick) to the card's file.

        Args:
            card_id: Card identifier
            symbol: Stock symbol
            tick_data: TickData object with OHLCV data
            indicators: Calculated indicator values
            raw_indicators: Raw indicator trigger values (0/1)
            bar_scores: Bar score values

        Returns:
            True if saved successfully, False otherwise
        """
        if not self.is_enabled:
            return False

        with self._lock:
            try:
                # Get or create file handle for this card
                writer = self._get_or_create_writer(card_id, symbol, indicators, raw_indicators, bar_scores)
                if not writer:
                    return False

                # Build row data
                row = self._build_row(tick_data, indicators, raw_indicators, bar_scores)
                writer.writerow(row)

                # Flush to ensure data is written
                if card_id in self._file_handles:
                    self._file_handles[card_id].flush()

                self._pip_counts[card_id] = self._pip_counts.get(card_id, 0) + 1

                return True

            except Exception as e:
                logger.error(f"Error saving pip for {card_id}: {e}")
                return False

    def _get_or_create_writer(self, card_id: str, symbol: str,
                               indicators: Dict[str, float] = None,
                               raw_indicators: Dict[str, float] = None,
                               bar_scores: Dict[str, float] = None) -> Optional[csv.writer]:
        """Get existing writer or create new one for card."""
        if card_id in self._csv_writers:
            return self._csv_writers[card_id]

        try:
            # Create filename with session timestamp
            timestamp_str = self._session_start.strftime("%Y%m%d_%H%M%S") if self._session_start else "unknown"
            filename = f"{symbol}_{card_id}_{timestamp_str}.csv"
            filepath = self.output_dir / filename

            # Open file and create writer
            file_handle = open(filepath, 'w', newline='')
            writer = csv.writer(file_handle)

            # Write header row
            header = self._build_header(indicators, raw_indicators, bar_scores)
            writer.writerow(header)

            # Store handles
            self._file_handles[card_id] = file_handle
            self._csv_writers[card_id] = writer
            self._pip_counts[card_id] = 0

            logger.info(f"Created pip file for {card_id}: {filepath}")
            return writer

        except Exception as e:
            logger.error(f"Error creating writer for {card_id}: {e}")
            return None

    def _build_header(self, indicators: Dict[str, float] = None,
                      raw_indicators: Dict[str, float] = None,
                      bar_scores: Dict[str, float] = None) -> list:
        """Build CSV header row."""
        header = [
            'timestamp',
            'open',
            'high',
            'low',
            'close',
            'volume'
        ]

        # Add indicator columns
        if indicators:
            for name in sorted(indicators.keys()):
                header.append(f"ind_{name}")

        # Add raw indicator columns
        if raw_indicators:
            for name in sorted(raw_indicators.keys()):
                header.append(f"raw_{name}")

        # Add bar score columns
        if bar_scores:
            for name in sorted(bar_scores.keys()):
                header.append(f"bar_{name}")

        return header

    def _build_row(self, tick_data: Any, indicators: Dict[str, float] = None,
                   raw_indicators: Dict[str, float] = None,
                   bar_scores: Dict[str, float] = None) -> list:
        """Build CSV data row."""
        row = [
            tick_data.timestamp.isoformat() if hasattr(tick_data, 'timestamp') else '',
            tick_data.open if hasattr(tick_data, 'open') else '',
            tick_data.high if hasattr(tick_data, 'high') else '',
            tick_data.low if hasattr(tick_data, 'low') else '',
            tick_data.close if hasattr(tick_data, 'close') else '',
            tick_data.volume if hasattr(tick_data, 'volume') else ''
        ]

        # Add indicator values
        if indicators:
            for name in sorted(indicators.keys()):
                value = indicators.get(name)
                row.append(value if value is not None else '')

        # Add raw indicator values
        if raw_indicators:
            for name in sorted(raw_indicators.keys()):
                value = raw_indicators.get(name)
                row.append(value if value is not None else '')

        # Add bar score values
        if bar_scores:
            for name in sorted(bar_scores.keys()):
                value = bar_scores.get(name)
                row.append(value if value is not None else '')

        return row

    def _close_all_files(self):
        """Close all open file handles."""
        for card_id, file_handle in self._file_handles.items():
            try:
                file_handle.close()
                count = self._pip_counts.get(card_id, 0)
                logger.info(f"Closed pip file for {card_id} ({count} pips saved)")
            except Exception as e:
                logger.error(f"Error closing file for {card_id}: {e}")

        self._file_handles.clear()
        self._csv_writers.clear()
        self._pip_counts.clear()

    def close_card_file(self, card_id: str):
        """Close file handle for a specific card (when card is removed)."""
        with self._lock:
            if card_id in self._file_handles:
                try:
                    self._file_handles[card_id].close()
                    count = self._pip_counts.get(card_id, 0)
                    logger.info(f"Closed pip file for removed card {card_id} ({count} pips saved)")
                except Exception as e:
                    logger.error(f"Error closing file for {card_id}: {e}")

                del self._file_handles[card_id]
                if card_id in self._csv_writers:
                    del self._csv_writers[card_id]
                if card_id in self._pip_counts:
                    del self._pip_counts[card_id]

    def get_status(self) -> Dict[str, Any]:
        """Get current pip saver status."""
        with self._lock:
            return {
                'enabled': self.is_enabled,
                'output_dir': str(self.output_dir),
                'active_cards': list(self._file_handles.keys()),
                'pip_counts': dict(self._pip_counts),
                'total_pips': sum(self._pip_counts.values()),
                'session_start': isoformat_et(self._session_start) if self._session_start else None
            }

    def cleanup(self):
        """Cleanup resources on shutdown."""
        self.disable()
        logger.info("PipSaver cleanup completed")
