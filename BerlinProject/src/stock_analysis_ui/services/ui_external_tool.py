import logging
from typing import Dict, Optional, List
from datetime import datetime
from flask_socketio import SocketIO
from collections import defaultdict

from environments.tick_data import TickData

logger = logging.getLogger('UIExternalTool')


class UIExternalTool:
    """Simplified UI external tool for real-time data streaming to web interface"""

    def __init__(self, socketio: SocketIO, monitor_config):
        self.socketio: SocketIO = socketio
        self.monitor_config = monitor_config

        # Current data storage
        self.current_data: Dict[str, Dict] = defaultdict(dict)
        self.indicators: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.bar_scores: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.raw_indicators: Dict[str, Dict[str, float]] = defaultdict(dict)

        # Historical data (limited size)
        self.history: Dict[str, List[Dict]] = defaultdict(list)
        self.max_history: int = 1000

    def feature_vector(self, fv, tick: TickData) -> None:
        """Handle feature vector updates (not used in current system)"""
        pass

    def indicator_vector(self, indicators: Dict[str, float], tick: Optional[TickData],
                         index: int, raw_indicators: Optional[Dict[str, float]] = None,
                         bar_scores: Optional[Dict[str, float]] = None) -> None:
        """Process indicator updates and send to UI"""

        if not tick or not hasattr(tick, 'symbol'):
            return

        symbol: str = tick.symbol
        timestamp: str = self._format_timestamp(tick.timestamp)

        # Store indicator data
        self.indicators[symbol] = indicators
        self.raw_indicators[symbol] = raw_indicators or {}
        self.bar_scores[symbol] = bar_scores or {}

        # Store current price data
        self.current_data[symbol] = {
            'price': tick.close,
            'timestamp': timestamp,
            'ohlc': [tick.open, tick.high, tick.low, tick.close],
            'volume': tick.volume
        }

        # Send comprehensive update to UI
        self._emit_indicator_update(symbol, indicators, bar_scores, raw_indicators, tick)

        logger.info(f"Sent indicator update for {symbol}: {len(indicators)} indicators, {len(bar_scores or {})} bars")

    def handle_completed_candle(self, symbol: str, candle: TickData) -> None:
        """Handle completed candle data"""

        candle_data: Dict = {
            'timestamp': self._format_timestamp(candle.timestamp),
            'open': candle.open,
            'high': candle.high,
            'low': candle.low,
            'close': candle.close,
            'volume': candle.volume,
            'timeframe': getattr(candle, 'time_increment', '1m')
        }

        # Add to history with size limit
        self.history[symbol].append(candle_data)
        if len(self.history[symbol]) > self.max_history:
            self.history[symbol] = self.history[symbol][-self.max_history:]

        # Send to UI
        self.socketio.emit('candle_completed', {
            'symbol': symbol,
            'candle': candle_data,
            'history_size': len(self.history[symbol])
        })

        logger.info(f"Sent completed candle for {symbol}: {candle_data['timeframe']} @ {candle_data['timestamp']}")

    def _emit_indicator_update(self, symbol: str, indicators: Dict[str, float],
                               bar_scores: Optional[Dict[str, float]],
                               raw_indicators: Optional[Dict[str, float]],
                               tick: TickData) -> None:
        """Send comprehensive indicator update to UI"""

        update_data: Dict = {
            'symbol': symbol,
            'timestamp': self._format_timestamp(tick.timestamp),
            'indicators': indicators,
            'bar_scores': bar_scores or {},
            'raw_indicators': raw_indicators or {},
            'current_price': tick.close,
            'current_ohlc': [tick.open, tick.high, tick.low, tick.close],
            'volume': tick.volume
        }

        self.socketio.emit('indicator_update', update_data)

    def _format_timestamp(self, timestamp) -> str:
        """Format timestamp for JSON serialization"""
        if isinstance(timestamp, datetime):
            return timestamp.isoformat()
        return str(timestamp)

    def get_current_data(self, symbol: str) -> Dict:
        """Get current data for a symbol"""
        return {
            'current': self.current_data.get(symbol, {}),
            'indicators': self.indicators.get(symbol, {}),
            'bar_scores': self.bar_scores.get(symbol, {}),
            'raw_indicators': self.raw_indicators.get(symbol, {}),
            'history': self.history.get(symbol, [])
        }

    def get_all_data(self) -> Dict:
        """Get all current data for all symbols"""
        all_symbols: List[str] = list(set(
            list(self.current_data.keys()) +
            list(self.indicators.keys()) +
            list(self.history.keys())
        ))

        return {
            'symbols': all_symbols,
            'data': {symbol: self.get_current_data(symbol) for symbol in all_symbols}
        }

    def send_status_update(self) -> None:
        """Send general status update to UI"""
        status: Dict = {
            'timestamp': datetime.now().isoformat(),
            'active_symbols': list(self.current_data.keys()),
            'total_indicators': sum(len(ind) for ind in self.indicators.values()),
            'total_history': sum(len(hist) for hist in self.history.values())
        }

        self.socketio.emit('status_update', status)

    def clear_data(self) -> None:
        """Clear all stored data"""
        self.current_data.clear()
        self.indicators.clear()
        self.bar_scores.clear()
        self.raw_indicators.clear()
        self.history.clear()

        self.socketio.emit('data_cleared', {'timestamp': datetime.now().isoformat()})
        logger.info("Cleared all UI data.")