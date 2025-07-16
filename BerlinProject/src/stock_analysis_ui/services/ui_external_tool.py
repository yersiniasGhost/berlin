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


# In ui_external_tool.py, modify the UIExternalTool class

class UIExternalTool(ExternalTool):
    """
    Clean UI External Tool - sends data to browser via WebSocket
    """

    def __init__(self, socketio: SocketIO, app_service=None):  # ADD app_service parameter
        self.socketio: SocketIO = socketio
        self.app_service = app_service  # Store reference to app_service
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

    # Update your UIExternalTool to send session-specific updates
    # Add this method to your UIExternalTool class in ui_external_tool.py

    def emit_to_session(self, event_name, data, session_id=None):
        """Emit WebSocket event to specific session room"""
        try:
            if session_id:
                # Send to specific session room
                self.socketio.emit(event_name, data, room=f"session_{session_id}")
            else:
                # Fallback to broadcast (for replay mode or legacy)
                self.socketio.emit(event_name, data)

            self.total_emits += 1
            self.last_successful_emit = time.time()
            return True

        except Exception as e:
            self.failed_emits += 1
            logger.error(f"Failed to emit {event_name} to session {session_id}: {e}")
            return False

    def get_session_id_from_app_service(self):
        """Get session ID from the app_service if it has one"""
        if hasattr(self.app_service, 'session_id'):
            return self.app_service.session_id
        return None

    # Update the process_tick method to use session-based emit
    def process_tick(self, card_id: str, symbol: str, tick_data: TickData,
                     indicators: Dict[str, float], raw_indicators: Dict[str, float],
                     bar_scores: Dict[str, float], portfolio_metrics: Optional[Dict[str, Any]] = None) -> None:
        """
        Process real-time tick data and send updates to browser (session-specific)
        """
        try:
            current_time = time.time()

            # Rate limiting check
            if current_time - self.last_update_time[card_id] < self.min_update_interval:
                return

            self.last_update_time[card_id] = current_time
            self.update_counter[card_id] += 1

            # Build update data
            update_data = {
                'card_id': card_id,
                'symbol': symbol,
                'price': tick_data.close,
                'timestamp': tick_data.timestamp.isoformat(),
                'ohlc': [tick_data.open, tick_data.high, tick_data.low, tick_data.close],
                'volume': tick_data.volume,
                'indicators': indicators,
                'bar_scores': bar_scores,
                'raw_indicators': raw_indicators
            }

            # Add portfolio metrics if provided
            if portfolio_metrics:
                update_data['portfolio'] = portfolio_metrics

            # Store as last meaningful data
            self.last_meaningful_data[card_id] = update_data.copy()

            # Get session ID for targeted emit
            session_id = self.get_session_id_from_app_service()

            # Emit to specific session
            success = self.emit_to_session('card_update', update_data, session_id)

            if not success:
                self.failed_emit_counter[card_id] += 1
            else:
                self.failed_emit_counter[card_id] = 0

        except Exception as e:
            logger.error(f"Error in process_tick for {card_id}: {e}")
            self.failed_emit_counter[card_id] += 1

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