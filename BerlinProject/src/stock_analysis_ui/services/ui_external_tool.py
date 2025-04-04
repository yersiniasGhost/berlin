import logging
import numpy as np
from typing import Dict, Optional, List, Any
from datetime import datetime
from flask_socketio import SocketIO

from environments.tick_data import TickData

logger = logging.getLogger('UIExternalTool')


class UIExternalTool:
    """
    External Tool implementation for the UI.
    Processes data from indicators and sends to the UI via Socket.IO.
    """

    def __init__(self, socketio: SocketIO):
        """
        Initialize the UI external tool.

        Args:
            socketio: Flask-SocketIO instance for real-time updates
        """
        self.socketio = socketio
        self.ticker_data = {}  # Store latest data for each ticker
        self.history = {}  # Store historical data (limited amount)
        self.indicators = {}  # Store indicator results by ticker
        self.raw_indicators = {}  # Store raw indicator values by ticker
        self.overall_scores = {}  # Store overall bull/bear scores by ticker
        self.weights = {}  # Store weights for each ticker's indicators

        # Configure history limits
        self.max_history_items = 600

        # Initialize logger
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    def feature_vector(self, fv: np.ndarray, tick):
        """Process feature vector"""
        if not hasattr(tick, 'symbol') or tick.symbol is None:
            return

        symbol = tick.symbol

        # Initialize data structures for new tickers
        if symbol not in self.ticker_data:
            self.ticker_data[symbol] = {}
            self.history[symbol] = []
            self.indicators[symbol] = {}
            self.raw_indicators[symbol] = {}
            self.overall_scores[symbol] = {'bull': 0.0, 'bear': 0.0}

        # Check if this is a completed candle (it will have open/high/low attributes)
        is_completed_candle = (hasattr(tick, 'open') and hasattr(tick, 'high') and
                               hasattr(tick, 'low') and not getattr(tick, 'is_current', False))

        # If it's a completed candle, handle it differently
        if is_completed_candle:
            # Handle as a completed candle
            self.handle_completed_candle(symbol, tick)
            return

        # Store current tick data (for regular ticks)
        timestamp = getattr(tick, 'timestamp', datetime.now())

        # Convert datetime to string for JSON serialization
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.isoformat()
        else:
            timestamp_str = str(timestamp)

        tick_data = {
            'timestamp': timestamp_str,
            'open': getattr(tick, 'open', getattr(tick, 'close', 0.0)),
            'high': getattr(tick, 'high', getattr(tick, 'close', 0.0)),
            'low': getattr(tick, 'low', getattr(tick, 'close', 0.0)),
            'close': getattr(tick, 'close', 0.0),
            'volume': getattr(tick, 'volume', 0),
            'symbol': symbol,
            'is_current': getattr(tick, 'is_current', False)
        }

        self.ticker_data[symbol] = tick_data

        # Emit update via Socket.IO
        self.socketio.emit('ticker_update', {
            'symbol': symbol,
            'data': tick_data
        })

        # If this is a current (in-progress) candle, also emit a special event
        if getattr(tick, 'is_current', False):
            self.socketio.emit('current_candle_update', {
                'symbol': symbol,
                'candle': tick_data
            })

    def indicator_vector(self, indicators: Dict[str, float], tick, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        """
        Process new indicator results with proper weight handling.

        Args:
            indicators: Dictionary of indicator values
            tick: Corresponding tick data
            index: Tick index
            raw_indicators: Optional raw indicator values
        """
        if not hasattr(tick, 'symbol') or tick.symbol is None:
            logger.warning("Tick data missing symbol information")
            return

        symbol = tick.symbol

        # Initialize data structures for new tickers
        if symbol not in self.ticker_data:
            self.ticker_data[symbol] = {}
            self.history[symbol] = []
            self.indicators[symbol] = {}
            self.raw_indicators[symbol] = {}
            self.overall_scores[symbol] = {'bull': 0.0, 'bear': 0.0}

        # Store indicator results
        self.indicators[symbol] = indicators.copy()

        if raw_indicators:
            self.raw_indicators[symbol] = raw_indicators.copy()

        # Calculate overall scores using weights
        # Split indicators into bullish and bearish
        bull_indicators = {k: v for k, v in indicators.items() if 'bear' not in k.lower()}
        bear_indicators = {k: v for k, v in indicators.items() if 'bear' in k.lower()}

        # Apply weights (from monitor config)
        bull_score = self.calculate_weighted_score(bull_indicators, self.weights.get(symbol, {}))
        bear_score = self.calculate_weighted_score(bear_indicators, self.weights.get(symbol, {}))

        self.overall_scores[symbol] = {
            'bull': bull_score,
            'bear': bear_score
        }

        # Get a timestamp for the update
        timestamp = getattr(tick, 'timestamp', None) or datetime.now()

        # Convert datetime to string for JSON serialization
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.isoformat()
        else:
            timestamp_str = str(timestamp)

        # Create a JSON-serializable update object
        update_data = {
            'symbol': symbol,
            'indicators': self.indicators[symbol],
            'raw_indicators': self.raw_indicators[symbol],
            'overall_scores': self.overall_scores[symbol],
            'timestamp': timestamp_str
        }

        # Emit update via Socket.IO
        self.socketio.emit('indicator_update', update_data)

    def calculate_weighted_score(self, indicators: Dict[str, float], weights: Dict[str, float]) -> float:
        """
        Calculate weighted score from indicators and weights

        Args:
            indicators: Dictionary of indicator values
            weights: Dictionary of indicator weights

        Returns:
            Weighted score
        """
        if not indicators or not weights:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0

        for name, value in indicators.items():
            weight = weights.get(name, 1.0)
            weighted_sum += value * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    def update_weights(self, *args, **kwargs):
        """
        Update weights for indicators - flexible method to handle different call patterns
        """
        weights = None
        symbol = None

        # Handle different ways this method could be called
        if len(args) == 1 and isinstance(args[0], dict):
            # Called as update_weights(weights_dict)
            weights = args[0]
        elif len(args) == 2 and isinstance(args[1], dict):
            # Called as update_weights(symbol, weights_dict)
            symbol = args[0]
            weights = args[1]
        elif 'weights' in kwargs:
            # Called with keyword arguments
            weights = kwargs['weights']
            symbol = kwargs.get('symbol')

        if not weights:
            logger.error("No weights provided to update_weights")
            return

        logger.info(f"Updating weights: symbol={symbol}, weights={weights}")

        if symbol:
            # Update weights for specific symbol
            self.weights[symbol] = weights
        else:
            # Update weights for all symbols
            for sym in self.ticker_data:
                self.weights[sym] = weights

        # Recalculate scores if we have indicators
        for sym in self.indicators:
            if sym not in self.weights:
                self.weights[sym] = weights

            # Split indicators into bull and bear
            bull_indicators = {k: v for k, v in self.indicators[sym].items() if 'bear' not in k.lower()}
            bear_indicators = {k: v for k, v in self.indicators[sym].items() if 'bear' in k.lower()}

            # Calculate weighted scores
            bull_score = self.calculate_weighted_score(bull_indicators, self.weights[sym])
            bear_score = self.calculate_weighted_score(bear_indicators, self.weights[sym])

            self.overall_scores[sym] = {
                'bull': bull_score,
                'bear': bear_score
            }

            # Emit updates for this symbol
            self.socketio.emit('indicator_update', {
                'symbol': sym,
                'indicators': self.indicators[sym],
                'raw_indicators': self.raw_indicators.get(sym, {}),
                'overall_scores': self.overall_scores[sym]
            })

    def present_sample(self, sample: dict, index: int) -> None:
        """Handle sample presentation"""
        # Not used for this UI implementation
        pass

    def reset_next_sample(self) -> None:
        """Reset for next sample"""
        # Clear historical data but keep current tick data
        for symbol in self.history:
            self.history[symbol] = []

        # Emit reset event
        self.socketio.emit('reset_samples')

    def get_ticker_data(self) -> Dict[str, Any]:
        """
        Get all ticker data for API responses

        Returns:
            Dictionary with all ticker data
        """
        # Create a copy to ensure JSON serialization works
        result = {
            'tickers': list(self.ticker_data.keys()),
            'data': {},
            'indicators': {},
            'overall_scores': {},
            'history': {}
        }

        # Add more detailed logging
        logger.info(f"get_ticker_data called, have {len(self.ticker_data)} symbols")
        logger.info(f"History lengths: {', '.join([f'{s}: {len(h)}' for s, h in self.history.items()])}")

        # Convert all data to JSON-serializable format
        for symbol in self.ticker_data:
            # Copy ticker data
            result['data'][symbol] = self.ticker_data[symbol].copy()

            # Copy indicators and overall scores
            result['indicators'][symbol] = self.indicators.get(symbol, {}).copy()
            result['overall_scores'][symbol] = self.overall_scores.get(symbol, {'bull': 0.0, 'bear': 0.0}).copy()

            # Copy recent history (all items)
            result['history'][symbol] = [item.copy() for item in self.history.get(symbol, [])]
            logger.info(f"Returning {len(result['history'][symbol])} historical candles for {symbol}")

        return result

    # In src/stock_analysis_ui/services/ui_external_tool.py, update handle_completed_candle

    def handle_completed_candle(self, symbol: str, candle: TickData) -> None:
        """
        Handle a completed candle for a symbol.
        """
        # Make sure we have data structures initialized
        if symbol not in self.ticker_data:
            self.ticker_data[symbol] = {}
            self.history[symbol] = []
            self.indicators[symbol] = {}
            self.raw_indicators[symbol] = {}
            self.overall_scores[symbol] = {'bull': 0.0, 'bear': 0.0}

        # Convert datetime to string for JSON serialization
        timestamp = candle.timestamp
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.isoformat()
        else:
            timestamp_str = str(timestamp)

        # Create JSON-serializable candle data
        candle_data = {
            'timestamp': timestamp_str,
            'open': candle.open,
            'high': candle.high,
            'low': candle.low,
            'close': candle.close,
            'volume': candle.volume,
            'symbol': symbol
        }

        # Add to history
        self.history[symbol].append(candle_data.copy())
        if len(self.history[symbol]) > self.max_history_items:
            self.history[symbol].pop(0)

        # Emit candle update via Socket.IO
        self.socketio.emit('candle_completed', {
            'symbol': symbol,
            'candle': candle_data
        })

        # Also emit a ticker_update event to ensure the UI is updated
        self.socketio.emit('ticker_update', {
            'symbol': symbol,
            'data': candle_data
        })

    def clear_data(self) -> None:
        """
        Clear all stored data
        """
        self.ticker_data = {}
        self.history = {}
        self.indicators = {}
        self.raw_indicators = {}
        self.overall_scores = {}

        # Emit clear event
        self.socketio.emit('clear_data')