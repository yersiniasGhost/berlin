# File: BerlinProject/src/stock_analysis_ui/services/ui_external_tool.py
# Updated version with portfolio metrics support

"""
UIExternalTool for sending data to browser via WebSocket including portfolio metrics
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime

import numpy as np
from flask_socketio import SocketIO

from data_streamer import ExternalTool
from models.tick_data import TickData

logger = logging.getLogger('UIExternalTool')


class UIExternalTool(ExternalTool):
    """
    UI External Tool - sends indicator, price, and portfolio data to browser
    """

    def __init__(self, socketio: SocketIO):
        self.socketio: SocketIO = socketio
        self.last_meaningful_data: Dict[str, Dict] = {}

    def process_tick(self, card_id: str, symbol: str, tick_data: TickData,
                     indicators: Dict[str, float], raw_indicators: Dict[str, float],
                     bar_scores: Dict[str, float], portfolio_metrics: Optional[Dict[str, Any]] = None) -> None:
        """
        Process real-time tick data and send updates to browser including portfolio metrics

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
                'indicators': indicators,
                'bar_scores': bar_scores,
                'raw_indicators': raw_indicators
            }

            # Add portfolio metrics if available
            if portfolio_metrics:
                update_data['portfolio'] = portfolio_metrics

            self.socketio.emit('card_update', update_data)

        except Exception as e:
            logger.error(f"Error in process_tick for {card_id}: {e}")

    def indicator_vector(self, card_id: str, symbol: str, tick: TickData,
                         indicators: Dict[str, float], bar_scores: Dict[str, float] = None,
                         raw_indicators: Dict[str, float] = None,
                         combination_id: Optional[str] = None,
                         portfolio_metrics: Optional[Dict[str, Any]] = None) -> None:
        """
        Send indicator data to browser including portfolio metrics

        Args:
            card_id: Card identifier
            symbol: Stock symbol
            tick: Current tick data
            indicators: Calculated indicators
            bar_scores: Bar scores
            raw_indicators: Raw indicator values
            portfolio_metrics: Portfolio performance metrics
        """
        try:
            # Check if this update has bar data (even if values are 0.0)
            has_bar_data: bool = bool(bar_scores and len(bar_scores) > 0)

            # UPDATED: Get test_name from app_service combinations
            test_name = "Unknown Config"
            try:
                from flask import current_app
                if hasattr(current_app, 'app_service') and card_id in current_app.app_service.combinations:
                    test_name = current_app.app_service.combinations[card_id].get('test_name', 'Unknown Config')
            except:
                pass

            # Prepare data
            update_data: Dict[str, Any] = {
                'card_id': card_id,
                'symbol': symbol,
                'test_name': test_name,  # ADDED: Include test_name
                'price': tick.close,
                'timestamp': self._format_timestamp(tick.timestamp),
                'ohlc': [tick.open, tick.high, tick.low, tick.close],
                'volume': tick.volume,
                'indicators': indicators or {},
                'bar_scores': bar_scores or {},
                'raw_indicators': raw_indicators or {}
            }

            # Add portfolio metrics if available
            if portfolio_metrics:
                update_data['portfolio'] = portfolio_metrics

            if has_bar_data:
                # Store and emit meaningful data
                self.last_meaningful_data[card_id] = update_data.copy()
                self.socketio.emit('card_update', update_data)
            else:
                # Preserve previous bar scores if available
                if card_id in self.last_meaningful_data:
                    meaningful_data: Dict[str, Any] = self.last_meaningful_data[card_id].copy()
                    meaningful_data['price'] = tick.close
                    meaningful_data['timestamp'] = update_data['timestamp']
                    meaningful_data['ohlc'] = update_data['ohlc']
                    meaningful_data['volume'] = update_data['volume']
                    meaningful_data['test_name'] = test_name  # ADDED: Update test_name

                    # Update portfolio metrics if provided
                    if portfolio_metrics:
                        meaningful_data['portfolio'] = portfolio_metrics

                    self.socketio.emit('card_update', meaningful_data)
                else:
                    # No previous data - send as-is
                    self.socketio.emit('card_update', update_data)

        except Exception as e:
            logger.error(f"Error sending indicator data for {card_id}: {e}")

    def feature_vector(self, fv: np.array, tick: TickData) -> None:
        pass

    def indicator_vector(self, card_id: str, symbol: str, tick: TickData,
                         indicators: Dict[str, float], bar_scores: Dict[str, float] = None,
                         raw_indicators: Dict[str, float] = None,
                         combination_id: Optional[str] = None,
                         portfolio_metrics: Optional[Dict[str, Any]] = None) -> None:
        """
        Send indicator data to browser including portfolio metrics

        Args:
            card_id: Card identifier
            symbol: Stock symbol
            tick: Current tick data
            indicators: Calculated indicators
            bar_scores: Bar scores
            raw_indicators: Raw indicator values
            portfolio_metrics: Portfolio performance metrics
        """
        try:
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

            # Add portfolio metrics if available
            if portfolio_metrics:
                update_data['portfolio'] = portfolio_metrics

            if has_bar_data:
                # Store and emit meaningful data
                self.last_meaningful_data[card_id] = update_data.copy()
                self.socketio.emit('card_update', update_data)
            else:
                # Preserve previous bar scores if available
                if card_id in self.last_meaningful_data:
                    meaningful_data: Dict[str, Any] = self.last_meaningful_data[card_id].copy()
                    meaningful_data['price'] = tick.close
                    meaningful_data['timestamp'] = update_data['timestamp']
                    meaningful_data['ohlc'] = update_data['ohlc']
                    meaningful_data['volume'] = update_data['volume']

                    # Update portfolio metrics if provided
                    if portfolio_metrics:
                        meaningful_data['portfolio'] = portfolio_metrics

                    self.socketio.emit('card_update', meaningful_data)
                else:
                    # No previous data - send as-is
                    self.socketio.emit('card_update', update_data)

        except Exception as e:
            logger.error(f"Error sending indicator data for {card_id}: {e}")

    def price_update(self, card_id: str, symbol: str, tick: TickData,
                     portfolio_metrics: Optional[Dict[str, Any]] = None) -> None:
        """
        Send price update to browser including portfolio metrics

        Args:
            card_id: Card identifier
            symbol: Stock symbol
            tick: Current tick data
            portfolio_metrics: Portfolio performance metrics
        """
        try:
            # Preserve bar scores if available
            if card_id in self.last_meaningful_data:
                meaningful_data = self.last_meaningful_data[card_id].copy()
                meaningful_data['price'] = tick.close
                meaningful_data['timestamp'] = self._format_timestamp(tick.timestamp)
                meaningful_data['ohlc'] = [tick.open, tick.high, tick.low, tick.close]
                meaningful_data['volume'] = tick.volume

                # Update portfolio metrics if provided
                if portfolio_metrics:
                    meaningful_data['portfolio'] = portfolio_metrics

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

                # Add portfolio metrics if provided
                if portfolio_metrics:
                    update_data['portfolio'] = portfolio_metrics

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