# File: BerlinProject/src/stock_analysis_ui/services/ui_external_tool.py
# PRODUCTION VERSION - Clean, no debug code

"""
UIExternalTool for sending data to browser via WebSocket
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime
from flask_socketio import SocketIO

from environments.tick_data import TickData

logger = logging.getLogger('UIExternalTool')


class UIExternalTool:
    """
    UI External Tool - sends indicator and price data to browser
    """

    def __init__(self, socketio: SocketIO):
        self.socketio: SocketIO = socketio
        self.last_meaningful_data: Dict[str, Dict] = {}

    def indicator_vector(self, card_id: str, symbol: str, tick: TickData,
                         indicators: Dict[str, float], bar_scores: Dict[str, float] = None,
                         raw_indicators: Dict[str, float] = None) -> None:
        """
        Send indicator data to browser

        Args:
            card_id: Card identifier
            symbol: Stock symbol
            tick: Current tick data
            indicators: Calculated indicators
            bar_scores: Bar scores
            raw_indicators: Raw indicator values
        """
        try:
            # Debug: Log what we're sending
            print(f"UI TOOL - SENDING TO {card_id}: bar_scores = {bar_scores}")  # ADD THIS DEBUG
            print(f"UI TOOL - indicators = {indicators}")  # ADD THIS DEBUG

            # Check if this update has bar data (even if values are 0.0)
            has_bar_data: bool = bool(bar_scores and len(bar_scores) > 0)

            # Prepare data
            update_data: Dict[str, Any] = {
                'card_id': card_id,
                'symbol': symbol,
                'price': tick.close,
                'timestamp': self._format_timestamp(tick.timestamp),
                'ohlc': [tick.open, tick.high, tick.low, tick.close],
                'volume': tick.volume,
                'indicators': indicators or {},
                'bar_scores': bar_scores or {},
                'raw_indicators': raw_indicators or {}
            }

            if has_bar_data:
                # Store and emit meaningful data
                self.last_meaningful_data[card_id] = update_data.copy()
                print(f"UI TOOL - EMITTING: {update_data['bar_scores']}")  # ADD THIS DEBUG
                self.socketio.emit('card_update', update_data)
            else:
                # Preserve previous bar scores if available
                if card_id in self.last_meaningful_data:
                    meaningful_data: Dict[str, Any] = self.last_meaningful_data[card_id].copy()
                    meaningful_data['price'] = tick.close
                    meaningful_data['timestamp'] = update_data['timestamp']
                    meaningful_data['ohlc'] = update_data['ohlc']
                    meaningful_data['volume'] = update_data['volume']

                    print(f"UI TOOL - USING CACHED: {meaningful_data['bar_scores']}")  # ADD THIS DEBUG
                    self.socketio.emit('card_update', meaningful_data)
                else:
                    # No previous data - send as-is
                    print(f"UI TOOL - NO CACHE, SENDING: {update_data['bar_scores']}")  # ADD THIS DEBUG
                    self.socketio.emit('card_update', update_data)

        except Exception as e:
            logger.error(f"Error sending indicator data for {card_id}: {e}")

    def price_update(self, card_id: str, symbol: str, tick: TickData) -> None:
        """
        Send price update to browser

        Args:
            card_id: Card identifier
            symbol: Stock symbol
            tick: Current tick data
        """
        try:
            # Preserve bar scores if available
            if card_id in self.last_meaningful_data:
                meaningful_data = self.last_meaningful_data[card_id].copy()
                meaningful_data['price'] = tick.close
                meaningful_data['timestamp'] = self._format_timestamp(tick.timestamp)
                meaningful_data['ohlc'] = [tick.open, tick.high, tick.low, tick.close]
                meaningful_data['volume'] = tick.volume

                self.socketio.emit('card_update', meaningful_data)
            else:
                # Send basic price update
                update_data = {
                    'card_id': card_id,
                    'symbol': symbol,
                    'price': tick.close,
                    'timestamp': self._format_timestamp(tick.timestamp),
                    'ohlc': [tick.open, tick.high, tick.low, tick.close],
                    'volume': tick.volume,
                    'indicators': {},
                    'bar_scores': {},
                    'raw_indicators': {}
                }

                self.socketio.emit('card_update', update_data)

        except Exception as e:
            logger.error(f"Error sending price update for {card_id}: {e}")

    def _format_timestamp(self, timestamp) -> str:
        """Format timestamp for JSON serialization"""
        if isinstance(timestamp, datetime):
            return timestamp.isoformat()
        return str(timestamp)

    def clear_meaningful_data(self, card_id: str = None) -> None:
        """Clear stored meaningful data"""
        if card_id:
            self.last_meaningful_data.pop(card_id, None)
        else:
            self.last_meaningful_data.clear()