from flask import Flask, render_template, request, jsonify
import json
import threading
import logging
import time
from datetime import datetime, timedelta
import pandas as pd
import random

# Import the data processor
from data_processor import DataProcessor

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('StockApp')

app = Flask(__name__)

# This will store our streaming data for each symbol
streaming_data = {}
# Track active streaming symbols
active_symbols = set()
# Lock for thread-safe operations
data_lock = threading.Lock()

# Initialize Schwab client
schwab_client = None
is_connected = False

# Initialize data processor
data_processor = DataProcessor()


def initialize_schwab():
    global schwab_client, is_connected
    # Create and authenticate the Schwab client
    try:
        from authentication import SchwabClient  # Your authentication module
        logger.info("Creating Schwab client")
        schwab_client = SchwabClient()

        logger.info("Authenticating with Schwab API")
        success = schwab_client.authenticate()

        if success:
            logger.info("Authentication successful, connecting to stream")
            success = schwab_client.connect_stream()
            if success:
                is_connected = True
                logger.info("Successfully connected to Schwab streaming API")
            else:
                logger.error("Failed to connect to Schwab streaming API")
        else:
            logger.error("Authentication with Schwab API failed")

        return success
    except Exception as e:
        logger.exception(f"Error initializing Schwab client: {e}")
        return False


def check_stream_connection():
    """Check and maintain streaming connection"""
    global schwab_client, is_connected

    while True:
        if schwab_client:
            # Update the global connection status from client
            is_connected = getattr(schwab_client, 'is_connected', False)

            # Log connection status periodically
            logger.debug(f"Stream connection status: {is_connected}")

            # If connection was lost and needs to be resubscribed
            if is_connected and active_symbols:
                # Check if we need to resubscribe symbols
                try:
                    schwab_client.subscribe_quotes(list(active_symbols), handle_quote_data)
                    logger.info(f"Resubscribed to: {list(active_symbols)}")
                except Exception as e:
                    logger.error(f"Error resubscribing: {e}")

        # Check every 15 seconds
        time.sleep(15)


def handle_quote_data(data):
    """Handle incoming quote data"""
    logger.info(f"Received quote data: {str(data)[:100]}...")  # Log first part of data

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
                        'open': last,  # For streaming, we use last price for all OHLC values initially
                        'high': last,
                        'low': last,
                        'close': last,
                        'volume': volume
                    }

                    # Process through data processor which handles anomalies
                    updated_data = data_processor.process_streaming_update(symbol, new_point)
                    streaming_data[symbol] = updated_data

                    logger.debug(f"Updated data for {symbol}, current candles: {len(updated_data)}")

                except Exception as e:
                    logger.error(f"Error processing quote for {symbol}: {e}")


def generate_mock_price_series(symbol, days=1, initial_price=None):
    """Generate a realistic mock price series for a symbol"""
    # Use a seed based on symbol name for consistent results
    random.seed(sum(ord(c) for c in symbol))

    # Set initial price based on symbol if not provided
    if initial_price is None:
        initial_price = random.uniform(50, 500)

    # Parameters for random walk
    volatility = random.uniform(0.005, 0.02)  # Daily volatility
    drift = random.uniform(-0.001, 0.001)  # Slight trend

    # Create timestamp series starting from midnight
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    start_time = datetime.combine(start_time.date(), datetime.min.time())  # Midnight of start day

    # Include all times from midnight, but add more activity during market hours
    current_time = start_time
    times = []

    while current_time <= end_time:
        # More data points during market hours
        hours_increment = 1 / 60  # 1 minute by default

        # For pre-market and after-hours, use larger increments
        current_hour = current_time.hour
        if current_hour < 6 or current_hour > 13:
            # Only add a point every 5 minutes outside market hours
            if current_time.minute % 5 == 0:
                times.append(current_time)
        else:
            times.append(current_time)

        current_time += timedelta(minutes=1)

    # Generate price series as geometric random walk
    prices = [initial_price]
    for i in range(1, len(times)):
        # Different activity based on market hours
        t = times[i]
        time_of_day = t.hour + t.minute / 60

        # Market open/close times (6:30 AM - 1:00 PM)
        market_open_hour = 6.5  # 6:30 AM
        market_close_hour = 13.0  # 1:00 PM

        # Pre-market (low activity)
        if time_of_day < market_open_hour:
            daily_volatility = volatility * 0.3
            daily_return = drift * 0.5 + random.normalvariate(0, daily_volatility)
        # Market hours (high activity)
        elif market_open_hour <= time_of_day <= market_close_hour:
            # More activity at market open and close
            if abs(time_of_day - market_open_hour) < 1 or abs(time_of_day - market_close_hour) < 1:
                daily_volatility = volatility * 1.5
            else:
                daily_volatility = volatility
            daily_return = drift + random.normalvariate(0, daily_volatility)
        # After-market (low activity)
        else:
            daily_volatility = volatility * 0.4
            daily_return = drift * 0.5 + random.normalvariate(0, daily_volatility)

        prices.append(prices[-1] * (1 + daily_return))

    # Create OHLC candles
    candles = []
    for i, t in enumerate(times):
        # Create realistic candle with open, high, low, close
        price = prices[i]

        # Different volatility based on market hours
        time_of_day = t.hour + t.minute / 60
        # Market open/close times
        market_open_hour = 6.5  # 6:30 AM
        market_close_hour = 13.0  # 1:00 PM

        if time_of_day < market_open_hour:
            candle_volatility = volatility * 0.3
        elif market_open_hour <= time_of_day <= market_close_hour:
            candle_volatility = volatility * random.uniform(0.5, 1.5)
        else:
            candle_volatility = volatility * 0.4

        open_price = price
        close_price = price * (1 + random.normalvariate(0, candle_volatility / 2))
        high_price = max(open_price, close_price) * (1 + abs(random.normalvariate(0, candle_volatility)))
        low_price = min(open_price, close_price) * (1 - abs(random.normalvariate(0, candle_volatility)))

        # Volume varies by time of day
        # Pre-market (very low volume)
        if time_of_day < market_open_hour:
            volume = random.randint(100, 1000)
        # Market hours (high volume, especially at open and close)
        elif market_open_hour <= time_of_day <= market_close_hour:
            if abs(time_of_day - market_open_hour) < 1:
                volume = random.randint(5000, 15000)  # Higher volume at open
            elif abs(time_of_day - market_close_hour) < 1:
                volume = random.randint(4000, 12000)  # Higher volume at close
            else:
                volume = random.randint(2000, 8000)  # Normal market hours
        # After-market (low volume)
        else:
            volume = random.randint(500, 2000)

        candles.append({
            'timestamp': t.strftime('%Y-%m-%d %H:%M:%S'),
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': volume
        })

    return candles


# Mock data for testing if Schwab API is not available
def create_mock_data(symbol, days=1):
    """Create mock data for a symbol if real data is not available"""
    logger.info(f"Creating mock data for {symbol}")
    return generate_mock_price_series(symbol, days)


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
                mock_data = create_mock_data(symbol)
                return data_processor.process_historical_data(symbol, mock_data)
        except Exception as e:
            logger.exception(f"Exception fetching historical data: {e}")
            mock_data = create_mock_data(symbol)
            return data_processor.process_historical_data(symbol, mock_data)

    logger.warning(f"Cannot fetch historical data from Schwab API, using mock data for {symbol}")
    mock_data = create_mock_data(symbol)
    return data_processor.process_historical_data(symbol, mock_data)


@app.route('/')
def index():
    return render_template('index.html')


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
                streaming_data[symbol] = historical_data
                logger.info(f"Loaded {len(historical_data)} historical data points for {symbol}")
            except Exception as e:
                logger.error(f"Error fetching historical data for {symbol}: {e}")
                streaming_data[symbol] = create_mock_data(symbol)
                logger.info(f"Using mock data for {symbol}")

    # Subscribe to real-time updates
    if is_connected and schwab_client:
        try:
            logger.info(f"Subscribing to quotes for {list(active_symbols)}")
            schwab_client.subscribe_quotes(list(active_symbols), handle_quote_data)
            return jsonify({
                'success': True,
                'message': f'Subscribed to {len(active_symbols)} symbols with historical data'
            })
        except Exception as e:
            logger.error(f"Error subscribing to quotes: {e}")
            return jsonify({
                'success': True,
                'message': f'Loaded historical data for {len(active_symbols)} symbols'
            })
    else:
        return jsonify({
            'success': True,
            'message': f'Using historical/mock data for {len(active_symbols)} symbols'
        })


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
    # Print instructions
    print("\n==== STOCK STREAMING APP ====")
    print("1. First authenticate with Schwab API (follow prompts in console)")
    print("2. Then visit the web application at: http://127.0.0.1:5000\n")

    # Initialize Schwab client in a separate thread
    threading.Thread(target=initialize_schwab, daemon=True).start()

    # Start connection monitoring thread
    threading.Thread(target=check_stream_connection, daemon=True).start()

    # Short delay to allow initialization
    time.sleep(2)

    # Run the Flask app with debug mode but no auto-reloader
    app.run(debug=True, use_reloader=False)