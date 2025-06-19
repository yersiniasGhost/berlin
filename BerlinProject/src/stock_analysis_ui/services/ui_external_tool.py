"""
Clean UIExternalTool with minimal logging
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
    Clean UI External Tool - sends data to browser via WebSocket
    """

    def __init__(self, socketio: SocketIO):
        self.socketio: SocketIO = socketio
        self.last_meaningful_data: Dict[str, Dict] = {}

        # Rate limiting
        self.last_update_time: Dict[str, float] = defaultdict(float)
        self.min_update_interval: float = 0.05  # 50ms minimum between updates
        self.update_counter: Dict[str, int] = defaultdict(int)
        self.failed_emit_counter: Dict[str, int] = defaultdict(int)

        # WebSocket health monitoring
        self.last_successful_emit: float = time.time()
        self.total_emits: int = 0
        self.failed_emits: int = 0
        self.max_failed_emits: int = 10

    def process_tick(self, card_id: str, symbol: str, tick_data: TickData,
                     indicators: Dict[str, float], raw_indicators: Dict[str, float],
                     bar_scores: Dict[str, float], portfolio_metrics: Optional[Dict[str, Any]] = None) -> None:
        """
        Process real-time tick data and send updates to browser
        """
        try:
            current_time = time.time()

            # Rate limiting: Skip update if too recent
            if current_time - self.last_update_time[card_id] < self.min_update_interval:
                return

            self.last_update_time[card_id] = current_time
            self.update_counter[card_id] += 1

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
                'update_count': self.update_counter[card_id]
            }

            # Add portfolio metrics if available
            if portfolio_metrics:
                update_data['portfolio'] = portfolio_metrics

            # WebSocket emit with error handling
            emit_success = self._safe_emit('card_update', update_data, card_id)

            # Monitor WebSocket health
            if emit_success:
                self.last_successful_emit = current_time
                self.total_emits += 1
                # Reset failed counter on success
                if self.failed_emit_counter[card_id] > 0:
                    self.failed_emit_counter[card_id] = 0
            else:
                self.failed_emits += 1
                self.failed_emit_counter[card_id] += 1

                # If too many failures, reset counter to prevent spam
                if self.failed_emit_counter[card_id] >= self.max_failed_emits:
                    self.failed_emit_counter[card_id] = 0

        except Exception:
            pass

    def _safe_emit(self, event: str, data: Dict, card_id: str) -> bool:
        """
        Safely emit WebSocket data with error handling
        """
        try:
            self.socketio.emit(event, data)
            return True
        except Exception:
            return False

    def indicator_vector(self, indicators: Dict[str, float], tick: TickData, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        """Legacy indicator vector method - redirect to process_tick"""
        pass

    def feature_vector(self, fv: np.array, tick: TickData) -> None:
        """Feature vector processing (not used in current architecture)"""
        pass

    def present_sample(self, sample: dict, index: int):
        """Sample presentation (not used in current architecture)"""
        pass

    def reset_next_sample(self):
        """Reset for next sample (not used in current architecture)"""
        pass

    def _format_timestamp(self, timestamp) -> str:
        """Format timestamp for JSON serialization"""
        if isinstance(timestamp, datetime):
            return timestamp.isoformat()
        return str(timestamp)

    def clear_meaningful_data(self, card_id: str = None) -> None:
        """Clear stored meaningful data and reset counters"""
        if card_id:
            self.last_meaningful_data.pop(card_id, None)
            self.update_counter.pop(card_id, 0)
            self.failed_emit_counter.pop(card_id, 0)
            self.last_update_time.pop(card_id, 0)
        else:
            self.last_meaningful_data.clear()
            self.update_counter.clear()
            self.failed_emit_counter.clear()
            self.last_update_time.clear()

    def get_health_status(self) -> Dict[str, Any]:
        """Get WebSocket health status for debugging"""
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