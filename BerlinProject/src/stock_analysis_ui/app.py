#!/usr/bin/env python3
"""
Simple Flask app for streaming indicators with symbol/config selection
"""

import os
import sys
import json
import logging
import threading
from typing import List, Dict
from collections import defaultdict
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..', 'src'))

from stock_analysis_ui.services.schwab_auth import SchwabAuthManager
from data_streamer.schwab_data_link import SchwabDataLink
from data_streamer.candle_aggregator import CandleAggregator
from data_streamer.data_streamer import DataStreamer
from models.monitor_configuration import MonitorConfiguration
from stock_analysis_ui.services.streaming_manager import StreamingManager
from stock_analysis_ui.services.ui_external_tool_old import UIExternalTool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('StreamingApp')

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
streaming_active: bool = False
streaming_thread = None
data_service = None


def authenticate_before_startup():
    """Force fresh Schwab authentication before starting the web server"""
    global data_service

    print("\n=== SCHWAB AUTHENTICATION REQUIRED ===")
    print("You will be required to login to Schwab API (no saved token).")

    # Create auth manager and force fresh authentication
    auth_manager = SchwabAuthManager()
    # Clear any existing tokens to force fresh login
    auth_manager.access_token = None
    auth_manager.refresh_token = None

    print("Starting fresh Schwab authentication...")
    if not auth_manager.authenticate():
        print("\nAuthentication failed. Cannot start application.")
        return False

    # Create data service and assign the authenticated auth_manager
    data_service = DataService()
    data_service.auth_manager = auth_manager

    print("\nFresh authentication successful! Starting web server...")
    return True


class DataService:
    def __init__(self):
        self.auth_manager = None
        self.data_link = None
        self.streaming_manager = None
        self.data_streamer = None
        self.ui_tool = None
        self.is_running = False

    def setup_auth(self) -> bool:
        # Use the already authenticated auth_manager from startup
        return self.auth_manager is not None and self.auth_manager.access_token is not None

    def start_streaming(self, combinations: List[Dict]) -> bool:
        if self.is_running:
            return False

        # Setup data link
        self.data_link = SchwabDataLink()
        self.data_link.access_token = self.auth_manager.access_token
        self.data_link.refresh_token = self.auth_manager.refresh_token
        self.data_link.user_prefs = self.auth_manager.user_prefs

        if not self.data_link.connect_stream():
            return False

        # Create streaming manager
        self.streaming_manager = StreamingManager(self.data_link)

        # Setup aggregators and streamers for each combination
        all_symbols = set()
        for combo in combinations:
            symbol = combo['symbol']
            config_file = combo['config']

            # Load monitor config
            with open(config_file, 'r') as f:
                config_data = json.load(f)

            monitor_data = config_data['monitor']
            monitor_data['indicators'] = config_data['indicators']
            monitor_config = MonitorConfiguration(**monitor_data)

            timeframes = monitor_config.get_time_increments()

            # Create aggregators for this symbol
            aggregators = {}
            for timeframe in timeframes:
                aggregator = CandleAggregator(symbol, timeframe)
                # Load historical data
                aggregator.prepopulate_data(self.data_link)
                aggregators[timeframe] = aggregator

            # Register with streaming manager
            self.streaming_manager.aggregators[symbol] = aggregators

            # Create data streamer for this combination
            model_config = {"feature_vector": [{"name": "close"}]}
            data_streamer = DataStreamer(model_config, monitor_config)

            # Create UI tool for this combination
            ui_tool = UIExternalTool(socketio, monitor_config)
            data_streamer.connect_tool(ui_tool)

            # Store streamer (simplified - using last one for demo)
            self.data_streamer = data_streamer
            self.ui_tool = ui_tool

            all_symbols.add(symbol)

        # Start streaming
        self.data_link.add_quote_handler(self.streaming_manager.route_pip_data)
        self.data_link.subscribe_quotes(list(all_symbols))

        self.is_running = True
        return True

    def process_indicators(self):
        """Process indicators periodically"""
        while self.is_running:
            if self.data_streamer and self.streaming_manager:
                for symbol in self.streaming_manager.aggregators:
                    symbol_aggregators = self.streaming_manager.aggregators[symbol]
                    self.data_streamer.process_tick(symbol_aggregators)

            import time
            time.sleep(2)  # Process every 2 seconds

    def stop_streaming(self):
        self.is_running = False
        if self.data_link:
            self.data_link.disconnect()


# Routes
@app.route('/')
def index():
    """Main page with symbol/config selection"""
    # Get available config files - look in current directory and src directory
    config_files = []

    # Check current directory first
    for file in os.listdir('.'):
        if file.endswith('.json') and 'monitor_config' in file:
            config_files.append(file)

    # If no files found, check src/stock_analysis_ui directory
    if not config_files:
        try:
            src_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'stock_analysis_ui')
            if os.path.exists(src_dir):
                for file in os.listdir(src_dir):
                    if file.endswith('.json') and 'monitor_config' in file:
                        config_files.append(file)
        except:
            pass

    # If still no files, provide default
    if not config_files:
        config_files = ['monitor_config_example_time_intervals.json']

    return render_template('index.html', config_files=config_files)


# Add new route for authentication
@app.route('/api/authenticate', methods=['POST'])
def authenticate():
    """Handle Schwab authentication separately"""
    global data_service

    try:
        if not data_service:
            data_service = DataService()

        # This will prompt in terminal and wait for user input
        success = data_service.setup_auth()

        if success:
            return jsonify({'success': True, 'message': 'Authentication successful'})
        else:
            return jsonify({'success': False, 'error': 'Authentication failed'})

    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/start', methods=['POST'])
def start_streaming():
    """Start streaming with selected combinations"""
    global streaming_active, streaming_thread, data_service

    if streaming_active:
        return jsonify({'success': False, 'error': 'Already streaming'})

    combinations = request.json.get('combinations', [])
    if not combinations:
        return jsonify({'success': False, 'error': 'No combinations provided'})

    try:
        # Make sure we have data service and it's authenticated
        if not data_service:
            return jsonify({'success': False, 'error': 'Please authenticate first'})

        if not data_service.auth_manager or not data_service.auth_manager.is_authenticated():
            return jsonify({'success': False, 'error': 'Please authenticate first'})

        # Start streaming (authentication already done)
        if not data_service.start_streaming(combinations):
            return jsonify({'success': False, 'error': 'Failed to start streaming'})

        # Start background thread for indicator processing
        streaming_thread = threading.Thread(target=data_service.process_indicators)
        streaming_thread.daemon = True
        streaming_thread.start()

        streaming_active = True
        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error starting streaming: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/stop', methods=['POST'])
def stop_streaming():
    """Stop streaming"""
    global streaming_active, data_service

    if data_service:
        data_service.stop_streaming()

    streaming_active = False
    return jsonify({'success': True})


@app.route('/api/status')
def get_status():
    """Get current streaming status"""
    auth_status = False
    if data_service and data_service.auth_manager and data_service.auth_manager.access_token:
        auth_status = True

    return jsonify({
        'streaming': streaming_active,
        'authenticated': auth_status,
        'combinations': len(
            data_service.streaming_manager.aggregators) if data_service and data_service.streaming_manager else 0
    })


# WebSocket events
@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')


@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')


if __name__ == '__main__':
    # Authenticate before starting the server
    if authenticate_before_startup():
        print("🚀 Starting web application at http://localhost:5000")
        socketio.run(app, debug=False, host='0.0.0.0', port=5000)
    else:
        print("Exiting due to authentication failure.")