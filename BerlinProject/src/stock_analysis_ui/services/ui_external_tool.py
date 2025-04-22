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

    def indicator_vector(self, indicators: Dict[str, float], tick, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        """
        Process new indicator results.
        Only update indicators on completed candles.
        """
        if not hasattr(tick, 'symbol') or tick.symbol is None:
            return

        # Only proceed for completed candles
        is_completed_candle = (hasattr(tick, 'open') and hasattr(tick, 'high') and
                               hasattr(tick, 'low') and hasattr(tick, 'close') and
                               not getattr(tick, 'is_current', False))

        if not is_completed_candle:
            return

        symbol = tick.symbol

        # Initialize data structures if needed
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
        bull_indicators = {k: v for k, v in indicators.items() if 'bear' not in k.lower()}
        bear_indicators = {k: v for k, v in indicators.items() if 'bear' in k.lower()}

        # Apply weights
        bull_score = self.calculate_weighted_score(bull_indicators, self.weights.get(symbol, {}))
        bear_score = self.calculate_weighted_score(bear_indicators, self.weights.get(symbol, {}))

        self.overall_scores[symbol] = {
            'bull': bull_score,
            'bear': bear_score
        }

        # Prepare indicator details with the exact same format as test_initialization_run
        indicator_details = {}
        if raw_indicators:
            for name, value in indicators.items():
                indicator_details[name] = {
                    'value': value,
                    'raw_value': raw_indicators.get(name),
                }

                # Add transformation info like in test_initialization_run
                if name in raw_indicators and isinstance(raw_indicators[name], (int, float)) and value != 0:
                    raw_value = raw_indicators[name]
                    if raw_value != 0:
                        ratio = value / raw_value
                        indicator_details[name]['ratio'] = ratio
                        indicator_details[name]['decay'] = ratio if abs(value) < abs(raw_value) else 1.0
                        indicator_details[name]['strength_pct'] = int(ratio * 100) if ratio < 1 else 100

        # Emit update with detailed indicator information
        self.socketio.emit('indicator_update', {
            'symbol': symbol,
            'indicators': self.indicators[symbol],
            'raw_indicators': self.raw_indicators[symbol],
            'overall_scores': self.overall_scores[symbol],
            'indicator_details': indicator_details,  # Added this field with detailed info
            'timestamp': tick.timestamp.isoformat() if isinstance(tick.timestamp, datetime) else str(tick.timestamp)
        })

        # Log the information similar to test_initialization_run for debugging
        logger.info(f"Indicator update for {symbol}: {indicators}")
        if raw_indicators:
            logger.info(f"Raw indicator values: {raw_indicators}")
        logger.info(f"Overall scores: Bull={bull_score:.2f}, Bear={bear_score:.2f}")


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

    def handle_completed_candle(self, symbol: str, candle: TickData) -> None:
        """Handle a completed candle with improved history management"""

        # Initialize data structures if needed
        if symbol not in self.ticker_data:
            self.ticker_data[symbol] = {}
            self.history[symbol] = []
            self.indicators[symbol] = {}
            self.raw_indicators[symbol] = {}
            self.overall_scores[symbol] = {'bull': 0.0, 'bear': 0.0}

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

        # Add to history
        self.history[symbol].append(candle_data.copy())

        # Limit history size for performance
        max_history = 1000
        if len(self.history[symbol]) > max_history:
            self.history[symbol] = self.history[symbol][-max_history:]

        # Emit candle completion event
        self.socketio.emit('candle_completed', {
            'symbol': symbol,
            'candle': candle_data
        })

        # Log candle info (similar to test_initialization_run)
        logger.info(f"Completed candle for {symbol} @ {timestamp_str}: "
                    f"OHLC({candle.open:.2f},{candle.high:.2f},{candle.low:.2f},{candle.close:.2f})")

        # Update ticker data
        self.ticker_data[symbol] = candle_data.copy()

        # Emit ticker update
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