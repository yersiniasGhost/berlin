# File: BerlinProject/src/stock_analysis_ui/services/ui_external_tool.py

"""
Simplified UIExternalTool - just passes data to browser
"""

import logging
from typing import Dict, Optional
from datetime import datetime
from flask_socketio import SocketIO

from environments.tick_data import TickData

logger = logging.getLogger('UIExternalTool')


class UIExternalTool:
    """
    Simplified UI External Tool - just routes data to browser by card_id
    """

    def __init__(self, socketio: SocketIO):
        self.socketio: SocketIO = socketio
        logger.info("UIExternalTool initialized - simplified version")

    def indicator_vector(self, card_id: str, symbol: str, tick: TickData,
                         indicators: Dict[str, float], bar_scores: Dict[str, float] = None,
                         raw_indicators: Dict[str, float] = None) -> None:
        """
        Send indicator data to browser

        Args:
            card_id: Card identifier (card1, card2, etc.)
            symbol: Stock symbol
            tick: Current tick data
            indicators: Calculated indicators
            bar_scores: Bar scores
            raw_indicators: Raw indicator values
        """
        try:
            # Prepare data for browser
            update_data = {
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

            logger.info(f"🚀 EMITTING card_update: {card_id} ({symbol}) @ ${tick.close:.2f} "
                        f"with {len(bar_scores or {})} bars")

            # Send to browser
            self.socketio.emit('card_update', update_data)

        except Exception as e:
            logger.error(f"Error sending indicator data for {card_id}: {e}")

    def price_update(self, card_id: str, symbol: str, tick: TickData) -> None:
        """
        Send price update to browser (when indicators aren't ready yet)

        Args:
            card_id: Card identifier
            symbol: Stock symbol
            tick: Current tick data
        """
        try:
            # Prepare simple price update
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

            logger.debug(f"💰 EMITTING price_update: {card_id} ({symbol}) @ ${tick.close:.2f}")

            # Send to browser
            self.socketio.emit('card_update', update_data)

        except Exception as e:
            logger.error(f"Error sending price update for {card_id}: {e}")

    def _format_timestamp(self, timestamp) -> str:
        """Format timestamp for JSON serialization"""
        if isinstance(timestamp, datetime):
            return timestamp.isoformat()
        return str(timestamp)