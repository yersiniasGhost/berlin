import logging
import numpy as np
from typing import Dict, Optional, List, Any
from datetime import datetime
from flask_socketio import SocketIO

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
        self.max_history_items = 100

        # Initialize logger
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    def feature_vector(self, fv: np.ndarray, tick):
        """
        Process a new feature vector.

        Args:
            fv: Feature vector as numpy array
            tick: Corresponding tick data
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

        # Store current tick data
        timestamp = tick.timestamp or datetime.now()
        self.ticker_data[symbol] = {
            'timestamp': timestamp,
            'open': getattr(tick, 'open', 0.0),
            'high': getattr(tick, 'high', 0.0),
            'low': getattr(tick, 'low', 0.0),
            'close': getattr(tick, 'close', 0.0),
            'volume': getattr(tick, 'volume', 0),
            'symbol': symbol
        }

        # Add to history (limited size)
        self.history[symbol].append(self.ticker_data[symbol].copy())
        if len(self.history[symbol]) > self.max_history_items:
            self.history[symbol].pop(0)

        # Emit update via Socket.IO
        self.socketio.emit('ticker_update', {
            'symbol': symbol,
            'data': self.ticker_data[symbol]
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

        # Emit update via Socket.IO
        self.socketio.emit('indicator_update', {
            'symbol': symbol,
            'indicators': self.indicators[symbol],
            'raw_indicators': self.raw_indicators[symbol],
            'overall_scores': self.overall_scores[symbol]
        })

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
        return {
            'tickers': list(self.ticker_data.keys()),
            'data': self.ticker_data,
            'indicators': self.indicators,
            'overall_scores': self.overall_scores,
            'history': {symbol: self.history[symbol][-20:] for symbol in self.history}  # Last 20 items
        }

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