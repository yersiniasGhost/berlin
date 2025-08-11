"""
Enhanced UIExternalTool with candlestick chart support and minimal logging
"""

import logging
import time
from typing import Dict, Optional, Any, List
from datetime import datetime
from collections import defaultdict

import numpy as np
from flask_socketio import SocketIO

from data_streamer import ExternalTool
from models.tick_data import TickData

logger = logging.getLogger('UIExternalTool')


class UIExternalTool(ExternalTool):
    """
    Enhanced UI External Tool - sends data to browser via WebSocket with candlestick support
    """

    def __init__(self, socketio: SocketIO, app_service=None):
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

    # Required abstract methods from ExternalTool base class
    def feature_vector(self, tick_data: TickData) -> np.ndarray:
        """Required abstract method - return empty array since UI tool doesn't use features"""
        return np.array([])

    def indicator_vector(self, tick_data: TickData) -> np.ndarray:
        """Required abstract method - return empty array since UI tool doesn't use indicators"""
        return np.array([])

    def emit_to_session(self, event_name, data, session_id=None):
        """Emit WebSocket event to specific session room or broadcast"""
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

    def process_tick(self, card_id: str, symbol: str, tick_data: TickData,
                     indicators: Dict[str, float], raw_indicators: Dict[str, float],
                     bar_scores: Dict[str, float], portfolio_metrics: Optional[Dict[str, Any]] = None) -> None:
        """
        Process real-time tick data and send updates to browser (session-specific) - Enhanced for candlestick support
        """
        try:
            current_time = time.time()

            # Rate limiting check
            if current_time - self.last_update_time[card_id] < self.min_update_interval:
                return

            self.last_update_time[card_id] = current_time
            self.update_counter[card_id] += 1

            # Build update data - Enhanced with candlestick information
            update_data = {
                'card_id': card_id,
                'symbol': symbol,
                'price': tick_data.close,
                'timestamp': tick_data.timestamp.isoformat(),
                'ohlc': [tick_data.open, tick_data.high, tick_data.low, tick_data.close],  # For candlestick chart
                'volume': tick_data.volume,
                'indicators': indicators,
                'raw_indicators': raw_indicators,
                'bar_scores': bar_scores,
                'update_count': self.update_counter[card_id]
            }

            # Add portfolio data if available
            if portfolio_metrics:
                update_data['portfolio'] = portfolio_metrics
                update_data['portfolio_data'] = portfolio_metrics  # For backward compatibility

            # Get session ID from app_service if available
            session_id = self.get_session_id_from_app_service()

            # Emit to specific session or broadcast
            success = self.emit_to_session('card_update', update_data, session_id)

            if not success:
                self.failed_emit_counter[card_id] += 1
                if self.failed_emit_counter[card_id] > self.max_failed_emits:
                    logger.warning(f"Too many failed emits for card {card_id}, temporarily reducing updates")
                    self.min_update_interval = min(self.min_update_interval * 1.5, 1.0)

            # Reset failed counter on success
            if success and self.failed_emit_counter[card_id] > 0:
                self.failed_emit_counter[card_id] = 0
                self.min_update_interval = 0.05  # Reset to normal rate

        except Exception as e:
            logger.error(f"Error processing tick for card {card_id}: {e}")

    def process_completed_candle(self, card_id: str, symbol: str, timeframe: str,
                               completed_candle: TickData, aggregator_history: List[TickData]) -> None:
        """
        Process completed candle and send candlestick update to browser
        """
        try:
            # Prepare candlestick data in Highcharts format
            candlestick_point = [
                int(completed_candle.timestamp.timestamp() * 1000),  # Timestamp in milliseconds
                float(completed_candle.open),
                float(completed_candle.high),
                float(completed_candle.low),
                float(completed_candle.close)
            ]

            update_data = {
                'card_id': card_id,
                'symbol': symbol,
                'timeframe': timeframe,
                'completed_candle': candlestick_point,
                'candle_count': len(aggregator_history),
                'timestamp': completed_candle.timestamp.isoformat()
            }

            # Get session ID and emit
            session_id = self.get_session_id_from_app_service()
            self.emit_to_session('candle_completed', update_data, session_id)

            logger.debug(f"Sent completed candle for {symbol} {timeframe}: {candlestick_point}")

        except Exception as e:
            logger.error(f"Error processing completed candle for {card_id}: {e}")

    def get_candlestick_history(self, card_id: str, timeframe: str = '1m', limit: int = 200) -> List[List]:
        """
        Get historical candlestick data for a specific card and timeframe
        """
        try:
            if not self.app_service or card_id not in self.app_service.combinations:
                return []

            combination = self.app_service.combinations[card_id]
            data_streamer = combination['data_streamer']

            # Get all candle data
            all_candle_data = data_streamer._get_all_candle_data()

            # Find matching aggregator
            aggregator_key = f"{timeframe}-normal"  # Assuming normal aggregators
            if aggregator_key not in all_candle_data:
                # Try without the suffix
                for key in all_candle_data.keys():
                    if key.startswith(timeframe):
                        aggregator_key = key
                        break
                else:
                    logger.warning(f"No aggregator found for timeframe {timeframe}")
                    return []

            candles = all_candle_data[aggregator_key]

            # Convert to Highcharts format
            candlestick_data = []
            for candle in candles[-limit:]:  # Get last N candles
                timestamp = int(candle.timestamp.timestamp() * 1000)
                candlestick_data.append([
                    timestamp,
                    float(candle.open),
                    float(candle.high),
                    float(candle.low),
                    float(candle.close)
                ])

            return candlestick_data

        except Exception as e:
            logger.error(f"Error getting candlestick history for {card_id}: {e}")
            return []

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the UI tool"""
        current_time = time.time()

        return {
            'total_emits': self.total_emits,
            'failed_emits': self.failed_emits,
            'success_rate': (self.total_emits - self.failed_emits) / max(self.total_emits, 1) * 100,
            'last_successful_emit': self.last_successful_emit,
            'seconds_since_last_emit': current_time - self.last_successful_emit,
            'min_update_interval': self.min_update_interval,
            'active_cards': len(self.last_update_time),
            'total_updates': sum(self.update_counter.values())
        }

    def send_system_message(self, message: str, message_type: str = 'info', session_id: str = None):
        """Send system message to UI"""
        try:
            message_data = {
                'message': message,
                'type': message_type,
                'timestamp': datetime.now().isoformat()
            }

            self.emit_to_session('system_message', message_data, session_id)
            logger.info(f"Sent system message: {message}")

        except Exception as e:
            logger.error(f"Error sending system message: {e}")

    def send_streaming_status(self, is_streaming: bool, session_id: str = None):
        """Send streaming status update to UI"""
        try:
            status_data = {
                'streaming': is_streaming,
                'timestamp': datetime.now().isoformat()
            }

            self.emit_to_session('streaming_status', status_data, session_id)
            logger.info(f"Sent streaming status: {is_streaming}")

        except Exception as e:
            logger.error(f"Error sending streaming status: {e}")

    def send_connection_status(self, connected: bool, session_id: str = None):
        """Send connection status update to UI"""
        try:
            status_data = {
                'connected': connected,
                'timestamp': datetime.now().isoformat()
            }

            self.emit_to_session('connection_status', status_data, session_id)

        except Exception as e:
            logger.error(f"Error sending connection status: {e}")

    def send_initial_data(self, combinations: List[Dict], session_id: str = None):
        """Send initial data when client connects"""
        try:
            initial_data = {
                'combinations': combinations,
                'streaming': self.app_service.is_streaming if self.app_service else False,
                'authenticated': True,
                'message': 'Connected successfully',
                'timestamp': datetime.now().isoformat()
            }

            self.emit_to_session('initial_data', initial_data, session_id)
            logger.info(f"Sent initial data with {len(combinations)} combinations")

        except Exception as e:
            logger.error(f"Error sending initial data: {e}")

    def cleanup(self):
        """Cleanup resources when shutting down"""
        try:
            logger.info("Cleaning up UIExternalTool...")

            # Clear tracking dictionaries
            self.last_update_time.clear()
            self.update_counter.clear()
            self.failed_emit_counter.clear()
            self.last_meaningful_data.clear()

            logger.info("UIExternalTool cleanup completed")

        except Exception as e:
            logger.error(f"Error during UIExternalTool cleanup: {e}")


    def get_session_id_from_app_service(self):
        """Get session ID from the app_service if it has one"""
        if hasattr(self.app_service, 'session_id'):
            return self.app_service.session_id
        return None

    def process_tick(self, card_id: str, symbol: str, tick_data: TickData,
                     indicators: Dict[str, float], raw_indicators: Dict[str, float],
                     bar_scores: Dict[str, float], portfolio_metrics: Optional[Dict[str, Any]] = None) -> None:
        """
        Process real-time tick data and send updates to browser (session-specific) - Enhanced for candlestick support
        """
        try:
            current_time = time.time()

            # Rate limiting check
            if current_time - self.last_update_time[card_id] < self.min_update_interval:
                return

            self.last_update_time[card_id] = current_time
            self.update_counter[card_id] += 1

            # Build update data - Enhanced with candlestick information
            update_data = {
                'card_id': card_id,
                'symbol': symbol,
                'price': tick_data.close,
                'timestamp': tick_data.timestamp.isoformat(),
                'ohlc': [tick_data.open, tick_data.high, tick_data.low, tick_data.close],  # For candlestick chart
                'volume': tick_data.volume,
                'indicators': indicators,
                'raw_indicators': raw_indicators,
                'bar_scores': bar_scores,
                'update_count': self.update_counter[card_id]
            }

            # Add portfolio data if available
            if portfolio_metrics:
                update_data['portfolio'] = portfolio_metrics
                update_data['portfolio_data'] = portfolio_metrics  # For backward compatibility

            # Get session ID from app_service if available
            session_id = self.get_session_id_from_app_service()

            # Emit to specific session or broadcast
            success = self.emit_to_session('card_update', update_data, session_id)

            if not success:
                self.failed_emit_counter[card_id] += 1
                if self.failed_emit_counter[card_id] > self.max_failed_emits:
                    logger.warning(f"Too many failed emits for card {card_id}, temporarily reducing updates")
                    self.min_update_interval = min(self.min_update_interval * 1.5, 1.0)

            # Reset failed counter on success
            if success and self.failed_emit_counter[card_id] > 0:
                self.failed_emit_counter[card_id] = 0
                self.min_update_interval = 0.05  # Reset to normal rate

        except Exception as e:
            logger.error(f"Error processing tick for card {card_id}: {e}")

    def process_completed_candle(self, card_id: str, symbol: str, timeframe: str,
                               completed_candle: TickData, aggregator_history: List[TickData]) -> None:
        """
        Process completed candle and send candlestick update to browser
        """
        try:
            # Prepare candlestick data in Highcharts format
            candlestick_point = [
                int(completed_candle.timestamp.timestamp() * 1000),  # Timestamp in milliseconds
                float(completed_candle.open),
                float(completed_candle.high),
                float(completed_candle.low),
                float(completed_candle.close)
            ]

            update_data = {
                'card_id': card_id,
                'symbol': symbol,
                'timeframe': timeframe,
                'completed_candle': candlestick_point,
                'candle_count': len(aggregator_history),
                'timestamp': completed_candle.timestamp.isoformat()
            }

            # Get session ID and emit
            session_id = self.get_session_id_from_app_service()
            self.emit_to_session('candle_completed', update_data, session_id)

            logger.debug(f"Sent completed candle for {symbol} {timeframe}: {candlestick_point}")

        except Exception as e:
            logger.error(f"Error processing completed candle for {card_id}: {e}")

    def get_candlestick_history(self, card_id: str, timeframe: str = '1m', limit: int = 200) -> List[List]:
        """
        Get historical candlestick data for a specific card and timeframe
        """
        try:
            if not self.app_service or card_id not in self.app_service.combinations:
                return []

            combination = self.app_service.combinations[card_id]
            data_streamer = combination['data_streamer']

            # Get all candle data
            all_candle_data = data_streamer._get_all_candle_data()

            # Find matching aggregator
            aggregator_key = f"{timeframe}-normal"  # Assuming normal aggregators
            if aggregator_key not in all_candle_data:
                # Try without the suffix
                for key in all_candle_data.keys():
                    if key.startswith(timeframe):
                        aggregator_key = key
                        break
                else:
                    logger.warning(f"No aggregator found for timeframe {timeframe}")
                    return []

            candles = all_candle_data[aggregator_key]

            # Convert to Highcharts format
            candlestick_data = []
            for candle in candles[-limit:]:  # Get last N candles
                timestamp = int(candle.timestamp.timestamp() * 1000)
                candlestick_data.append([
                    timestamp,
                    float(candle.open),
                    float(candle.high),
                    float(candle.low),
                    float(candle.close)
                ])

            return candlestick_data

        except Exception as e:
            logger.error(f"Error getting candlestick history for {card_id}: {e}")
            return []

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the UI tool"""
        current_time = time.time()

        return {
            'total_emits': self.total_emits,
            'failed_emits': self.failed_emits,
            'success_rate': (self.total_emits - self.failed_emits) / max(self.total_emits, 1) * 100,
            'last_successful_emit': self.last_successful_emit,
            'seconds_since_last_emit': current_time - self.last_successful_emit,
            'min_update_interval': self.min_update_interval,
            'active_cards': len(self.last_update_time),
            'total_updates': sum(self.update_counter.values())
        }

    def send_system_message(self, message: str, message_type: str = 'info', session_id: str = None):
        """Send system message to UI"""
        try:
            message_data = {
                'message': message,
                'type': message_type,
                'timestamp': datetime.now().isoformat()
            }

            self.emit_to_session('system_message', message_data, session_id)
            logger.info(f"Sent system message: {message}")

        except Exception as e:
            logger.error(f"Error sending system message: {e}")

    def send_streaming_status(self, is_streaming: bool, session_id: str = None):
        """Send streaming status update to UI"""
        try:
            status_data = {
                'streaming': is_streaming,
                'timestamp': datetime.now().isoformat()
            }

            self.emit_to_session('streaming_status', status_data, session_id)
            logger.info(f"Sent streaming status: {is_streaming}")

        except Exception as e:
            logger.error(f"Error sending streaming status: {e}")

    def send_connection_status(self, connected: bool, session_id: str = None):
        """Send connection status update to UI"""
        try:
            status_data = {
                'connected': connected,
                'timestamp': datetime.now().isoformat()
            }

            self.emit_to_session('connection_status', status_data, session_id)

        except Exception as e:
            logger.error(f"Error sending connection status: {e}")

    def send_initial_data(self, combinations: List[Dict], session_id: str = None):
        """Send initial data when client connects"""
        try:
            initial_data = {
                'combinations': combinations,
                'streaming': self.app_service.is_streaming if self.app_service else False,
                'authenticated': True,
                'message': 'Connected successfully',
                'timestamp': datetime.now().isoformat()
            }

            self.emit_to_session('initial_data', initial_data, session_id)
            logger.info(f"Sent initial data with {len(combinations)} combinations")

        except Exception as e:
            logger.error(f"Error sending initial data: {e}")
