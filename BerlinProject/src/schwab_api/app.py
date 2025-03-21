from flask import Flask, render_template, request, jsonify
import json
import threading
import logging
import time
from datetime import datetime, timedelta
import pandas as pd
import os

# Import the data processor and Schwab client
from schwab_api.data_processor import DataProcessor
from schwab_api.authentication import SchwabClient, easy_client
from data_streamer.schwab_data_stream import SchwabDataStreamAdapter

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('StockApp')

app = Flask(__name__)

# App configuration
APP_CONFIG = {
    'app_key': os.environ.get('SCHWAB_APP_KEY', ''),
    'app_secret': os.environ.get('SCHWAB_APP_SECRET', ''),
    'redirect_uri': os.environ.get('SCHWAB_REDIRECT_URI', 'https://127.0.0.1:8182'),
    'token_path': os.environ.get('SCHWAB_TOKEN_PATH', 'schwab_tokens.json')
}

# This will store our streaming data for each symbol
streaming_data = {}
# Track active streaming symbols
active_symbols = set()
# Lock for thread-safe operations
data_lock = threading.Lock()

# Initialize Schwab client
schwab_client = None
streaming_client = None
is_connected = False

# Initialize data processor
data_processor = DataProcessor()
# Initialize adapter
schwab_adapter = None


def initialize_schwab():
    global schwab_client, streaming_client, is_connected, schwab_adapter

    try:
        logger.info("Creating Schwab client")
        # Use the easy_client method for simplified authentication
        schwab_client = easy_client(
            app_key=APP_CONFIG['app_key'],
            app_secret=APP_CONFIG['app_secret'],
            callback_url=APP_CONFIG['redirect_uri'],
            token_path=APP_CONFIG['token_path']
        )

        if schwab_client:
            logger.info("Successfully authenticated with Schwab API")

            # Create streaming client
            streaming_client = schwab_client.create_streaming_session()

            if streaming_client:
                is_connected = True
                logger.info("Successfully connected to Schwab streaming API")

                # Initialize adapter
                schwab_adapter = SchwabDataStreamAdapter()
                return True
            else:
                logger.error("Failed to create streaming session")
        else:
            logger.error("Authentication with Schwab API failed")

        return False
    except Exception as e:
        logger.exception(f"Error initializing Schwab client: {e}")
        return False


def check_stream_connection():
    """Check and maintain streaming connection"""
    global streaming_client, is_connected, active_symbols

    while True:
        if streaming_client:
            # Update the global connection status from client
            is_connected = getattr(streaming_client, 'is_connected', False)

            # Log connection status periodically
            logger.debug(f"Stream connection status: {is_connected}")

            # If connection was lost and needs to be resubscribed
            if is_connected and active_symbols:
                # Check if we need to resubscribe symbols
                try:
                    streaming_client.subscribe_quotes(list(active_symbols), handle_quote_data)
                    streaming_client.subscribe_charts(list(active_symbols), handle_chart_data)
                    logger.info(f"Resubscribed to: {list(active_symbols)}")
                except Exception as e:
                    logger.error(f"Error resubscribing: {e}")

        # Check every 15 seconds
        time.sleep(15)


def handle_quote_data(data):
    """Handle incoming quote data"""
    logger.info(f"Received quote data: {str(data)[:100]}...")  # Log first part of data

    # Forward to schwab adapter
    if schwab_adapter:
        schwab_adapter.handle_quote_data(data)

    with data_lock:
        for quote in data:
            symbol = quote.get('key', 'UNKNOWN')
            if symbol in active_symbols:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

                # Parse values
                try:
                    bid = float(quote.get('1', 0.0))
                    ask = float(quote.get('2', 0.0))
                    last = float(quote.get('3', 0.0))
                    volume = int(quote.get('8', 0))

                    # Create a new data point
                    new_point = {
                        'timestamp': timestamp,
                        'last': last,
                        'bid': bid,
                        'ask': ask,
                        'volume': volume
                    }

                    # Process through data processor - updates last candle
                    updated_data = data_processor.process_quote_update(symbol, new_point)
                    streaming_data[symbol] = updated_data

                    logger.debug(f"Updated quote data for {symbol}")

                except Exception as e:
                    logger.error(f"Error processing quote for {symbol}: {e}")


def handle_chart_data(data):
    """Handle incoming chart (OHLCV) data"""
    logger.info(f"Received chart data: {str(data)[:100]}...")  # Log first part of data

    # Forward to schwab adapter
    if schwab_adapter:
        schwab_adapter.handle_chart_data(data)

    with data_lock:
        for chart_entry in data:
            symbol = chart_entry.get('key', 'UNKNOWN')
            if symbol in active_symbols:
                try:
                    # Parse chart values - field numbers based on Schwab API documentation
                    timestamp_ms = int(chart_entry.get('7', 0))
                    timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
                    formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')

                    # Create a candle data point
                    candle = {
                        'timestamp': formatted_time,
                        'open': float(chart_entry.get('2', 0.0)),
                        'high': float(chart_entry.get('3', 0.0)),
                        'low': float(chart_entry.get('4', 0.0)),
                        'close': float(chart_entry.get('5', 0.0)),
                        'volume': int(chart_entry.get('6', 0))
                    }

                    # Process through data processor
                    updated_data = data_processor.process_chart_update(symbol, candle)
                    streaming_data[symbol] = updated_data

                    logger.debug(f"Updated chart data for {symbol}, candles: {len(updated_data)}")

                except Exception as e:
                    logger.error(f"Error processing chart data for {symbol}: {e}")


def fetch_historical_data(symbol, days=1):
    """Fetch historical intraday data for a symbol"""
    logger.info(f"Fetching historical data for {symbol}")

    if is_connected and schwab_client and hasattr(schwab_client, 'price_history'):
        try:
            # For intraday data from midnight today
            logger.info(f"Calling Schwab API for {symbol} history")

            response = schwab_client.price_history(
                symbol=symbol,
                periodType="day",
                period=1,  # 1 day
                frequencyType="minute",
                frequency=1,  # 1-minute candles
                needExtendedHoursData=True  # Include pre-market and after-hours data
            )

            if hasattr(response, 'status_code') and response.status_code == 200:
                data = response.json()

                # Format the data to match our streaming format
                candles = []
                if 'candles' in data:
                    for candle in data['candles']:
                        timestamp = datetime.fromtimestamp(candle['datetime'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                        candles.append({
                            'timestamp': timestamp,
                            'open': candle['open'],
                            'high': candle['high'],
                            'low': candle['low'],
                            'close': candle['close'],
                            'volume': candle['volume']
                        })

                logger.info(f"Retrieved {len(candles)} historical data points for {symbol}")

                # Process through our data processor
                return data_processor.process_historical_data(symbol, candles)
            else:
                logger.error(f"Error fetching historical data: {getattr(response, 'text', 'No response text')}")
                return []
        except Exception as e:
            logger.exception(f"Exception fetching historical data: {e}")
            return []

    logger.warning(f"Cannot fetch historical data from Schwab API, no connection available")
    return []


# 4. REPLACE the subscribe route with this version:
@app.route('/subscribe', methods=['POST'])
def subscribe():
    data = request.json
    symbols = data.get('symbols', [])

    # Validate - max 4 symbols
    if len(symbols) > 4:
        return jsonify({'error': 'Maximum 4 symbols allowed'}), 400

    logger.info(f"Subscribing to symbols: {symbols}")

    with data_lock:
        # Clear previous data if changing symbols
        streaming_data.clear()
        active_symbols.clear()

        # Add new symbols
        for symbol in symbols:
            symbol = symbol.upper()
            active_symbols.add(symbol)

            # Load historical data for each symbol
            try:
                historical_data = fetch_historical_data(symbol)
                if historical_data:
                    streaming_data[symbol] = historical_data
                    logger.info(f"Loaded {len(historical_data)} historical data points for {symbol}")
                else:
                    streaming_data[symbol] = []
                    logger.warning(f"No historical data available for {symbol}")
            except Exception as e:
                logger.error(f"Error fetching historical data for {symbol}: {e}")
                streaming_data[symbol] = []

    # Subscribe to real-time updates
    if is_connected and streaming_client:
        try:
            logger.info(f"Subscribing to quotes for {list(active_symbols)}")
            streaming_client.subscribe_quotes(list(active_symbols), handle_quote_data)

            logger.info(f"Subscribing to charts for {list(active_symbols)}")
            streaming_client.subscribe_charts(list(active_symbols), handle_chart_data)

            # Update the adapter with the current symbols
            if schwab_adapter:
                schwab_adapter.symbols = list(active_symbols)

            return jsonify({
                'success': True,
                'message': f'Subscribed to {len(active_symbols)} symbols with real-time data'
            })
        except Exception as e:
            logger.error(f"Error subscribing to data streams: {e}")
            return jsonify({
                'success': True,
                'message': f'Loaded historical data for {len(active_symbols)} symbols'
            })
    else:
        return jsonify({
            'success': True,
            'message': f'No streaming connection available for {len(active_symbols)} symbols'
        })

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data/<symbol>')
def get_data(symbol):
    symbol = symbol.upper()
    timeframe = request.args.get('timeframe', '1m')

    with data_lock:
        if symbol in streaming_data and streaming_data[symbol]:
            # Get aggregated data at the requested timeframe through our data processor
            return jsonify(data_processor.get_aggregated_data(symbol, timeframe))
        else:
            logger.info(f"No data found for {symbol}")
            return jsonify([])


@app.route('/status')
def get_status():
    status = {
        'connected': is_connected,
        'active_symbols': list(active_symbols)
    }
    return jsonify(status)


if __name__ == '__main__':
    # Import random here to avoid circular imports
    import random

    # Print instructions
    print("\n==== STOCK STREAMING APP ====")
    print("1. First authenticate with Schwab API")
    print("2. Then visit the web application at: http://127.0.0.1:5000\n")

    # Initialize Schwab client in a separate thread
    threading.Thread(target=initialize_schwab, daemon=True).start()

    # Start connection monitoring thread
    threading.Thread(target=check_stream_connection, daemon=True).start()

    # Short delay to allow initialization
    time.sleep(2)

    # Run the Flask app with debug mode but no auto-reloader
    app.run(debug=True, use_reloader=False)