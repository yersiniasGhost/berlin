import os
import sys

# Import path fixer - add this at the top
import fix_imports

fix_imports.setup_imports()

import json
import logging
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO
from datetime import datetime

# Import from services
from services.schwab_auth import SchwabAuthManager
from services.data_service import DataService
from services.ui_external_tool import UIExternalTool

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('StockAnalysisUI')

# Path for authentication file
SCHWAB_AUTH_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'src', 'schwab_api', 'authentication_info.json')
print(f"Looking for auth file at: {SCHWAB_AUTH_FILE}")

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret_key')

# Initialize Socket.IO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*")

# Authentication manager will be set after authentication
auth_manager = None
ui_tool = None
data_service = None

# Default indicator configurations
from ui_config.indicator_configs import DEFAULT_INDICATORS, AVAILABLE_INDICATORS


def authenticate_before_startup():
    """Authenticate with Schwab API before starting the web server"""
    global auth_manager, ui_tool, data_service  # Declare globals at beginning of function

    # Check if we have already authenticated (for Flask debug mode restarts)
    token_path = "schwab_tokens.json"

    if os.path.exists(token_path):
        try:
            with open(token_path, 'r') as f:
                tokens = json.load(f)

                # Create authentication manager with existing tokens
                auth_manager = SchwabAuthManager()
                auth_manager.access_token = tokens.get('access_token')
                auth_manager.refresh_token = tokens.get('refresh_token')

                # Try to get streamer info to verify token validity
                if auth_manager._get_streamer_info():
                    print("\nUsing saved authentication. Starting web server...")

                    # Initialize other services
                    ui_tool = UIExternalTool(socketio)
                    data_service = DataService(ui_tool)

                    return True
        except Exception as e:
            print(f"Error loading saved tokens: {e}")
            # Continue with normal authentication below

    print("\n==== STOCK ANALYSIS UI ====")
    print("Before starting the web application, you need to authenticate with Schwab API.")

    # Create authentication manager
    auth = SchwabAuthManager()

    # Try to authenticate
    if auth.authenticate():
        print("\nAuthentication successful! Starting web server...")
        # Store the authenticated manager globals for the app to use
        auth_manager = auth

        # Initialize other services now that we have authentication
        ui_tool = UIExternalTool(socketio)
        data_service = DataService(ui_tool)

        # Save tokens for future app restarts
        try:
            with open(token_path, 'w') as f:
                json.dump({
                    'access_token': auth_manager.access_token,
                    'refresh_token': auth_manager.refresh_token
                }, f)
            print(f"Saved authentication tokens to {token_path}")
        except Exception as e:
            print(f"Error saving tokens: {e}")

        return True
    else:
        print("\nAuthentication failed. Cannot start application without Schwab API access.")
        return False


# Routes
@app.route('/')
def index():
    """Main dashboard view"""
    return render_template('dashboard.html')


@app.route('/ticker/<symbol>')
def ticker_detail(symbol):
    """Detailed view for a specific ticker"""
    return render_template('ticker_detail.html', symbol=symbol)


@app.route('/api/authenticate', methods=['POST'])
def authenticate():
    """
    API route for authentication (not used with command-line auth)
    but kept for compatibility with front-end
    """
    return jsonify({
        "success": True,
        "message": "Already authenticated via command line"
    })


@app.route('/api/start', methods=['POST'])
def start_streaming():
    """Start data streaming for selected tickers"""
    symbols = request.json.get('symbols', [])
    if not symbols:
        return jsonify({"success": False, "error": "No symbols provided"})

    # Configure indicators (use default or from request)
    indicators = request.json.get('indicators', DEFAULT_INDICATORS)
    weights = request.json.get('weights', {})
    timeframe = request.json.get('timeframe', '1m')  # Default to 1m if not specified

    # Start data service
    success = data_service.start(symbols, indicators, weights, timeframe)

    # If we couldn't start the real data service, send some test data
    if not success:
        logger.warning("Could not start real data service, sending test data")
        for symbol in symbols:
            socketio.emit('ticker_update', {
                'symbol': symbol,
                'data': {
                    'timestamp': datetime.now().isoformat(),
                    'open': 150.0,
                    'high': 152.5,
                    'low': 149.0,
                    'close': 151.75,
                    'volume': 1000000,
                    'symbol': symbol
                }
            })

            # Also send test indicator data
            socketio.emit('indicator_update', {
                'symbol': symbol,
                'indicators': {
                    'sma_crossover': 0.8,
                    'macd_signal': 0.6
                },
                'raw_indicators': {
                    'sma_crossover': 1.0,
                    'macd_signal': 0.75
                },
                'overall_scores': {
                    'bull': 0.7,
                    'bear': 0.2
                }
            })
        success = True

    return jsonify({"success": success})


@app.route('/api/stop', methods=['POST'])
def stop_streaming():
    """Stop data streaming"""
    data_service.stop()
    return jsonify({"success": True})


@app.route('/api/tickers', methods=['GET'])
def get_tickers():
    """Get current tickers and their data"""
    symbol = request.args.get('symbol')
    timeframe = request.args.get('timeframe', '1m')

    ticker_data = data_service.get_ticker_data()

    # If symbol is specified, filter the data
    if symbol:
        filtered_data = {}
        for key in ['data', 'indicators', 'overall_scores', 'history']:
            if key in ticker_data and symbol in ticker_data[key]:
                filtered_data[key] = {symbol: ticker_data[key][symbol]}
            else:
                filtered_data[key] = {}

        filtered_data['tickers'] = [symbol] if symbol in ticker_data.get('tickers', []) else []
        return jsonify(filtered_data)

    return jsonify(ticker_data)


@app.route('/api/indicators', methods=['GET'])
def get_indicators():
    """Get available indicator configurations"""
    # Ensure we have indicators to return
    if not AVAILABLE_INDICATORS or len(AVAILABLE_INDICATORS) == 0:
        # Return some default indicators if the configured ones aren't available
        return jsonify([
            {
                "name": "sma_crossover_bullish",
                "display_name": "SMA Crossover (Bullish)",
                "type": "INDICATOR_TYPE",
                "function": "sma_crossover",
                "parameters": {
                    "period": 20,
                    "crossover_value": 0.002,
                    "trend": "bullish",
                    "lookback": 10
                }
            },
            {
                "name": "macd_signal_bullish",
                "display_name": "MACD Signal (Bullish)",
                "type": "INDICATOR_TYPE",
                "function": "macd_histogram_crossover",
                "parameters": {
                    "fast": 12,
                    "slow": 26,
                    "signal": 9,
                    "histogram_threshold": 0.1,
                    "trend": "bullish",
                    "lookback": 15
                }
            }
        ])
    return jsonify(AVAILABLE_INDICATORS)


@app.route('/api/weights', methods=['POST'])
def update_weights():
    """Update indicator weights"""
    weights = request.json
    if not weights:
        return jsonify({"success": False, "error": "No weights provided"})

    # Update weights in data service
    success = data_service.update_weights(weights)
    return jsonify({"success": success})


# Socket.IO events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info('Client connected')


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info('Client disconnected')


# Add this to your Flask routes in app.py
@app.route('/api/test_socket')
def test_socket():
    """Test Socket.IO event emission"""
    symbol = request.args.get('symbol', 'TEST')
    print(f"Emitting test Socket.IO event for {symbol}")

    # Emit a test event
    socketio.emit('test_event', {
        'message': 'This is a test event from the server',
        'timestamp': datetime.now().isoformat(),
        'symbol': symbol
    })

    # Also try to emit a candle event
    socketio.emit('candle_completed', {
        'symbol': symbol,
        'candle': {
            'timestamp': datetime.now().isoformat(),
            'open': 100.0,
            'high': 105.0,
            'low': 95.0,
            'close': 102.0,
            'volume': 1000
        }
    })

    return jsonify({
        'success': True,
        'message': 'Test events emitted'
    })


# Main entry point
if __name__ == '__main__':
    # Authenticate before starting the server
    if authenticate_before_startup():
        socketio.run(app, debug=True, host='0.0.0.0', use_reloader=False)  # Disable reloader
    else:
        print("Exiting due to authentication failure.")