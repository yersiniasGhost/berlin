import logging
from typing import Dict, Optional, List, Set
from datetime import datetime
from flask_socketio import SocketIO
from collections import defaultdict
from dataclasses import dataclass

from environments.tick_data import TickData

logger = logging.getLogger('UIExternalTool')


@dataclass
class CombinationInfo:
    """Information about a symbol + monitor config combination"""
    symbol: str
    monitor_config_name: str
    monitor_config: object  # The actual MonitorConfiguration object
    card_id: str  # Unique identifier for the UI card


class CombinationData:
    """Data storage for a specific combination (symbol + monitor config)"""

    def __init__(self, combination_info: CombinationInfo):
        self.combination_info: CombinationInfo = combination_info

        # Current data for this combination
        self.current_data: Dict = {}
        self.indicators: Dict[str, float] = {}
        self.bar_scores: Dict[str, float] = {}
        self.raw_indicators: Dict[str, float] = {}

        # Historical data (limited size)
        self.history: List[Dict] = []
        self.max_history: int = 1000

        # Track last update time
        self.last_update: datetime = datetime.now()


class UIExternalTool:
    """
    Manages multiple DataStreamer combinations, each representing a UI card.
    Maps DataStreamers to WebSocket emissions based on symbol + monitor config combinations.
    """

    def __init__(self, socketio: SocketIO):
        self.socketio: SocketIO = socketio

        # Map combination_id -> CombinationData
        self.combinations: Dict[str, CombinationData] = {}

        # Map DataStreamer instance -> combination_id for routing
        self.streamer_to_combination: Dict[object, str] = {}

        # Track active combinations
        self.active_combinations: Set[str] = set()

    def register_combination(self, data_streamer: object, symbol: str,
                             monitor_config: object, card_id: Optional[str] = None) -> str:
        """
        Register a new DataStreamer + combination mapping

        Args:
            data_streamer: The DataStreamer instance
            symbol: Stock symbol
            monitor_config: MonitorConfiguration object
            card_id: Optional custom card ID, otherwise auto-generated

        Returns:
            combination_id: Unique identifier for this combination
        """
        if card_id is None:
            card_id = f"{symbol}_{monitor_config.name}_{len(self.combinations)}"

        combination_id = card_id

        # Create combination info
        combination_info = CombinationInfo(
            symbol=symbol,
            monitor_config_name=monitor_config.name,
            monitor_config=monitor_config,
            card_id=card_id
        )

        # Create data storage for this combination
        combination_data = CombinationData(combination_info)

        # Store mappings
        self.combinations[combination_id] = combination_data
        self.streamer_to_combination[data_streamer] = combination_id
        self.active_combinations.add(combination_id)

        logger.info(f"Registered combination: {combination_id} ({symbol} + {monitor_config.name})")

        # Emit registration event to UI
        self.socketio.emit('combination_registered', {
            'combination_id': combination_id,
            'card_id': card_id,
            'symbol': symbol,
            'monitor_config_name': monitor_config.name,
            'timestamp': datetime.now().isoformat()
        })

        return combination_id

    def populate_initial_data(self, combination_id: str, candle_aggregators: Dict[str, object]) -> None:
        """
        Populate initial data for a combination from historical candles
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
            # Try to get from history
            for timeframe, aggregator in candle_aggregators.items():
                history = aggregator.get_history()
                if history and len(history) > 0:
                    latest_candle = history[-1]  # Get most recent from history
                    logger.info(f"Using latest historical {timeframe} candle for {symbol}: ${latest_candle.close:.2f}")
                    break

        if latest_candle:
            # Ensure the candle has symbol
            if not hasattr(latest_candle, 'symbol') or not latest_candle.symbol:
                latest_candle.symbol = symbol

            # Store current price data
            combination_data.current_data = {
                'price': latest_candle.close,
                'timestamp': self._format_timestamp(latest_candle.timestamp),
                'ohlc': [latest_candle.open, latest_candle.high, latest_candle.low, latest_candle.close],
                'volume': latest_candle.volume
            }
            combination_data.last_update = datetime.now()

            # Send initial update to UI
            self._emit_combination_update(combination_id, combination_data, latest_candle)

            logger.info(f"Populated initial data for {combination_id}: ${latest_candle.close:.2f}")
        else:
            logger.warning(f"No candle data found for {symbol} in any timeframe")

    def unregister_combination(self, data_streamer: object) -> bool:
        """
        Unregister a DataStreamer combination

        Args:
            data_streamer: The DataStreamer instance to unregister

        Returns:
            bool: True if successfully unregistered
        """
        if data_streamer not in self.streamer_to_combination:
            return False

        combination_id = self.streamer_to_combination[data_streamer]

        # Clean up mappings
        del self.streamer_to_combination[data_streamer]
        del self.combinations[combination_id]
        self.active_combinations.discard(combination_id)

        # Emit unregistration event to UI
        self.socketio.emit('combination_unregistered', {
            'combination_id': combination_id,
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f"Unregistered combination: {combination_id}")
        return True

    def _get_combination_from_streamer(self, data_streamer: object) -> Optional[str]:
        """Get combination_id from DataStreamer instance"""
        return self.streamer_to_combination.get(data_streamer)

    def feature_vector(self, fv, tick: TickData) -> None:
        """Handle feature vector updates (not used in current system)"""
        pass

    def indicator_vector(self, indicators: Dict[str, float], tick: Optional[TickData],
                         index: int, raw_indicators: Optional[Dict[str, float]] = None,
                         bar_scores: Optional[Dict[str, float]] = None) -> None:
        """
        Standard indicator_vector method for compatibility
        Routes by symbol (fallback method)
        """
        self.indicator_vector_with_streamer(
            indicators=indicators,
            tick=tick,
            index=index,
            raw_indicators=raw_indicators,
            bar_scores=bar_scores,
            data_streamer=None
        )

    def indicator_vector_with_streamer(self, indicators: Dict[str, float], tick: Optional[TickData],
                                       index: int, raw_indicators: Optional[Dict[str, float]] = None,
                                       bar_scores: Optional[Dict[str, float]] = None,
                                       data_streamer: Optional[object] = None) -> None:
        """
        Process indicator updates for a specific combination with proper DataStreamer routing

        Args:
            indicators: Indicator results
            tick: Current tick data
            index: Data index
            raw_indicators: Raw indicator values
            bar_scores: Calculated bar scores
            data_streamer: The DataStreamer instance (for routing)
        """

        logger.info(
            f"Received indicator update from DataStreamer {id(data_streamer) if data_streamer else 'None'}: indicators={len(indicators)}, bar_scores={len(bar_scores or {})}, tick_symbol={tick.symbol if tick else 'None'}")

        if not tick or not hasattr(tick, 'symbol'):
            logger.warning("No tick data or symbol")
            return

        # ALWAYS try to get combination ID from the data_streamer FIRST
        combination_id = None
        if data_streamer:
            combination_id = self._get_combination_from_streamer(data_streamer)
            logger.info(f"Found combination from streamer mapping: {combination_id}")

        # If no streamer mapping found, this is a problem - don't fall back to symbol matching
        # because it could route to the wrong combination
        if not combination_id:
            logger.error(
                f"No combination mapping found for DataStreamer {id(data_streamer)}. Available mappings: {list(self.streamer_to_combination.keys())}")
            return

        if combination_id not in self.combinations:
            logger.error(f"Combination {combination_id} not found in active combinations")
            return

        combination_data = self.combinations[combination_id]
        symbol = tick.symbol
        timestamp = self._format_timestamp(tick.timestamp)

        # Update combination data
        combination_data.indicators = indicators
        combination_data.raw_indicators = raw_indicators or {}
        combination_data.bar_scores = bar_scores or {}
        combination_data.last_update = datetime.now()

        # Store current price data
        combination_data.current_data = {
            'price': tick.close,
            'timestamp': timestamp,
            'ohlc': [tick.open, tick.high, tick.low, tick.close],
            'volume': tick.volume
        }

        logger.info(
            f"Updated combination {combination_id}: price=${tick.close:.2f}, indicators={len(indicators)}, bars={len(bar_scores or {})}")

        # Send update specific to this combination/card
        self._emit_combination_update(combination_id, combination_data, tick)

        logger.info(f"Emitted update for combination {combination_id}")

    def _get_combination_from_streamer(self, data_streamer: object) -> Optional[str]:
        """Get combination_id from DataStreamer instance"""
        streamer_id = id(data_streamer)
        logger.debug(
            f"Looking for streamer ID {streamer_id} in mappings: {[(id(k), v) for k, v in self.streamer_to_combination.items()]}")
        return self.streamer_to_combination.get(data_streamer)

    def handle_completed_candle(self, symbol: str, candle: TickData) -> None:
        """
        Handle completed candle data for a specific combination
        """

        # Find combination by symbol (temporary solution)
        target_combination_id = None
        for combination_id, combination_data in self.combinations.items():
            if combination_data.combination_info.symbol == symbol:
                target_combination_id = combination_id
                break

        if not target_combination_id:
            logger.warning(f"No combination found for completed candle {symbol}")
            return

        combination_data = self.combinations[target_combination_id]

        candle_data = {
            'timestamp': self._format_timestamp(candle.timestamp),
            'open': candle.open,
            'high': candle.high,
            'low': candle.low,
            'close': candle.close,
            'volume': candle.volume,
            'timeframe': getattr(candle, 'time_increment', '1m')
        }

        # Add to combination's history with size limit
        combination_data.history.append(candle_data)
        if len(combination_data.history) > combination_data.max_history:
            combination_data.history = combination_data.history[-combination_data.max_history:]

        # Send to UI with combination context
        self.socketio.emit('candle_completed', {
            'combination_id': target_combination_id,
            'card_id': combination_data.combination_info.card_id,
            'symbol': symbol,
            'candle': candle_data,
            'history_size': len(combination_data.history)
        })

        logger.debug(
            f"Sent completed candle for combination {target_combination_id}: {candle_data['timeframe']} @ {candle_data['timestamp']}")

    def _emit_combination_update(self, combination_id: str, combination_data: CombinationData,
                                 tick: TickData) -> None:
        """Send comprehensive update for a specific combination to UI"""

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

        logger.info(
            f"EMITTING to browser: {combination_id} ({update_data['symbol']}) @ ${update_data['current_price']:.2f} with {len(update_data['bar_scores'])} bars")

        self.socketio.emit('combination_update', update_data)

        # Add a small delay after each emission to prevent flooding
        import time
        time.sleep(0.1)

    def _format_timestamp(self, timestamp) -> str:
        """Format timestamp for JSON serialization"""
        if isinstance(timestamp, datetime):
            return timestamp.isoformat()
        return str(timestamp)

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