import logging
from typing import Dict, Optional
from datetime import datetime
from flask_socketio import SocketIO

from environments.tick_data import TickData
from data_streamer.external_tool import ExternalTool

logger = logging.getLogger('MasterUIExternalTool')


class MasterUIExternalTool(ExternalTool):
    """
    Single UIExternalTool that routes based on combination_id
    No complex routing logic - just passes IDs through to WebSocket
    """

    def __init__(self, socketio: SocketIO):
        self.socketio = socketio

        # Simple data storage by combination_id (optional - for debugging/logging)
        self.combination_data: Dict[str, Dict] = {}

        # Track registered combinations
        self.registered_combinations: Dict[str, Dict] = {}

        logger.info("Created MasterUIExternalTool - ready for ID-based routing")

    def indicator_vector(self, combination_id: str, indicators: Dict[str, float],
                         tick: TickData, raw_indicators: Optional[Dict[str, float]] = None,
                         bar_scores: Optional[Dict[str, float]] = None) -> None:
        """
        Handle indicator updates - just pass through to WebSocket with ID
        NO ROUTING LOGIC NEEDED - just pass the ID through!
        """

        logger.debug(f"Received indicator update for combination_id: {combination_id}")

        # Update internal data storage (optional - for debugging/status)
        self.combination_data[combination_id] = {
            'indicators': indicators or {},
            'bar_scores': bar_scores or {},
            'raw_indicators': raw_indicators or {},
            'current_price': tick.close if tick else 0.0,
            'symbol': tick.symbol if tick else 'UNKNOWN',
            'last_update': datetime.now().isoformat()
        }

        # Simply pass everything through to WebSocket with the ID
        update_data = {
            'combination_id': combination_id,  # The routing key!
            'symbol': tick.symbol if tick else 'UNKNOWN',
            'price': tick.close if tick else 0.0,
            'indicators': indicators or {},
            'bar_scores': bar_scores or {},
            'raw_indicators': raw_indicators or {},
            'timestamp': datetime.now().isoformat()
        }

        # Send to browser - let browser decide where it goes
        self.socketio.emit('combination_update', update_data)

        logger.info(f"Forwarded update for combination_id: {combination_id} - ${tick.close:.2f}")

    def feature_vector(self, combination_id: str, fv, tick: TickData) -> None:
        """Handle feature vector updates (optional)"""
        logger.debug(f"Received feature vector for combination_id: {combination_id}")

        # Could emit feature vector data if needed
        # self.socketio.emit('feature_vector_update', {
        #     'combination_id': combination_id,
        #     'feature_vector': fv.tolist() if hasattr(fv, 'tolist') else fv,
        #     'symbol': tick.symbol if tick else 'UNKNOWN'
        # })

    def register_combination(self, combination_id: str, metadata: Dict) -> None:
        """Register a new combination (for UI management)"""
        self.combination_data[combination_id] = {}
        self.registered_combinations[combination_id] = metadata

        # Notify browser that new combination exists
        self.socketio.emit('combination_registered', {
            'combination_id': combination_id,
            'metadata': metadata,
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f"Registered combination_id: {combination_id}")

    def unregister_combination(self, combination_id: str) -> None:
        """Unregister a combination"""
        if combination_id in self.combination_data:
            del self.combination_data[combination_id]

        if combination_id in self.registered_combinations:
            del self.registered_combinations[combination_id]

        # Notify browser to remove the card
        self.socketio.emit('combination_unregistered', {
            'combination_id': combination_id,
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f"Unregistered combination_id: {combination_id}")

    def get_combination_data(self, combination_id: str) -> Optional[Dict]:
        """Get current data for a specific combination"""
        if combination_id not in self.combination_data:
            return None

        return {
            'combination_id': combination_id,
            'metadata': self.registered_combinations.get(combination_id, {}),
            'current_data': self.combination_data[combination_id],
            'last_update': self.combination_data[combination_id].get('last_update'),
            'timestamp': datetime.now().isoformat()
        }

    def get_all_combinations_data(self) -> Dict:
        """Get data for all registered combinations"""
        combinations_list = []

        for combination_id in self.registered_combinations:
            combination_data = self.get_combination_data(combination_id)
            if combination_data:
                combinations_list.append(combination_data)

        return {
            'combinations': combinations_list,
            'total_combinations': len(self.registered_combinations),
            'timestamp': datetime.now().isoformat()
        }

    def broadcast_status(self) -> None:
        """Broadcast current status to all clients"""
        status = {
            'total_combinations': len(self.registered_combinations),
            'active_combinations': list(self.registered_combinations.keys()),
            'timestamp': datetime.now().isoformat()
        }

        self.socketio.emit('status_update', status)
        logger.info(f"Broadcasted status: {status['total_combinations']} combinations")

    def handle_completed_candle(self, combination_id: str, symbol: str, candle: TickData) -> None:
        """Handle completed candle data"""
        candle_data = {
            'combination_id': combination_id,
            'symbol': symbol,
            'candle': {
                'timestamp': candle.timestamp.isoformat() if hasattr(candle.timestamp, 'isoformat') else str(
                    candle.timestamp),
                'open': candle.open,
                'high': candle.high,
                'low': candle.low,
                'close': candle.close,
                'volume': candle.volume,
                'timeframe': getattr(candle, 'time_increment', '1m')
            }
        }

        self.socketio.emit('candle_completed', candle_data)
        logger.debug(f"Sent completed candle for combination_id: {combination_id}")

    def clear_all_data(self) -> None:
        """Clear all stored data"""
        self.combination_data.clear()
        self.registered_combinations.clear()

        self.socketio.emit('all_data_cleared', {
            'timestamp': datetime.now().isoformat()
        })

        logger.info("Cleared all combination data")