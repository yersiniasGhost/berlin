import requests
import websocket
import json
import threading
import time
from typing import Set, Dict, List
from datetime import datetime

from data_streamer.data_link import DataLink
from models.tick_data import TickData
from mlf_utils.log_manager import LogManager
from mlf_utils.timezone_utils import utc_from_timestamp_ms, now_utc, format_et

logger = LogManager().get_logger("SchwabDataLink")


class SchwabDataLink(DataLink):
    """
    A "simplified" class for connecting to Schwab API and streaming market data.
    Converts PIP data to TickData objects before passing to DataStreamers.
    """

    def __init__(self):
        super().__init__()
        # Hardcoded authentication credentials
        self.app_key: str = "QtfsQiLHpno726ZFgRDtvHA3ZItCAkcQ"
        self.app_secret: str = "RmwUJyBGGgW2r2C7"
        self.redirect_uri: str = "https://127.0.0.1"
        self.access_token = None
        self.refresh_token = None

        # for data dumper
        self.quote_handlers = []

        # Streamer configuration
        self.user_prefs = None
        self.ws = None  # WebSocket connection
        self.is_connected = False
        self.request_id = 0
        self.subscribed_symbols: Set[str] = set()
        self.login_complete = False
        logger.info(f"Initialized SchwabDataLink with API key: {self.app_key}")

    # TODO: ADD A NEW VALIDATOR TO MAKE SURE WE ARE NOT GETTING HUGE DECREASES FROM PIP TO PIP...
    # DATA QUALITY ISSUE^

    # In schwab_data_link.py, modify the _pip_to_tick_data method

    def _pip_to_tick_data(self, pip_data: Dict) -> TickData:
        """
        Convert Schwab PIP (Price In Progress) data to TickData object.

        All timestamps are converted to UTC-aware datetimes using timezone_utils.
        This ensures consistent timezone handling throughout the application.
        """
        # Get required fields
        symbol = pip_data.get('key')
        close_price = pip_data.get('3')

        # Validation - only require symbol and price
        if not symbol or not close_price:
            logger.debug(f"Missing required data: symbol={symbol}, price={close_price}")
            return None

        # Convert price and validate
        try:
            price = float(close_price)
            if price <= 0:
                print(f"Invalid price: {price}")
                return None
        except (ValueError, TypeError):
            print(f"Cannot convert price to float: {close_price}")
            return None

        # Handle timestamp with fallback to current time
        # Schwab API returns timestamps as milliseconds since Unix epoch (UTC)
        timestamp_ms = pip_data.get('38')
        timestamp = None

        if timestamp_ms:
            try:
                timestamp_ms = int(timestamp_ms)
                if timestamp_ms > 0:
                    # Convert to UTC-aware datetime
                    timestamp = utc_from_timestamp_ms(timestamp_ms)

                    # Sanity check timestamp (must be after year 2000)
                    if timestamp.year < 2000:
                        print(f"Invalid timestamp year: {timestamp.year}, using current time")
                        timestamp = None  # Will use current time below
                else:
                    print(f"Invalid timestamp: {timestamp_ms}, using current time")
                    timestamp = None  # Will use current time below
            except (ValueError, TypeError):
                print(f"Cannot convert timestamp: {timestamp_ms}, using current time")
                timestamp = None  # Will use current time below

        # If no valid timestamp, use current UTC time
        if timestamp is None:
            timestamp = now_utc()

        volume = int(pip_data.get('8', 0))  # Optional, default to 0

        # For PIP data, all OHLC values are the current price
        return TickData(
            symbol=symbol,
            timestamp=timestamp,
            open=price,
            high=price,
            low=price,
            close=price,
            volume=volume,
            time_increment="PIP"
        )

    def authenticate(self):
        """Authenticate with Schwab API using console input"""
        logger.info("Starting authentication process...")

        # Construct auth URL
        auth_url = f"https://api.schwabapi.com/v1/oauth/authorize?client_id={self.app_key}&redirect_uri={self.redirect_uri}"

        # Open browser
        logger.info(f"Opening browser to: {auth_url}")
        import webbrowser
        webbrowser.open(auth_url)

        # Get redirect URL with code
        logger.info("\nAfter logging in, please copy the full URL from your browser's address bar")
        logger.info("and paste it here (it should contain 'code='):")
        returned_url = input()

        # Extract code from URL
        try:
            if "code=" in returned_url:
                # Use urllib.parse to properly handle URL encoding
                import urllib.parse
                parsed_url = urllib.parse.urlparse(returned_url)
                query_params = urllib.parse.parse_qs(parsed_url.query)

                if 'code' in query_params:
                    response_code = query_params['code'][0]
                    logger.info("Successfully extracted authorization code")
                else:
                    logger.error("Authorization code not found in URL parameters")
                    return False
            else:
                logger.error("URL does not contain authorization code")
                return False

            # Encode credentials
            import base64
            credentials = f"{self.app_key}:{self.app_secret}"
            base64_credentials = base64.b64encode(credentials.encode()).decode()

            # Set up headers and payload
            headers = {
                "Authorization": f"Basic {base64_credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            payload = {
                "grant_type": "authorization_code",
                "code": response_code,
                "redirect_uri": self.redirect_uri,
            }

            # Get token
            logger.info("Requesting access token...")
            token_response = requests.post(
                "https://api.schwabapi.com/v1/oauth/token",
                headers=headers,
                data=payload
            )

            # Process response
            token_data = token_response.json()

            if 'error' in token_data:
                logger.error(f"Token error: {token_data}")
                return False

            self.access_token = token_data.get("access_token")
            self.refresh_token = token_data.get("refresh_token")

            if self.access_token:
                logger.info("Successfully obtained access token")
                self._get_streamer_info()
                return True
            else:
                logger.error("No access token in response")
                return False

        except Exception as e:
            logger.error(f"Error processing authentication response: {e}")
            return False

    def _get_streamer_info(self) -> bool:
        """Get streamer information from user preferences"""
        if not self.access_token:
            logger.error("No access token available")
            return False

        headers = {"Authorization": f"Bearer {self.access_token}"}

        try:
            # Get user preferences
            response = requests.get(
                "https://api.schwabapi.com/trader/v1/userPreference",
                headers=headers
            )

            if response.status_code == 200:
                user_prefs = response.json()
                logger.info("Successfully got user preferences")

                streamer_info = user_prefs.get('streamerInfo', [{}])[0]
                self.user_prefs = {
                    "streamerUrl": streamer_info.get('streamerSocketUrl'),
                    "schwabClientCustomerId": streamer_info.get('schwabClientCustomerId'),
                    "schwabClientCorrelId": streamer_info.get('schwabClientCorrelId'),
                    "channel": streamer_info.get('schwabClientChannel'),
                    "functionId": streamer_info.get('schwabClientFunctionId')
                }
                return True
            else:
                logger.error(f"Error getting user preferences: {response.status_code} - {response.text}")

                # Use fallback values
                self.user_prefs = {
                    "streamerUrl": "wss://gateway-sip.schwab.com/streamer",
                    "schwabClientCustomerId": "DEFAULT_ID",
                    "schwabClientCorrelId": "DEFAULT_ID",
                    "channel": "IO",
                    "functionId": "APIAPP"
                }
                return False
        except Exception as e:
            logger.error(f"Error getting streamer info: {e}")
            return False

    def connect_stream(self) -> bool:
        """Connect to the Schwab streaming API"""
        if not self.user_prefs:
            logger.error("No streaming configuration available")
            return False

        streamer_url = self.user_prefs.get('streamerUrl')
        logger.info(f"Connecting to streamer URL: {streamer_url}")

        # Add a login_complete flag
        self.login_complete = False

        # Define WebSocket callbacks
        def on_open(ws):
            logger.info("WebSocket connection opened")
            self.is_connected = True
            self._login()

        def on_message(ws, message):
            self._handle_message(message)

        def on_error(ws, error):
            logger.error(f"WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
            self.is_connected = False

        # Create WebSocket connection
        self.ws = websocket.WebSocketApp(
            streamer_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )

        # Start WebSocket connection in a thread
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()

        # Wait for connection
        timeout = 10
        start_time = time.time()
        while not self.is_connected:
            if time.time() - start_time > timeout:
                logger.error("Connection timeout")
                return False
            time.sleep(0.5)

        # Wait for login to complete
        timeout = 10
        start_time = time.time()
        while not self.login_complete:
            if time.time() - start_time > timeout:
                logger.error("Login timeout")
                return False
            time.sleep(0.5)

        return True

    def _get_next_request_id(self) -> str:
        """Get next request ID"""
        self.request_id += 1
        return str(self.request_id)

    def _login(self) -> None:
        """Login to the streaming API"""
        login_request = {
            "requests": [
                {
                    "service": "ADMIN",
                    "requestid": self._get_next_request_id(),
                    "command": "LOGIN",
                    "SchwabClientCustomerId": self.user_prefs.get('schwabClientCustomerId'),
                    "SchwabClientCorrelId": self.user_prefs.get('schwabClientCorrelId'),
                    "parameters": {
                        "Authorization": self.access_token,
                        "SchwabClientChannel": self.user_prefs.get('channel'),
                        "SchwabClientFunctionId": self.user_prefs.get('functionId')
                    }
                }
            ]
        }

        logger.info("Sending login request to streamer")
        self.ws.send(json.dumps(login_request))

    def _handle_message(self, message: str) -> None:
        """Handle messages from the streaming API"""
        try:
            msg_data = json.loads(message)

            # Handle response messages (login, subscription responses)
            if 'response' in msg_data:
                for response in msg_data['response']:
                    service = response.get('service')
                    command = response.get('command')
                    content = response.get('content', {})

                    if service == 'ADMIN' and command == 'LOGIN':
                        code = content.get('code')
                        if code == 0:
                            logger.info("Login to streamer successful")
                            self.login_complete = True
                        else:
                            logger.error(f"Login to streamer failed: {content.get('msg', '')}")
                    else:
                        logger.info(f"Response for {service}/{command}: {content}")

            # Handle data messages (quotes, charts)
            if 'data' in msg_data:
                for data in msg_data['data']:
                    service = data.get('service')
                    content = data.get('content', [])
                    if service == 'LEVELONE_EQUITIES' and content:
                        self._handle_quote_data(content)

            # Handle notifications
            if 'notify' in msg_data:
                logger.info(f"Notification: {msg_data['notify']}")

        except json.JSONDecodeError:
            logger.error(f"Failed to decode message: {message}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _handle_quote_data(self, data: List[Dict]) -> None:
        """
        Process quote data and convert to TickData before passing to DataStreamers
        """
        logger.debug(f"Received quote data: {len(data)} quotes")

        for quote in data:
            try:
                # FIRST: Call any registered quote handlers with raw PIP data
                # This happens BEFORE validation, so we save everything
                for handler in self.quote_handlers:
                    try:
                        handler(quote)
                    except Exception as e:
                        logger.error(f"Error in quote handler: {e}")

                # THEN: Try to convert PIP data to TickData with validation
                tick_data = self._pip_to_tick_data(quote)

                # Skip if conversion failed (tick_data is None) but continue to next quote
                if tick_data is None:
                    continue

                symbol = tick_data.symbol

                logger.debug(f"Processing TickData for {symbol}: ${tick_data.close}")

                # Pass TickData to all registered DataStreamers for this symbol
                if symbol in self.data_streamers:
                    for data_streamer in self.data_streamers[symbol]:
                        try:
                            # DataStreamer now receives TickData instead of raw PIP data
                            data_streamer.process_tick(tick_data)
                        except Exception as ds_error:
                            logger.error(f"Error in DataStreamer for {symbol}: {ds_error}")
                else:
                    logger.debug(f"No DataStreamers registered for symbol: {symbol}")

            except Exception as e:
                logger.error(f"Unexpected error processing quote: {e}")
                import traceback
                traceback.print_exc()
                continue

    def add_symbol_subscription(self, symbol):
        """Add symbol to subscription list"""
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols.add(symbol)
            self.subscribe_quotes(list(self.subscribed_symbols))

    def subscribe_quotes(self, symbols: List[str]) -> bool:
        """
        Subscribe to level one quotes for specified symbols

        Args:
            symbols: List of stock symbols to track

        Returns:
            bool: Success status
        """
        if not self.is_connected:
            logger.error("Not connected to streaming API")
            return False

        # Fields to subscribe for quotes
        fields = "0,1,2,3,4,5,8,10,12,13,14,15,16,17,18,19,24,38"

        subscribe_request = {
            "requests": [
                {
                    "service": "LEVELONE_EQUITIES",
                    "requestid": self._get_next_request_id(),
                    "command": "SUBS",
                    "SchwabClientCustomerId": self.user_prefs.get('schwabClientCustomerId'),
                    "SchwabClientCorrelId": self.user_prefs.get('schwabClientCorrelId'),
                    "parameters": {
                        "keys": ",".join(symbols),
                        "fields": fields
                    }
                }
            ]
        }

        logger.info(f"Subscribing to quotes for: {symbols}")
        self.ws.send(json.dumps(subscribe_request))
        return True

    def load_historical_data(self, symbol: str, timeframe: str = "1m") -> List[TickData]:
        """
        Load historical data for the current trading session including extended hours.

        Fetches 1-minute candles with extended hours data (pre-market 4:00 AM to
        after-hours 8:00 PM ET) to capture the full trading session.

        Args:
            symbol: Stock symbol
            timeframe: Candle timeframe (1m, 5m, 15m, 30m, 1h)

        Returns:
            List of TickData objects sorted by timestamp
        """
        try:
            from datetime import datetime, timedelta
            import pytz

            # Get current time in Eastern timezone (market timezone)
            eastern = pytz.timezone('US/Eastern')
            now_et = datetime.now(eastern)

            # Check if today is a weekday (potential trading day)
            if now_et.weekday() >= 5:  # Saturday=5, Sunday=6
                logger.info(f"Weekend - no intraday history to load for {symbol}")
                return []

            # Extended hours: pre-market starts 4:00 AM ET, after-hours ends 8:00 PM ET
            extended_open = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
            extended_close = now_et.replace(hour=20, minute=0, second=0, microsecond=0)

            # Determine time range for current session (including extended hours)
            if now_et < extended_open:
                # Before pre-market open - no data yet for today
                logger.info(f"Before pre-market open - no intraday history to load for {symbol}")
                return []

            # Start from pre-market open, end at current time (or extended close)
            start_time = extended_open
            end_time = min(now_et, extended_close)

            # Convert to milliseconds for Schwab API
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(end_time.timestamp() * 1000)

            logger.info(f"Loading {timeframe} data for {symbol} - today's session: "
                       f"{start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')} ET")

            # API endpoint and auth
            url = "https://api.schwabapi.com/marketdata/v1/pricehistory"
            headers = {'Authorization': f'Bearer {self.access_token}'}

            # Simple timeframe mapping
            frequency_type = "minute"
            frequency = 1

            if timeframe == "5m":
                frequency = 5
            elif timeframe == "15m":
                frequency = 15
            elif timeframe == "30m":
                frequency = 30
            elif timeframe == "1h":
                frequency_type = "minute"
                frequency = 60

            # Use startDate/endDate for precise control over today's session only
            params = {
                'symbol': symbol,
                'periodType': 'day',
                'frequencyType': frequency_type,
                'frequency': frequency,
                'startDate': start_ms,
                'endDate': end_ms,
                'needExtendedHoursData': True
            }

            logger.info(f"API params: {params}")

            # Make request
            response = requests.get(url, headers=headers, params=params)

            # Process response
            if response.status_code != 200:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return []

            data = response.json()
            candles = data.get('candles', [])

            # Convert to TickData objects with UTC-aware timestamps
            result = []
            for candle in candles:
                # Schwab API returns timestamps as milliseconds since Unix epoch (UTC)
                # Convert to UTC-aware datetime for consistent timezone handling
                tick = TickData(
                    symbol=symbol,
                    timestamp=utc_from_timestamp_ms(candle['datetime']),
                    open=candle['open'],
                    high=candle['high'],
                    low=candle['low'],
                    close=candle['close'],
                    volume=candle.get('volume', 0),
                    time_increment=timeframe
                )
                result.append(tick)

            # Enhanced logging for debugging historical data issues
            # Display times in ET for readability (market timezone)
            if result:
                first_candle = result[0]
                last_candle = result[-1]
                logger.info(f"Loaded {len(result)} {timeframe} candles for {symbol}: "
                           f"{format_et(first_candle.timestamp, '%Y-%m-%d %H:%M')} to "
                           f"{format_et(last_candle.timestamp, '%Y-%m-%d %H:%M')} ET")
            else:
                logger.warning(f"No historical candles returned from Schwab API for {symbol} ({timeframe})")

            return result

        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
            return []

    def disconnect(self) -> None:
        """Disconnect from the streaming API"""
        if self.is_connected and self.ws:
            logout_request = {
                "requests": [
                    {
                        "service": "ADMIN",
                        "requestid": self._get_next_request_id(),
                        "command": "LOGOUT",
                        "SchwabClientCustomerId": self.user_prefs.get('schwabClientCustomerId'),
                        "SchwabClientCorrelId": self.user_prefs.get('schwabClientCorrelId'),
                        "parameters": {}
                    }
                ]
            }

            logger.info("Sending logout request")
            self.ws.send(json.dumps(logout_request))

            # Close websocket
            self.ws.close()
            self.is_connected = False
            logger.info("Disconnected from streaming API")

    #  THis is for the data dumper to use:
    def add_quote_handler(self, handler):
        """Add a quote handler function"""
        self.quote_handlers.append(handler)