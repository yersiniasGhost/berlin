import logging
import threading
import json
import time
import numpy as np
from typing import Dict, Optional, List, Any
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory

from data_streamer.external_tool import ExternalTool
from environments.tick_data import TickData


class UIExternalTool(ExternalTool):
    """
    ExternalTool implementation for the UI.
    Exposes a Flask web server to visualize market data.
    """

    def __init__(self, host='127.0.0.1', port=5000):
        """
        Initialize the UI external tool.

        Args:
            host: Host to run the Flask server on
            port: Port to run the Flask server on
        """
        self.logger = logging.getLogger('UIExternalTool')
        self.logger.setLevel(logging.INFO)

        # Set up data storage
        self.symbols_data = {}  # To store data for each symbol
        self.active_symbols = set()  # Track which symbols are active
        self.data_lock = threading.Lock()  # Lock for thread-safe operations

        # Reference to data_streamer for callbacks
        self.data_streamer = None

        # Set up Flask app
        self.app = Flask(__name__)
        self.host = host
        self.port = port

        # Register routes
        self._setup_routes()

        # Start Flask in a separate thread
        self.flask_thread = threading.Thread(target=self._run_flask, daemon=True)
        self.flask_thread.start()

        # Keep track of the last processed indicator results
        self.last_indicators = {}

        # Debug flag to print more information
        self.debug = True

    def _setup_routes(self):
        """Set up the Flask routes"""

        @self.app.route('/')
        def index():
            return render_template('index.html')

        @self.app.route('/static/<path:path>')
        def static_files(path):
            return send_from_directory('static', path)

        @self.app.route('/subscribe', methods=['POST'])
        def subscribe():
            data = request.json
            symbols = data.get('symbols', [])

            # Validate - max 4 symbols
            if len(symbols) > 4:
                return jsonify({'error': 'Maximum 4 symbols allowed'}), 400

            self.logger.info(f"Subscribing to symbols: {symbols}")

            with self.data_lock:
                # Clear previous data if changing symbols
                self.symbols_data.clear()
                self.active_symbols.clear()

                # Add new symbols
                for symbol in symbols:
                    symbol = symbol.upper()
                    self.active_symbols.add(symbol)
                    self.symbols_data[symbol] = []

                if self.debug:
                    print(f"UI subscribed to symbols: {self.active_symbols}")
                    print(f"symbols_data keys: {list(self.symbols_data.keys())}")

            # Update the data_streamer's symbols if available
            if self.data_streamer and hasattr(self.data_streamer, 'data_link'):
                data_link = self.data_streamer.data_link
                if hasattr(data_link, 'symbols'):
                    old_symbols = data_link.symbols
                    data_link.symbols = list(self.active_symbols)
                    print(f"Updated data_link symbols from {old_symbols} to {data_link.symbols}")

                # Force re-subscribe if it's a Schwab link
                if hasattr(data_link, 'client') and hasattr(data_link.client, 'subscribe_quotes'):
                    try:
                        print(f"Re-subscribing to quotes for: {list(self.active_symbols)}")
                        data_link.client.subscribe_quotes(list(self.active_symbols), data_link._handle_quote_data)
                        data_link.client.subscribe_charts(list(self.active_symbols), data_link._handle_chart_data)
                    except Exception as e:
                        print(f"Error re-subscribing: {e}")

            return jsonify({
                'success': True,
                'message': f'Subscribed to {len(self.active_symbols)} symbols'
            })

        @self.app.route('/data/<symbol>')
        def get_data(symbol):
            symbol = symbol.upper()
            timeframe = request.args.get('timeframe', '1m')

            if self.debug:
                print(f"UI request for {symbol}, symbols_data keys: {list(self.symbols_data.keys())}")
                print(f"Active symbols: {self.active_symbols}")

            with self.data_lock:
                # If symbol not in active_symbols, add it
                if symbol not in self.active_symbols:
                    self.active_symbols.add(symbol)
                    print(f"Added {symbol} to active_symbols")

                if symbol in self.symbols_data and self.symbols_data[symbol]:
                    # Get aggregated data based on timeframe
                    data = self.symbols_data[symbol]
                    if self.debug:
                        print(f"Returning {len(data)} data points for {symbol}")
                    return jsonify(data)
                else:
                    self.logger.info(f"No data found for {symbol}")
                    if self.debug:
                        print(f"No data found for {symbol} in {list(self.symbols_data.keys())}")
                    return jsonify([])

        @self.app.route('/status')
        def get_status():
            with self.data_lock:
                status = {
                    'connected': True,  # We're always "connected" in this implementation
                    'active_symbols': list(self.active_symbols),
                    'data_counts': {symbol: len(data) for symbol, data in self.symbols_data.items()},
                    'indicators': self.last_indicators
                }
                return jsonify(status)

        @self.app.route('/indicators')
        def get_indicators():
            return jsonify(self.last_indicators)

        @self.app.route('/debug')
        def debug_info():
            debug_data = {
                'active_symbols': list(self.active_symbols),
                'symbols_data_keys': list(self.symbols_data.keys()),
                'symbols_data_counts': {k: len(v) for k, v in self.symbols_data.items()},
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            return jsonify(debug_data)

    def _run_flask(self):
        """Run the Flask app in a separate thread"""
        self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)

    def feature_vector(self, fv: np.ndarray, tick: TickData) -> None:
        """
        Process a new feature vector.

        Args:
            fv: The feature vector as a numpy array
            tick: The corresponding tick data
        """
        if self.debug:
            print(f"feature_vector called with tick: {tick}")
            print(f"Active symbols: {self.active_symbols}")

        # If we don't have active symbols, there's nothing to do
        if not self.active_symbols:
            if self.debug:
                print("No active symbols, skipping")
            return

        # We need to associate this tick with a symbol
        # Since we're using symbol_idx in day_index, we'll use that
        # For simplicity, just use the first active symbol for now
        symbol = list(self.active_symbols)[0]

        # Convert feature vector to a list for JSON serialization
        fv_list = fv.tolist() if isinstance(fv, np.ndarray) else fv

        # Create a data point from the tick data
        with self.data_lock:
            # Get timestamp, default to current time if not available
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if hasattr(tick, 'timestamp') and tick.timestamp and isinstance(tick.timestamp,
                                                                            (int, float)) and tick.timestamp > 0:
                try:
                    timestamp = datetime.fromtimestamp(tick.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass  # Use default timestamp if conversion fails

            data_point = {
                'timestamp': timestamp,
                'open': tick.open if hasattr(tick, 'open') and tick.open else 0.0,
                'high': tick.high if hasattr(tick, 'high') and tick.high else 0.0,
                'low': tick.low if hasattr(tick, 'low') and tick.low else 0.0,
                'close': tick.close if hasattr(tick, 'close') and tick.close else 0.0,
                'volume': tick.volume if hasattr(tick, 'volume') and tick.volume else 0,
                'feature_vector': fv_list
            }

            # Store the data point
            if symbol in self.symbols_data:
                self.symbols_data[symbol].append(data_point)
                if self.debug:
                    print(f"Added data point for {symbol}, now have {len(self.symbols_data[symbol])} points")
            else:
                self.symbols_data[symbol] = [data_point]
                if self.debug:
                    print(f"Created new data array for {symbol}")

    def indicator_vector(self, indicators: Dict[str, float], tick: TickData, index: int,
                         raw_indicators: Optional[Dict[str, float]] = None) -> None:
        """
        Process new indicator results.

        Args:
            indicators: Dictionary of indicator values
            tick: The corresponding tick data
            index: The tick index
            raw_indicators: Optional raw indicator values
        """
        if self.debug:
            print(f"indicator_vector called with indicators: {indicators}")
            print(f"Active symbols: {self.active_symbols}")

        # If we don't have active symbols, there's nothing to do
        if not self.active_symbols:
            return

        # Since we're using symbol_idx in day_index, just use the first active symbol
        symbol = list(self.active_symbols)[0]

        # Store the indicator results
        with self.data_lock:
            # Get timestamp, default to current time if not available
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if hasattr(tick, 'timestamp') and tick.timestamp and isinstance(tick.timestamp,
                                                                            (int, float)) and tick.timestamp > 0:
                try:
                    timestamp = datetime.fromtimestamp(tick.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass  # Use default timestamp if conversion fails

            self.last_indicators = {
                'timestamp': timestamp,
                'symbol': symbol,
                'indicators': indicators,
                'raw_indicators': raw_indicators or {}
            }

            # Add indicators to the corresponding data point if it exists
            if symbol in self.symbols_data and self.symbols_data[symbol]:
                # Find the matching data point by timestamp or add to the latest
                matched = False
                for point in reversed(self.symbols_data[symbol]):
                    if point['timestamp'] == timestamp:
                        point['indicators'] = indicators
                        if raw_indicators:
                            point['raw_indicators'] = raw_indicators
                        matched = True
                        break

                # If no match found, add to the latest point
                if not matched and self.symbols_data[symbol]:
                    latest = self.symbols_data[symbol][-1]
                    latest['indicators'] = indicators
                    if raw_indicators:
                        latest['raw_indicators'] = raw_indicators

    def present_sample(self, sample: dict, index: int):
        """
        Process a sample when it's presented.

        Args:
            sample: The sample data
            index: The sample index
        """
        if self.debug:
            print(f"present_sample called with sample index: {index}")

    def reset_next_sample(self):
        """Reset state when moving to the next sample"""
        if self.debug:
            print("reset_next_sample called")

    def add_direct_data_point(self, symbol: str, data_point: Dict[str, Any]):
        """
        Directly add a data point for a symbol.
        Modified to handle both processed data points and raw chart data.

        Args:
            symbol: The symbol to add data for
            data_point: The data point to add
        """
        with self.data_lock:
            if symbol not in self.active_symbols:
                self.active_symbols.add(symbol)

            if symbol not in self.symbols_data:
                self.symbols_data[symbol] = []

            # Check if this is raw chart data (has fields 1-7)
            if '1' in data_point and '2' in data_point and '3' in data_point and \
                    '4' in data_point and '5' in data_point and '7' in data_point:

                # It's chart data from CHART_EQUITY
                processed_point = {
                    # Store original fields for UI processing
                    '1': data_point.get('1'),
                    '2': data_point.get('2'),
                    '3': data_point.get('3'),
                    '4': data_point.get('4'),
                    '5': data_point.get('5'),
                    '6': data_point.get('6', 0),
                    '7': data_point.get('7'),

                    # Also store in standard format for backward compatibility
                    'timestamp': data_point.get('7'),
                    'open': float(data_point.get('2')),
                    'high': float(data_point.get('3')),
                    'low': float(data_point.get('4')),
                    'close': float(data_point.get('5')),
                    'volume': float(data_point.get('6', 0))
                }

                # Add to data store
                self.symbols_data[symbol].append(processed_point)

                if self.debug:
                    print(f"Added chart candle for {symbol}, now have {len(self.symbols_data[symbol])} points")

            else:
                # It's a regular data point
                self.symbols_data[symbol].append(data_point)

                if self.debug:
                    print(f"Added regular data point for {symbol}, now have {len(self.symbols_data[symbol])} points")

    def shutdown(self):
        """Shutdown the Flask server"""
        # This doesn't actually stop the Flask server in development mode
        # but it's a placeholder for proper shutdown in production
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            self.logger.error('Not running with the Werkzeug Server')
        else:
            func()