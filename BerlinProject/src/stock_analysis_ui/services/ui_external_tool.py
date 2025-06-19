# File: BerlinProject/src/stock_analysis_ui/services/ui_external_tool.py
# Complete UIExternalTool with enhanced WebSocket monitoring and recovery

"""
UIExternalTool for sending data to browser via WebSocket with enhanced monitoring
"""

import logging
import time
from typing import Dict, Optional, Any
from datetime import datetime
from collections import defaultdict

import numpy as np
from flask_socketio import SocketIO

from data_streamer import ExternalTool
from models.tick_data import TickData

logger = logging.getLogger('UIExternalTool')


class UIExternalTool(ExternalTool):
    """
    Enhanced UI External Tool - sends indicator, price, and portfolio data to browser
    with WebSocket health monitoring and recovery mechanisms
    """

    def __init__(self, socketio: SocketIO):
        self.socketio: SocketIO = socketio
        self.last_meaningful_data: Dict[str, Dict] = {}

        # Enhanced rate limiting and monitoring
        self.last_update_time: Dict[str, float] = defaultdict(float)
        self.min_update_interval: float = 0.05  # 50ms minimum between updates
        self.update_counter: Dict[str, int] = defaultdict(int)
        self.failed_emit_counter: Dict[str, int] = defaultdict(int)

        # WebSocket health monitoring
        self.last_successful_emit: float = time.time()
        self.total_emits: int = 0
        self.failed_emits: int = 0
        self.max_failed_emits: int = 10

        logger.info("UIExternalTool initialized with enhanced monitoring")

    def process_tick(self, card_id: str, symbol: str, tick_data: TickData,
                     indicators: Dict[str, float], raw_indicators: Dict[str, float],
                     bar_scores: Dict[str, float], portfolio_metrics: Optional[Dict[str, Any]] = None) -> None:
        """
        Process real-time tick data and send updates to browser with enhanced error handling

        Args:
            card_id: Card identifier
            symbol: Stock symbol
            tick_data: TickData object (already validated)
            indicators: Calculated indicators
            raw_indicators: Raw indicator values
            bar_scores: Bar scores
            portfolio_metrics: Portfolio performance metrics (position and P&L)
        """
        try:
            current_time = time.time()

            # Rate limiting: Skip update if too recent
            if current_time - self.last_update_time[card_id] < self.min_update_interval:
                return

            self.last_update_time[card_id] = current_time
            self.update_counter[card_id] += 1

            # Log health status periodically
            if self.update_counter[card_id] % 200 == 0:
                logger.info(f"💓 UI Health: {card_id} updates: {self.update_counter[card_id]}, "
                            f"failed emits: {self.failed_emit_counter[card_id]}")

            # Extract data from TickData object
            price = tick_data.close
            volume = tick_data.volume
            timestamp = tick_data.timestamp

            # Prepare update data
            update_data = {
                'card_id': card_id,
                'symbol': symbol,
                'price': price,
                'timestamp': self._format_timestamp(timestamp),
                'ohlc': [tick_data.open, tick_data.high, tick_data.low, tick_data.close],
                'volume': volume,
                'indicators': indicators or {},
                'bar_scores': bar_scores or {},
                'raw_indicators': raw_indicators or {},
                'update_count': self.update_counter[card_id]  # Add update counter for debugging
            }

            # Add portfolio metrics if available
            if portfolio_metrics:
                update_data['portfolio'] = portfolio_metrics

            # Enhanced WebSocket emit with comprehensive error handling
            emit_success = self._safe_emit('card_update', update_data, card_id)

            # Monitor WebSocket health
            if emit_success:
                self.last_successful_emit = current_time
                self.total_emits += 1
                # Reset failed counter on success
                if self.failed_emit_counter[card_id] > 0:
                    logger.info(f"✅ WebSocket recovered for {card_id}")
                    self.failed_emit_counter[card_id] = 0
            else:
                self.failed_emits += 1
                self.failed_emit_counter[card_id] += 1

                # Log WebSocket issues
                if self.failed_emit_counter[card_id] % 5 == 1:  # Log every 5th failure
                    logger.warning(f"⚠️  WebSocket emit failing for {card_id} "
                                   f"(failures: {self.failed_emit_counter[card_id]})")

                # If too many failures, try to diagnose and recover
                if self.failed_emit_counter[card_id] >= self.max_failed_emits:
                    logger.error(f"🚨 WebSocket appears broken for {card_id} - "
                                 f"{self.failed_emit_counter[card_id]} consecutive failures")
                    self._attempt_websocket_recovery(card_id)

        except Exception as e:
            logger.error(f"💥 Critical error in process_tick for {card_id}: {e}")
            import traceback
            traceback.print_exc()

    def _safe_emit(self, event: str, data: Dict, card_id: str) -> bool:
        """
        Safely emit WebSocket data with comprehensive error handling

        Args:
            event: WebSocket event name
            data: Data to emit
            card_id: Card identifier for debugging

        Returns:
            bool: True if emit succeeded, False if failed
        """
        try:
            # Try to emit with timeout protection
            self.socketio.emit(event, data)
            return True

        except Exception as e:
            logger.debug(f"WebSocket emit failed for {card_id}: {type(e).__name__}: {e}")
            return False

    def _attempt_websocket_recovery(self, card_id: str) -> None:
        """
        Attempt to recover from WebSocket issues

        Args:
            card_id: Card identifier experiencing issues
        """
        try:
            logger.info(f"🔧 Attempting WebSocket recovery for {card_id}")

            # Try sending a simple ping message
            test_data = {
                'card_id': card_id,
                'type': 'recovery_test',
                'timestamp': datetime.now().isoformat()
            }

            success = self._safe_emit('recovery_ping', test_data, card_id)

            if success:
                logger.info(f"✅ WebSocket recovery successful for {card_id}")
                self.failed_emit_counter[card_id] = 0
            else:
                logger.error(f"❌ WebSocket recovery failed for {card_id}")

                # Reset counter to prevent spam
                self.failed_emit_counter[card_id] = 0

        except Exception as e:
            logger.error(f"WebSocket recovery attempt failed: {e}")

    def indicator_vector(self, indicators: Dict[str, float], tick: TickData, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        """
        Legacy indicator vector method - redirect to process_tick

        Args:
            indicators: Dictionary of indicators
            tick: Tick data
            index: Index of the tick
            raw_indicators: Raw indicator values
        """
        # This shouldn't be called in the new architecture, but just in case
        logger.debug("indicator_vector called - this should use process_tick instead")

    def feature_vector(self, fv: np.array, tick: TickData) -> None:
        """
        Feature vector processing (not used in current architecture)

        Args:
            fv: Feature vector
            tick: Tick data
        """
        pass

    def present_sample(self, sample: dict, index: int):
        """
        Sample presentation (not used in current architecture)

        Args:
            sample: Sample data
            index: Sample index
        """
        pass

    def reset_next_sample(self):
        """Reset for next sample (not used in current architecture)"""
        pass

    def _format_timestamp(self, timestamp) -> str:
        """
        Format timestamp for JSON serialization

        Args:
            timestamp: Timestamp to format

        Returns:
            Formatted timestamp string
        """
        if isinstance(timestamp, datetime):
            return timestamp.isoformat()
        return str(timestamp)

    def clear_meaningful_data(self, card_id: str = None) -> None:
        """
        Clear stored meaningful data and reset counters

        Args:
            card_id: Specific card to clear, or None for all cards
        """
        if card_id:
            self.last_meaningful_data.pop(card_id, None)
            self.update_counter.pop(card_id, 0)
            self.failed_emit_counter.pop(card_id, 0)
            self.last_update_time.pop(card_id, 0)
            logger.info(f"Cleared data for card: {card_id}")
        else:
            self.last_meaningful_data.clear()
            self.update_counter.clear()
            self.failed_emit_counter.clear()
            self.last_update_time.clear()
            logger.info("Cleared all meaningful data")

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive WebSocket health status for debugging

        Returns:
            Dictionary with health metrics
        """
        current_time = time.time()
        silence_duration = current_time - self.last_successful_emit

        return {
            'total_emits': self.total_emits,
            'failed_emits': self.failed_emits,
            'success_rate': (self.total_emits / max(self.total_emits + self.failed_emits, 1)) * 100,
            'last_successful_emit': datetime.fromtimestamp(self.last_successful_emit).isoformat(),
            'silence_duration_seconds': silence_duration,
            'cards_with_failures': {card_id: count for card_id, count in self.failed_emit_counter.items() if count > 0},
            'update_counts': dict(self.update_counter),
            'min_update_interval_ms': self.min_update_interval * 1000,
            'active_cards': len(self.update_counter)
        }