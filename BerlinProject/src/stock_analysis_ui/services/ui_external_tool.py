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

        # Configure history limits
        self.max_history_items = 600

        # Initialize logger
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    # Fix in UIExternalTool.feature_vector method
    # In services/ui_external_tool.py

    def feature_vector(self, fv: np.ndarray, tick):
        """Process feature vector"""
        logger.info(f"UIExternalTool received feature vector for tick: {tick}")

        if not hasattr(tick, 'symbol') or tick.symbol is None:
            logger.warning("Tick data missing symbol information")
            return

        symbol = tick.symbol

        # Initialize data structures for new tickers
        if symbol not in self.ticker_data:
            logger.info(f"Initializing data for new symbol: {symbol}")
            self.ticker_data[symbol] = {}
            self.history[symbol] = []
            self.indicators[symbol] = {}
            self.raw_indicators[symbol] = {}
            self.overall_scores[symbol] = {'bull': 0.0, 'bear': 0.0}

        # Check if this is a completed candle (it will have open/high/low attributes)
        is_completed_candle = hasattr(tick, 'open') and hasattr(tick, 'high') and hasattr(tick, 'low')

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
            'open': getattr(tick, 'open', tick.close),
            'high': getattr(tick, 'high', tick.close),
            'low': getattr(tick, 'low', tick.close),
            'close': getattr(tick, 'close', 0.0),
            'volume': getattr(tick, 'volume', 0),
            'symbol': symbol
        }

        self.ticker_data[symbol] = tick_data

        # Emit update via Socket.IO
        logger.info(f"Emitting ticker_update for {symbol} with price {tick_data['close']}")
        self.socketio.emit('ticker_update', {
            'symbol': symbol,
            'data': tick_data
        })

    def indicator_vector(self, indicators: Dict[str, float], tick, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        """
        Process new indicator results.

        Args:
            indicators: Dictionary of indicator values
            tick: Corresponding tick data
            index: Tick index
            raw_indicators: Optional raw indicator values
        """
        if not hasattr(tick, 'symbol') or tick.symbol is None:
            print(f"UIExternalTool: Warning - Tick data missing symbol information: {tick}")
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

        # Calculate overall scores
        # This could be enhanced with the weights from your monitor model
        bull_indicators = {k: v for k, v in indicators.items() if 'bearish' not in k.lower()}
        bear_indicators = {k: v for k, v in indicators.items() if 'bearish' in k.lower()}

        # Calculate average scores (this should be replaced with weighted calculation)
        bull_score = sum(bull_indicators.values()) / max(len(bull_indicators), 1)
        bear_score = sum(bear_indicators.values()) / max(len(bear_indicators), 1)

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
            'timestamp': timestamp_str  # Include string timestamp
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

    def update_weights(self, weights: Dict[str, float]) -> None:
        """
        Update weights and recalculate scores

        Args:
            weights: Dictionary of indicator weights
        """
        # Recalculate scores for all tickers with new weights
        for symbol in self.indicators:
            # Split indicators into bull and bear
            bull_indicators = {k: v for k, v in self.indicators[symbol].items() if 'bearish' not in k.lower()}
            bear_indicators = {k: v for k, v in self.indicators[symbol].items() if 'bearish' in k.lower()}

            # Filter weights for bull and bear indicators
            bull_weights = {k: v for k, v in weights.items() if k in bull_indicators}
            bear_weights = {k: v for k, v in weights.items() if k in bear_indicators}

            # Calculate weighted scores
            bull_score = self.calculate_weighted_score(bull_indicators, bull_weights)
            bear_score = self.calculate_weighted_score(bear_indicators, bear_weights)

            self.overall_scores[symbol] = {
                'bull': bull_score,
                'bear': bear_score
            }

        # Emit updates for all tickers
        for symbol in self.indicators:
            self.socketio.emit('indicator_update', {
                'symbol': symbol,
                'indicators': self.indicators[symbol],
                'raw_indicators': self.raw_indicators.get(symbol, {}),
                'overall_scores': self.overall_scores[symbol]
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

    def handle_completed_candle(self, symbol: str, candle: TickData) -> None:
        """
        Handle a completed candle for a symbol.

        Args:
            symbol: Symbol the candle belongs to
            candle: The completed TickData candle
        """
        logger.info(f"Handling completed candle for {symbol}: {candle}")

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
        logger.info(f"Emitting completed candle for {symbol}")
        self.socketio.emit('candle_completed', {
            'symbol': symbol,
            'candle': candle_data
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