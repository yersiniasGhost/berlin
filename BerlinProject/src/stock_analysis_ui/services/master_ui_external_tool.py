"""
MasterUIExternalTool that handles multiple combinations with simple ID-based routing
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime
from flask_socketio import SocketIO
from dataclasses import dataclass

from environments.tick_data import TickData

logger = logging.getLogger('MasterUIExternalTool')


@dataclass
class CombinationInfo:
    """Information about a combination"""
    combination_id: str
    symbol: str
    monitor_config_name: str
    monitor_config: object
    card_id: str


class CombinationData:
    """Data storage for a specific combination"""

    def __init__(self, combination_info: CombinationInfo):
        self.combination_info: CombinationInfo = combination_info

        # Current data
        self.current_data: Dict = {}
        self.indicators: Dict[str, float] = {}
        self.bar_scores: Dict[str, float] = {}
        self.raw_indicators: Dict[str, float] = {}

        # Historical data (limited size)
        self.history: List[Dict] = []
        self.max_history: int = 1000

        # Track last update
        self.last_update: datetime = datetime.now()


class MasterUIExternalTool:
    """
    Master UI External Tool that routes data based on combination_id
    Simple pass-through routing without complex mapping
    """

    def __init__(self, socketio: SocketIO):
        self.socketio: SocketIO = socketio

        # Simple storage: combination_id -> CombinationData
        self.combinations: Dict[str, CombinationData] = {}
        self.active_combinations: set = set()

    def register_combination(self, combination_id: str, symbol: str,
                             monitor_config: object, card_id: str) -> str:
        """
        Register a new combination

        Args:
            combination_id: Unique combination identifier
            symbol: Stock symbol
            monitor_config: MonitorConfiguration object
            card_id: Card ID for UI

        Returns:
            combination_id: The registered combination ID
        """
        combination_info = CombinationInfo(
            combination_id=combination_id,
            symbol=symbol,
            monitor_config_name=monitor_config.name,
            monitor_config=monitor_config,
            card_id=card_id
        )

        combination_data = CombinationData(combination_info)

        self.combinations[combination_id] = combination_data
        self.active_combinations.add(combination_id)

        logger.info(f"Registered combination: {combination_id} ({symbol})")

        # Emit registration event
        self.socketio.emit('combination_registered', {
            'combination_id': combination_id,
            'card_id': card_id,
            'symbol': symbol,
            'monitor_config_name': monitor_config.name,
            'timestamp': datetime.now().isoformat()
        })

        return combination_id

    def unregister_combination(self, combination_id: str) -> bool:
        """
        Unregister a combination

        Args:
            combination_id: Combination to unregister

        Returns:
            bool: True if successfully unregistered
        """
        if combination_id not in self.combinations:
            return False

        del self.combinations[combination_id]
        self.active_combinations.discard(combination_id)

        # Emit unregistration event
        self.socketio.emit('combination_unregistered', {
            'combination_id': combination_id,
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f"Unregistered combination: {combination_id}")
        return True

    def feature_vector(self, fv, tick: TickData) -> None:
        """Handle feature vector (not used in current system)"""
        pass

    def indicator_vector(self, indicators, tick, index, raw_indicators=None, bar_scores=None, combination_id=None):
        # Update data for this specific combination
        combination_data = self.combinations[combination_id]
        combination_data.indicators = indicators
        combination_data.bar_scores = bar_scores

        # Emit to browser with combination_id
        self.socketio.emit('combination_update', {
            'combination_id': combination_id,
            'symbol': tick.symbol,
            'current_price': tick.close,
            'bar_scores': bar_scores,
            'indicators': indicators
        })

    def populate_initial_data(self, combination_id: str, candle_aggregators: Dict) -> None:
        """
        Populate initial data for a combination from historical candles

        Args:
            combination_id: Combination to populate
            candle_aggregators: Dictionary of aggregators by timeframe
        """
        if combination_id not in self.combinations:
            logger.warning(f"Cannot populate data for unknown combination: {combination_id}")
            return

        combination_data = self.combinations[combination_id]
        symbol = combination_data.combination_info.symbol

        # Find the most recent candle with data
        latest_candle = None
        for timeframe, aggregator in candle_aggregators.items():
            current_candle = aggregator.get_current_candle()
            if current_candle and hasattr(current_candle, 'close') and current_candle.close > 0:
                latest_candle = current_candle
                logger.info(f"Found latest {timeframe} candle for {symbol}: ${current_candle.close:.2f}")
                break

        if not latest_candle:
            # Try history
            for timeframe, aggregator in candle_aggregators.items():
                history = aggregator.get_history()
                if history and len(history) > 0:
                    latest_candle = history[-1]
                    logger.info(f"Using latest historical {timeframe} candle for {symbol}: ${latest_candle.close:.2f}")
                    break

        if latest_candle:
            # Ensure symbol is set
            if not hasattr(latest_candle, 'symbol') or not latest_candle.symbol:
                latest_candle.symbol = symbol

            # Store initial data
            combination_data.current_data = {
                'price': latest_candle.close,
                'timestamp': self._format_timestamp(latest_candle.timestamp),
                'ohlc': [latest_candle.open, latest_candle.high, latest_candle.low, latest_candle.close],
                'volume': latest_candle.volume
            }
            combination_data.last_update = datetime.now()

            # Send initial update
            self._emit_combination_update(combination_id, combination_data, latest_candle)
            logger.info(f"Populated initial data for {combination_id}: ${latest_candle.close:.2f}")
        else:
            logger.warning(f"No candle data found for {symbol}")

    def get_combination_data(self, combination_id: str) -> Optional[Dict]:
        """Get current data for a specific combination"""
        if combination_id not in self.combinations:
            return None

        combination_data = self.combinations[combination_id]
        return {
            'combination_info': {
                'combination_id': combination_id,
                'card_id': combination_data.combination_info.card_id,
                'symbol': combination_data.combination_info.symbol,
                'monitor_config_name': combination_data.combination_info.monitor_config_name
            },
            'current': combination_data.current_data,
            'indicators': combination_data.indicators,
            'bar_scores': combination_data.bar_scores,
            'raw_indicators': combination_data.raw_indicators,
            'history': combination_data.history,
            'last_update': combination_data.last_update.isoformat()
        }

    def get_all_combinations_data(self) -> Dict:
        """Get data for all active combinations"""
        return {
            'combinations': {
                combination_id: self.get_combination_data(combination_id)
                for combination_id in self.active_combinations
            },
            'total_combinations': len(self.active_combinations),
            'timestamp': datetime.now().isoformat()
        }

    def handle_completed_candle(self, symbol: str, candle: TickData) -> None:
        """
        Handle completed candle data for combinations with this symbol
        """
        # Find combinations with this symbol
        matching_combinations = []
        for combination_id, combination_data in self.combinations.items():
            if combination_data.combination_info.symbol == symbol:
                matching_combinations.append((combination_id, combination_data))

        if not matching_combinations:
            logger.debug(f"No combinations found for completed candle {symbol}")
            return

        candle_data = {
            'timestamp': self._format_timestamp(candle.timestamp),
            'open': candle.open,
            'high': candle.high,
            'low': candle.low,
            'close': candle.close,
            'volume': candle.volume,
            'timeframe': getattr(candle, 'time_increment', '1m')
        }

        # Send candle completion to each matching combination
        for combination_id, combination_data in matching_combinations:
            # Add to combination's history with size limit
            combination_data.history.append(candle_data.copy())
            if len(combination_data.history) > combination_data.max_history:
                combination_data.history = combination_data.history[-combination_data.max_history:]

            # Send to UI with combination context
            self.socketio.emit('candle_completed', {
                'combination_id': combination_id,
                'card_id': combination_data.combination_info.card_id,
                'symbol': symbol,
                'candle': candle_data,
                'history_size': len(combination_data.history)
            })

            logger.debug(f"Sent completed candle for combination {combination_id}: "
                         f"{candle_data['timeframe']} @ {candle_data['timestamp']}")

    def send_status_update(self) -> None:
        """Send general status update to UI"""
        status = {
            'timestamp': datetime.now().isoformat(),
            'active_combinations': len(self.active_combinations),
            'combination_details': [
                {
                    'combination_id': combination_id,
                    'card_id': data.combination_info.card_id,
                    'symbol': data.combination_info.symbol,
                    'monitor_config': data.combination_info.monitor_config_name,
                    'last_update': data.last_update.isoformat()
                }
                for combination_id, data in self.combinations.items()
                if combination_id in self.active_combinations
            ]
        }

        self.socketio.emit('status_update', status)

    def clear_combination_data(self, combination_id: str) -> bool:
        """Clear data for a specific combination"""
        if combination_id not in self.combinations:
            return False

        combination_data = self.combinations[combination_id]
        combination_data.current_data.clear()
        combination_data.indicators.clear()
        combination_data.bar_scores.clear()
        combination_data.raw_indicators.clear()
        combination_data.history.clear()

        self.socketio.emit('combination_data_cleared', {
            'combination_id': combination_id,
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f"Cleared data for combination: {combination_id}")
        return True

    def clear_all_data(self) -> None:
        """Clear all stored data for all combinations"""
        for combination_id in list(self.active_combinations):
            self.clear_combination_data(combination_id)

        self.socketio.emit('all_data_cleared', {
            'timestamp': datetime.now().isoformat()
        })

        logger.info("Cleared all combination data")

    def _emit_combination_update(self, combination_id: str, combination_data: CombinationData,
                                 tick: TickData) -> None:
        """Send update to browser with combination_id for simple routing"""

        update_data = {
            'combination_id': combination_id,
            'card_id': combination_data.combination_info.card_id,
            'symbol': combination_data.combination_info.symbol,
            'monitor_config_name': combination_data.combination_info.monitor_config_name,
            'timestamp': self._format_timestamp(tick.timestamp),
            'indicators': combination_data.indicators,
            'bar_scores': combination_data.bar_scores,
            'raw_indicators': combination_data.raw_indicators,
            'current_price': tick.close,
            'current_ohlc': [tick.open, tick.high, tick.low, tick.close],
            'volume': tick.volume
        }

        logger.info(f"EMITTING combination_update: {combination_id} ({update_data['symbol']}) @ "
                    f"${update_data['current_price']:.2f} with {len(update_data['bar_scores'])} bars")

        self.socketio.emit('combination_update', update_data)

    def _format_timestamp(self, timestamp) -> str:
        """Format timestamp for JSON serialization"""
        if isinstance(timestamp, datetime):
            return timestamp.isoformat()
        return str(timestamp)