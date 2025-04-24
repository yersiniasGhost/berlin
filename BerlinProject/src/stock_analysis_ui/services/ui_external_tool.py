import json
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
        """
        self.socketio = socketio
        self.ticker_data = {}  # Store latest data for each ticker
        self.history = {}  # Store historical data (limited amount)
        self.indicators = {}  # Store indicator results by ticker
        self.raw_indicators = {}  # Store raw indicator values by ticker
        self.overall_scores = {}  # Store overall bull/bear scores by ticker
        self.weights = {}  # Store weights for each ticker's indicators

        # Added for tracking progress similar to test_initialization_run
        self.initial_history_size = 0
        self.current_history_size = 0
        self.last_checked_size = 0
        self.data_streamer_ref = None  # Will hold reference to data_streamer

        # Configure history limits
        self.max_history_items = 600

        # Initialize logger
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    def set_data_streamer_ref(self, data_streamer):
        """Store a reference to the data_streamer for accessing history"""
        self.data_streamer_ref = data_streamer

    def set_initial_history_size(self, size):
        """Set the initial history size for progress tracking"""
        self.initial_history_size = size
        self.last_checked_size = size
        logger.info(f"Set initial history size to {size}")

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

        # Check if this is a completed candle
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

        # Track progress
        self._check_progress()

    def indicator_vector(self, indicators, tick, index, raw_indicators=None, combination_id=None):
        """Process indicator results with combination ID"""
        if not hasattr(tick, 'symbol') or tick.symbol is None:
            return

        symbol = tick.symbol

        # Use combination_id if provided, otherwise fall back to just symbol
        identifier = combination_id or symbol

        # Initialize data structures if needed
        if identifier not in self.ticker_data:
            self.ticker_data[identifier] = {}
            self.history[identifier] = []
            self.indicators[identifier] = {}
            self.raw_indicators[identifier] = {}
            self.overall_scores[identifier] = {'bull': 0.0, 'bear': 0.0}

        # Store indicator results for this combination
        self.indicators[identifier] = indicators.copy()
        if raw_indicators:
            self.raw_indicators[identifier] = raw_indicators.copy()

        # Calculate overall scores
        bull_indicators = {k: v for k, v in indicators.items() if 'bear' not in k.lower()}
        bear_indicators = {k: v for k, v in indicators.items() if 'bear' in k.lower()}

        # Use weights specific to this combination
        weights = self.weights.get(identifier, {})
        bull_score = self.calculate_weighted_score(bull_indicators, weights)
        bear_score = self.calculate_weighted_score(bear_indicators, weights)

        self.overall_scores[identifier] = {
            'bull': bull_score,
            'bear': bear_score
        }

        # Emit update with combination ID
        self.socketio.emit('indicator_update', {
            'symbol': symbol,
            'combination_id': identifier,
            'indicators': self.indicators[identifier],
            'raw_indicators': self.raw_indicators[identifier],
            'overall_scores': self.overall_scores[identifier],
            'timestamp': tick.timestamp.isoformat() if isinstance(tick.timestamp, datetime) else str(tick.timestamp)
        })

    def _check_progress(self, is_indicator_update=False):
        """
        Check progress and emit updates when needed.
        Similar to the print_progress_report in test_initialization_run
        """
        if not self.data_streamer_ref:
            return

        try:
            history = self.data_streamer_ref.preprocessor.history
            self.current_history_size = len(history)

            # Only report when size changes
            should_report = self.current_history_size > self.last_checked_size

            if should_report or is_indicator_update:
                # Calculate progress stats
                added_ticks = self.current_history_size - self.initial_history_size

                # Build progress report
                progress_data = {
                    'initial_history_size': self.initial_history_size,
                    'current_history_size': self.current_history_size,
                    'added_ticks': added_ticks
                }

                # Add time range if available
                if history and len(history) > 0:
                    first_tick = history[0]
                    last_tick = history[-1]
                    progress_data['time_range'] = {
                        'start': first_tick.timestamp.isoformat() if isinstance(first_tick.timestamp,
                                                                                datetime) else str(
                            first_tick.timestamp),
                        'end': last_tick.timestamp.isoformat() if isinstance(last_tick.timestamp, datetime) else str(
                            last_tick.timestamp)
                    }

                # Add indicator info if this is an indicator update
                if is_indicator_update:
                    # Get the ticker symbol
                    symbol = next(iter(self.indicators))

                    # Add indicator info
                    if symbol in self.indicators and symbol in self.raw_indicators:
                        progress_data['indicators'] = {
                            'latest': self.indicators[symbol],
                            'raw': self.raw_indicators[symbol]
                        }

                        # Add transformation analysis
                        progress_data['indicator_analysis'] = {}

                        for name, value in self.indicators[symbol].items():
                            if name in self.raw_indicators[symbol]:
                                raw_value = self.raw_indicators[symbol][name]
                                if isinstance(raw_value, (int, float)) and isinstance(value, (int, float)):
                                    if raw_value != 0:
                                        ratio = value / raw_value
                                        progress_data['indicator_analysis'][name] = {
                                            'scaling_factor': ratio,
                                            'strength_percentage': ratio * 100 if ratio < 1 else 100
                                        }

                # Add recently added ticks
                if added_ticks > 0:
                    recent_ticks = []
                    for i in range(max(self.initial_history_size, self.current_history_size - 3),
                                   self.current_history_size):
                        if i < len(history):
                            tick = history[i]
                            recent_ticks.append({
                                'symbol': tick.symbol,
                                'timestamp': tick.timestamp.isoformat() if isinstance(tick.timestamp,
                                                                                      datetime) else str(
                                    tick.timestamp),
                                'ohlc': [tick.open, tick.high, tick.low, tick.close]
                            })

                    progress_data['recent_ticks'] = recent_ticks

                # Emit progress report
                self.socketio.emit('progress_report', progress_data)

                # Update last checked size
                self.last_checked_size = self.current_history_size

        except Exception as e:
            logger.error(f"Error checking progress: {e}")

    def handle_completed_candle(self, symbol: str, candle: TickData, combination_id=None) -> None:
        """Handle a completed candle with improved history management"""

        # Use combination_id if provided, otherwise fallback to symbol
        identifier = combination_id or symbol

        # Initialize data structures if needed
        if identifier not in self.ticker_data:
            self.ticker_data[identifier] = {}
            self.history[identifier] = []
            self.indicators[identifier] = {}
            self.raw_indicators[identifier] = {}
            self.overall_scores[identifier] = {'bull': 0.0, 'bear': 0.0}

        # Format timestamp
        timestamp = candle.timestamp
        timestamp_str = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)

        # Create candle data
        candle_data = {
            'timestamp': timestamp_str,
            'open': candle.open,
            'high': candle.high,
            'low': candle.low,
            'close': candle.close,
            'volume': candle.volume,
            'symbol': symbol
        }

        # Add to history using identifier instead of symbol
        self.history[identifier].append(candle_data.copy())

        # Limit history size for performance
        max_history = 1000
        if len(self.history[identifier]) > max_history:
            self.history[identifier] = self.history[identifier][-max_history:]

        # Update the ticker_data with candle information
        self.ticker_data[identifier].update(candle_data)

        # Print debug info
        print(f"DEBUG - Ticker data for {symbol} updated with candle: {self.ticker_data[identifier]}")

        # Emit candle completion event with combination_id
        self.socketio.emit('candle_completed', {
            'symbol': symbol,
            'combination_id': identifier,
            'candle': candle_data
        })

    def calculate_weighted_score(self, indicators, weights):
        """
        Calculate weighted score for indicators.

        Args:
            indicators: Dictionary of indicator values
            weights: Dictionary of weights for indicators

        Returns:
            float: Weighted score between 0 and 1
        """
        if not indicators:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0

        for name, value in indicators.items():
            # Get weight for this indicator (default to 1.0)
            weight = weights.get(name, 1.0)
            weighted_sum += value * weight
            total_weight += weight

        # Avoid division by zero
        if total_weight == 0:
            return 0.0

        # Return normalized score
        return weighted_sum / total_weight

    def update_weights(self, weights, combination_id=None):
        """
        Update the weights used for calculating overall scores.

        Args:
            weights: Dictionary of indicator weights
            combination_id: Optional identifier for specific symbol-monitor combination
        """
        # If combination_id is provided, update weights just for that combination
        if combination_id:
            self.weights[combination_id] = weights
        else:
            # Otherwise, update weights for all symbols/combinations
            for symbol in self.ticker_data:
                self.weights[symbol] = weights

        # Recalculate overall scores with new weights
        for identifier in self.indicators:
            # Skip if no indicators
            if not self.indicators[identifier]:
                continue

            # Split indicators into bull and bear
            bull_indicators = {k: v for k, v in self.indicators[identifier].items() if 'bear' not in k.lower()}
            bear_indicators = {k: v for k, v in self.indicators[identifier].items() if 'bear' in k.lower()}

            # Get weights for this specific identifier
            identifier_weights = self.weights.get(identifier, weights)

            # Calculate weighted scores
            bull_score = self.calculate_weighted_score(bull_indicators, identifier_weights)
            bear_score = self.calculate_weighted_score(bear_indicators, identifier_weights)

            self.overall_scores[identifier] = {
                'bull': bull_score,
                'bear': bear_score
            }

        logger.info(f"Updated weights: {weights} for combination: {combination_id}")
        return True

    def clear_data(self) -> None:
        """
        Clear all stored data
        """
        self.ticker_data = {}
        self.history = {}
        self.indicators = {}
        self.raw_indicators = {}
        self.overall_scores = {}

        # Emit clear eventF
        self.socketio.emit('clear_data')