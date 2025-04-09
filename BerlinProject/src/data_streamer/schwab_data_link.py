# schwab_data_link.py
import os
import base64
import requests
import websocket
import json
import threading
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Iterator, Tuple

from data_streamer.data_link import DataLink
from environments.tick_data import TickData

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SchwabDataLink')


class SchwabDataLink(DataLink):
    """
    A simplified class for connecting to Schwab API and streaming market data.
    """

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        pass

    def reset_index(self) -> None:
        pass

    def get_next2(self) -> Optional[TickData]:
        pass

    def serve_next_tick(self) -> Iterator[Tuple[TickData, int, int]]:
        pass

    def __init__(self):
        # Hardcoded authentication credentials
        self.app_key = "QtfsQiLHpno726ZFgRDtvHA3ZItCAkcQ"
        self.app_secret = "RmwUJyBGGgW2r2C7"
        self.redirect_uri = "https://127.0.0.1"
        self.access_token = None
        self.refresh_token = None

        # Streamer configuration
        self.user_prefs = None
        self.ws = None  # WebSocket connection
        self.is_connected = False
        self.request_id = 0

        # Data handlers
        self.quote_handlers = []
        self.chart_handlers = []

        logger.info(f"Initialized SchwabDataLink with API key: {self.app_key}")

    def load_auth_info(self):
        """Load authentication credentials from JSON file"""
        try:
            with open(self.auth_file_path, 'r') as auth_file:
                auth_info = json.load(auth_file)

            # Make sure we're using the exact keys from your JSON file
            self.app_key = auth_info.get('api_key', auth_info.get('app_key', ''))
            self.app_secret = auth_info.get('api_secret', auth_info.get('app_secret', ''))
            self.redirect_uri = auth_info.get('redirect_uri', 'https://127.0.0.1')

            logger.info(f"Loaded authentication info for API key: {self.app_key}")
            return True
        except Exception as e:
            logger.error(f"Error loading authentication info: {e}")
            return False

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

                    elif service == 'CHART_EQUITY' and content:
                        self._handle_chart_data(content)

            # Handle notifications
            if 'notify' in msg_data:
                logger.info(f"Notification: {msg_data['notify']}")

        except json.JSONDecodeError:
            logger.error(f"Failed to decode message: {message}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _handle_quote_data(self, data: List[Dict]) -> None:
        """Process quote data and pass to handlers"""
        for quote in data:
            try:
                # Call all registered quote handlers
                for handler in self.quote_handlers:
                    handler(quote)
            except Exception as e:
                logger.error(f"Error in quote handler: {e}")

    def _handle_chart_data(self, data: List[Dict]) -> None:
        """Process chart data and pass to handlers"""
        for chart_entry in data:
            try:
                # Call all registered chart handlers
                for handler in self.chart_handlers:
                    handler(chart_entry)
            except Exception as e:
                logger.error(f"Error in chart handler: {e}")

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

    def subscribe_charts(self, symbols: List[str], timeframe: str = "1m") -> bool:
        """
        Subscribe to chart data for specified symbols

        Args:
            symbols: List of stock symbols
            timeframe: Candle timeframe (1m, 5m, 15m, 30m, 1h, 1d)

        Returns:
            bool: Success status
        """
        if not self.is_connected:
            logger.error("Not connected to streaming API")
            return False

        # Map timeframe string to frequency parameters
        timeframe_mapping = {
            "1m": {"frequency_type": "minute", "frequency": 1},
            "5m": {"frequency_type": "minute", "frequency": 5},
            "15m": {"frequency_type": "minute", "frequency": 15},
            "30m": {"frequency_type": "minute", "frequency": 30},
            "1h": {"frequency_type": "hour", "frequency": 1},
            "1d": {"frequency_type": "daily", "frequency": 1}
        }

        tf_params = timeframe_mapping.get(timeframe, timeframe_mapping["1m"])

        # Fields for chart data
        fields = "0,1,2,3,4,5,6,7,8"

        subscribe_request = {
            "requests": [
                {
                    "service": "CHART_EQUITY",
                    "requestid": self._get_next_request_id(),
                    "command": "SUBS",
                    "SchwabClientCustomerId": self.user_prefs.get('schwabClientCustomerId'),
                    "SchwabClientCorrelId": self.user_prefs.get('schwabClientCorrelId'),
                    "parameters": {
                        "keys": ",".join(symbols),
                        "fields": fields,
                        "frequency_type": tf_params["frequency_type"],
                        "frequency": tf_params["frequency"]
                    }
                }
            ]
        }

        logger.info(f"Subscribing to charts for: {symbols} with timeframe {timeframe}")
        self.ws.send(json.dumps(subscribe_request))
        return True


    def load_historical_data(self, symbol: str, timeframe: str = "1m") -> List[Dict]:
        """
        Load historical candle data for ONLY the current trading day

        Args:
            symbol: Stock symbol
            timeframe: Candle timeframe (1m, 5m, 15m, 30m, 1h, 1d)

        Returns:
            List of candle dictionaries
        """
        if not self.access_token:
            logger.error("No access token available")
            return []

        # Get today's date
        from datetime import datetime, timedelta
        today = datetime.now().date()

        # Calculate start time - Use today's pre-market (4 AM ET)
        start_time = datetime.combine(today, datetime.min.time().replace(hour=4, minute=0))

        # Convert to milliseconds timestamp for API
        start_timestamp = int(start_time.timestamp() * 1000)

        # Explicitly set end time to current time
        end_time = datetime.now()
        end_timestamp = int(end_time.timestamp() * 1000)

        # Map timeframe string to API parameters
        timeframe_mapping = {
            "1m": {"periodType": "day", "period": 1, "frequencyType": "minute", "frequency": 1},
            "5m": {"periodType": "day", "period": 1, "frequencyType": "minute", "frequency": 5},
            "15m": {"periodType": "day", "period": 1, "frequencyType": "minute", "frequency": 15},
            "30m": {"periodType": "day", "period": 1, "frequencyType": "minute", "frequency": 30},
            "1h": {"periodType": "day", "period": 1, "frequencyType": "hour", "frequency": 1},
            "1d": {"periodType": "month", "period": 1, "frequencyType": "daily", "frequency": 1}
        }

        tf_params = timeframe_mapping.get(timeframe, timeframe_mapping["1m"])

        logger.info(f"Loading historical data for {symbol} with timeframe {timeframe}")
        logger.info(f"Using time range: {start_time} to {end_time}")

        try:
            url = "https://api.schwabapi.com/marketdata/v1/pricehistory"

            params = {
                'symbol': symbol,
                'periodType': tf_params["periodType"],
                'period': tf_params["period"],
                'frequencyType': tf_params["frequencyType"],
                'frequency': tf_params["frequency"],
                'startDate': start_timestamp,
                'endDate': end_timestamp,
                'needExtendedHoursData': True
            }

            headers = {
                'Authorization': f'Bearer {self.access_token}'
            }

            logger.info(f"Requesting historical data for {symbol} from {url}")

            response = requests.get(url, headers=headers, params=params)

            logger.info(f"Response status code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                if 'candles' in data:
                    candles = data['candles']
                    logger.info(f"Found {len(candles)} candles in response")

                    processed_candles = []
                    for candle in candles:
                        timestamp = datetime.fromtimestamp(candle['datetime'] / 1000)

                        # Only include candles from today
                        if timestamp.date() == today:
                            processed_candle = {
                                'symbol': symbol,
                                'timestamp': timestamp,
                                'open': candle['open'],
                                'high': candle['high'],
                                'low': candle['low'],
                                'close': candle['close'],
                                'volume': candle.get('volume', 0)
                            }

                            processed_candles.append(processed_candle)

                    logger.info(f"Processed {len(processed_candles)} candles for today ({today})")
                    return processed_candles
                else:
                    logger.warning(f"No 'candles' key in API response")
                    return []
            else:
                logger.error(f"API returned error: {response.status_code} - {response.text}")

                # Try without explicit endDate if we get a date range error
                if "endDate" in response.text and "startDate" in response.text:
                    logger.info("Retrying request without explicit endDate parameter")
                    params.pop('endDate', None)

                    response = requests.get(url, headers=headers, params=params)

                    if response.status_code == 200:
                        data = response.json()

                        if 'candles' in data:
                            candles = data['candles']
                            logger.info(f"Found {len(candles)} candles in retry response")

                            processed_candles = []
                            for candle in candles:
                                timestamp = datetime.fromtimestamp(candle['datetime'] / 1000)

                                # Only include candles from today
                                if timestamp.date() == today:
                                    processed_candle = {
                                        'symbol': symbol,
                                        'timestamp': timestamp,
                                        'open': candle['open'],
                                        'high': candle['high'],
                                        'low': candle['low'],
                                        'close': candle['close'],
                                        'volume': candle.get('volume', 0)
                                    }

                                    processed_candles.append(processed_candle)

                            logger.info(f"Processed {len(processed_candles)} candles for today ({today}) in retry")
                            return processed_candles

                    else:
                        logger.error(f"Retry also failed: {response.status_code} - {response.text}")

                return []

        except Exception as e:
            logger.error(f"Exception during historical data loading: {e}")
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