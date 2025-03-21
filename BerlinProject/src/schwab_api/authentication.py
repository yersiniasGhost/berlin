import os
import base64
import requests
import webbrowser
import websocket
import json
import logging
import time
import threading
from typing import Dict, List, Any, Optional, Callable
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import socket

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SchwabClient')


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback"""

    def do_GET(self):
        """Handle GET request to callback URL"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        # Return simple HTML to indicate success
        self.wfile.write(
            b"<html><body><h1>Authentication Successful!</h1><p>You can close this window and return to the application.</p></body></html>")

        # Store the URL path and query parameters
        self.server.callback_path = self.path


class SchwabClient:
    def __init__(self, config_path=None, app_key=None, app_secret=None, redirect_uri=None, token_path=None):
        # Use provided credentials or load from config
        self.app_key = app_key
        self.app_secret = app_secret
        self.redirect_uri = redirect_uri or "https://127.0.0.1:8182"
        self.token_path = token_path

        # Load config if provided
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.app_key = config.get('app_key', self.app_key)
                    self.app_secret = config.get('app_secret', self.app_secret)
                    self.redirect_uri = config.get('redirect_uri', self.redirect_uri)
                    self.token_path = config.get('token_path', self.token_path)
            except Exception as e:
                logger.error(f"Error loading config: {e}")

        # Streaming connection
        self.access_token = None
        self.refresh_token = None
        self.user_prefs = None
        self.ws = None
        self.is_connected = False
        self.request_id = 0

        # Callbacks for services
        self.callbacks = {
            'LEVELONE_EQUITIES': [],
            'CHART_EQUITY': []
        }

        # Try to load tokens if token path is provided
        if self.token_path and os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'r') as f:
                    tokens = json.load(f)
                    self.access_token = tokens.get('access_token')
                    self.refresh_token = tokens.get('refresh_token')
                    logger.info("Loaded tokens from file")
            except Exception as e:
                logger.error(f"Error loading tokens: {e}")

    def authenticate(self, use_local_server=True):
        """
        Authenticate using OAuth flow with optional local server for callback

        Args:
            use_local_server: If True, start a local server to catch the callback
        """
        # Construct auth URL
        auth_url = f"https://api.schwabapi.com/v1/oauth/authorize?client_id={self.app_key}&redirect_uri={self.redirect_uri}"

        logger.info(f"Opening authorization URL in browser: {auth_url}")
        webbrowser.open(auth_url)

        # Determine if we should use local server or manual input
        if use_local_server and "127.0.0.1" in self.redirect_uri:
            # Extract port from redirect URI
            parsed_uri = urlparse(self.redirect_uri)
            host = parsed_uri.hostname
            port = parsed_uri.port or 8182

            # Start HTTP server for callback
            server_address = (host, port)
            httpd = HTTPServer(server_address, CallbackHandler)
            httpd.callback_path = None

            # Run server in a thread
            server_thread = threading.Thread(target=self._run_server, args=(httpd,))
            server_thread.daemon = True
            server_thread.start()

            logger.info(f"Waiting for callback on {host}:{port}...")

            # Wait for callback
            timeout = 120  # 2 minutes
            start_time = time.time()
            while httpd.callback_path is None:
                if time.time() - start_time > timeout:
                    logger.error("Authentication timeout")
                    return False
                time.sleep(0.5)

            # Process the callback
            callback_url = f"{self.redirect_uri}{httpd.callback_path}"
            logger.info("Received callback")

            # Shutdown server
            httpd.shutdown()
            server_thread.join()
        else:
            # Manual input
            logger.info("Please manually visit this URL to authenticate:")
            logger.info(auth_url)
            logger.info("After authenticating, paste the URL you were redirected to:")
            callback_url = input()

        # Extract code from callback URL
        try:
            # Parse the URL to extract the code
            parsed_url = urlparse(callback_url)
            query_params = parse_qs(parsed_url.query)

            if 'code' in query_params:
                response_code = query_params['code'][0]
            else:
                # Alternative parsing (backup method)
                code_start = callback_url.index('code=') + 5
                if '@' in callback_url:
                    code_end = callback_url.index('%40')
                    response_code = f"{callback_url[code_start:code_end]}@"
                else:
                    code_end = callback_url.find('&', code_start)
                    if code_end == -1:
                        response_code = callback_url[code_start:]
                    else:
                        response_code = callback_url[code_start:code_end]

            # Encode credentials
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

                # Save tokens if token path is provided
                if self.token_path:
                    try:
                        with open(self.token_path, 'w') as f:
                            json.dump({
                                'access_token': self.access_token,
                                'refresh_token': self.refresh_token
                            }, f)
                        logger.info(f"Saved tokens to {self.token_path}")
                    except Exception as e:
                        logger.error(f"Error saving tokens: {e}")

                # Try to get streamer info
                self._get_streamer_info()
                return True
            else:
                logger.error("No access token in response")
                return False

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    def _run_server(self, httpd):
        """Run HTTP server to catch OAuth callback"""
        try:
            httpd.serve_forever()
        except Exception as e:
            logger.error(f"Server error: {e}")

    def refresh_auth_token(self):
        """Refresh the authentication token using the refresh token"""
        if not self.refresh_token:
            logger.error("No refresh token available")
            return False

        try:
            # Encode credentials
            credentials = f"{self.app_key}:{self.app_secret}"
            base64_credentials = base64.b64encode(credentials.encode()).decode()

            # Set up headers and payload
            headers = {
                "Authorization": f"Basic {base64_credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            payload = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token
            }

            # Get new token
            token_response = requests.post(
                "https://api.schwabapi.com/v1/oauth/token",
                headers=headers,
                data=payload
            )

            # Process response
            token_data = token_response.json()

            if 'error' in token_data:
                logger.error(f"Token refresh error: {token_data}")
                return False

            self.access_token = token_data.get("access_token")
            self.refresh_token = token_data.get("refresh_token")

            if self.access_token:
                logger.info("Successfully refreshed access token")

                # Save tokens if token path is provided
                if self.token_path:
                    try:
                        with open(self.token_path, 'w') as f:
                            json.dump({
                                'access_token': self.access_token,
                                'refresh_token': self.refresh_token
                            }, f)
                        logger.info(f"Saved refreshed tokens to {self.token_path}")
                    except Exception as e:
                        logger.error(f"Error saving tokens: {e}")

                return True
            else:
                logger.error("No access token in refresh response")
                return False

        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False

    def _get_streamer_info(self):
        """Get streaming info from user preferences"""
        # After authentication, try to get streaming info
        if not self.access_token:
            logger.error("No access token available")
            return False

        headers = {"Authorization": f"Bearer {self.access_token}"}

        try:
            # Try the specific preferences endpoint
            response = requests.get("https://api.schwabapi.com/trader/v1/userPreference", headers=headers)

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
        except Exception as e:
            logger.error(f"Error getting streamer info: {e}")

        # Default values as fallback
        self.user_prefs = {
            "streamerUrl": "wss://gateway-sip.schwab.com/streamer",
            "schwabClientCustomerId": "DEFAULT_ID",
            "schwabClientCorrelId": "DEFAULT_ID",
            "channel": "IO",
            "functionId": "APIAPP"
        }
        return False

    def create_streaming_session(self):
        """Create a streaming session using the SchwabStreamerClient"""
        from streamer_client import SchwabStreamerClient

        if not self.user_prefs or not self.access_token:
            logger.error("No streaming configuration or access token available")
            return None

        # Create a new streaming client
        try:
            streaming_client = SchwabStreamerClient(self.user_prefs, self.access_token)
            # Connect to the streaming API
            connected = streaming_client.connect()

            if connected:
                logger.info("Successfully created streaming session")
                return streaming_client
            else:
                logger.error("Failed to connect streaming session")
                return None
        except Exception as e:
            logger.error(f"Error creating streaming session: {e}")
            return None

    def connect_stream(self):
        """
        Connect to streaming API (legacy method, use create_streaming_session instead)

        Returns:
            bool: True if connection was successful, False otherwise
        """
        if not self.user_prefs:
            logger.error("No streaming configuration available")
            return False

        streamer_url = self.user_prefs.get('streamerUrl')
        logger.info(f"Connecting to streamer URL: {streamer_url}")

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

        try:
            self.ws = websocket.WebSocketApp(
                streamer_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )

            # Start websocket in a thread
            thread = threading.Thread(target=self.ws.run_forever, kwargs={'ping_interval': 30, 'ping_timeout': 10})
            thread.daemon = True
            thread.start()

            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self.is_connected:
                if time.time() - start_time > timeout:
                    logger.error("Connection timeout")
                    return False
                time.sleep(0.5)

            return True
        except Exception as e:
            logger.error(f"Error connecting to stream: {e}")
            return False

    def _get_next_request_id(self):
        """Get next request ID"""
        self.request_id += 1
        return str(self.request_id)

    def _login(self):
        """Send login request to streaming API"""
        customer_id = self.user_prefs.get('schwabClientCustomerId')
        correl_id = self.user_prefs.get('schwabClientCorrelId')
        client_channel = self.user_prefs.get('channel')
        function_id = self.user_prefs.get('functionId')

        login_request = {
            "requests": [
                {
                    "service": "ADMIN",
                    "requestid": self._get_next_request_id(),
                    "command": "LOGIN",
                    "SchwabClientCustomerId": customer_id,
                    "SchwabClientCorrelId": correl_id,
                    "parameters": {
                        "Authorization": self.access_token,
                        "SchwabClientChannel": client_channel,
                        "SchwabClientFunctionId": function_id
                    }
                }
            ]
        }

        logger.info("Sending login request to streamer")
        self.ws.send(json.dumps(login_request))

    def _handle_message(self, message: str):
        """Handle incoming messages from streaming API"""
        try:
            msg_data = json.loads(message)
            logger.debug(f"Received message: {msg_data}")

            # Handle response messages
            if 'response' in msg_data:
                for response in msg_data['response']:
                    service = response.get('service')
                    command = response.get('command')
                    content = response.get('content', {})

                    if service == 'ADMIN' and command == 'LOGIN':
                        code = content.get('code')
                        if code == 0:
                            logger.info("Login to streamer successful")
                        else:
                            logger.error(f"Login to streamer failed: {content.get('msg', '')}")
                    else:
                        logger.info(f"Response for {service}/{command}: {content}")

            # Handle data messages
            if 'data' in msg_data:
                for data in msg_data['data']:
                    service = data.get('service')
                    content = data.get('content', [])

                    if service in self.callbacks and content:
                        for callback in self.callbacks[service]:
                            callback(content)

            # Handle notifications
            if 'notify' in msg_data:
                logger.debug(f"Notification: {msg_data['notify']}")

        except json.JSONDecodeError:
            logger.error(logger.error(f"Failed to decode message: {message}"))
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def subscribe_quotes(self, symbols: List[str], callback: Callable[[List[Dict]], None]):
        """Subscribe to real-time quotes for specified symbols"""
        if not self.is_connected:
            logger.error("Not connected to streaming API")
            return False

        self.callbacks['LEVELONE_EQUITIES'] = [callback]

        customer_id = self.user_prefs.get('schwabClientCustomerId')
        correl_id = self.user_prefs.get('schwabClientCorrelId')

        # Fields for level one quotes
        fields = "0,1,2,3,4,5,8,10,12,13,14,15,16,17,18,19"

        subscribe_request = {
            "requests": [
                {
                    "service": "LEVELONE_EQUITIES",
                    "requestid": self._get_next_request_id(),
                    "command": "SUBS",
                    "SchwabClientCustomerId": customer_id,
                    "SchwabClientCorrelId": correl_id,
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

    def subscribe_charts(self, symbols: List[str], callback: Callable[[List[Dict]], None]):
        """Subscribe to chart data for specified symbols"""
        if not self.is_connected:
            logger.error("Not connected to streaming API")
            return False

        self.callbacks['CHART_EQUITY'] = [callback]

        customer_id = self.user_prefs.get('schwabClientCustomerId')
        correl_id = self.user_prefs.get('schwabClientCorrelId')

        # Fields for chart data
        fields = "0,1,2,3,4,5,6,7,8"

        subscribe_request = {
            "requests": [
                {
                    "service": "CHART_EQUITY",
                    "requestid": self._get_next_request_id(),
                    "command": "SUBS",
                    "SchwabClientCustomerId": customer_id,
                    "SchwabClientCorrelId": correl_id,
                    "parameters": {
                        "keys": ",".join(symbols),
                        "fields": fields
                    }
                }
            ]
        }

        logger.info(f"Subscribing to charts for: {symbols}")
        self.ws.send(json.dumps(subscribe_request))
        return True

    def price_history(self, symbol, periodType="day", period=1,
                      frequencyType="minute", frequency=1,
                      startDate=None, endDate=None,
                      needExtendedHoursData=False, needPreviousClose=False):
        """Get price history for a symbol"""
        if not self.access_token:
            logger.error("No access token available")
            return None

        url = f"{self._base_api_url}/marketdata/v1/pricehistory"

        params = {
            'symbol': symbol,
            'periodType': periodType,
            'period': period,
            'frequencyType': frequencyType,
            'frequency': frequency
        }

        if startDate is not None:
            params['startDate'] = startDate
        if endDate is not None:
            params['endDate'] = endDate
        if needExtendedHoursData:
            params['needExtendedHoursData'] = needExtendedHoursData
        if needPreviousClose:
            params['needPreviousClose'] = needPreviousClose

        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }

        response = requests.get(url, headers=headers, params=params)
        logger.info(f"Price history response status: {response.status_code}")

        return response

    # Add base API URL class attribute
    _base_api_url = "https://api.schwabapi.com"

    def disconnect(self):
        """Disconnect from streaming API"""
        if self.is_connected and self.ws:
            customer_id = self.user_prefs.get('schwabClientCustomerId')
            correl_id = self.user_prefs.get('schwabClientCorrelId')

            logout_request = {
                "requests": [
                    {
                        "service": "ADMIN",
                        "requestid": self._get_next_request_id(),
                        "command": "LOGOUT",
                        "SchwabClientCustomerId": customer_id,
                        "SchwabClientCorrelId": correl_id,
                        "parameters": {}
                    }
                ]
            }

            logger.info("Sending logout request")
            self.ws.send(json.dumps(logout_request))

            # Close WebSocket
            self.ws.close()
            self.is_connected = False
            logger.info("Disconnected from streaming API")


# Helper function to create an easy client
def easy_client(app_key=None, app_secret=None, callback_url=None, token_path=None):
    """
    Create and authenticate a SchwabClient with simplified setup

    Args:
        app_key: Schwab API key
        app_secret: Schwab API secret
        callback_url: OAuth callback URL
        token_path: Path to store/load tokens

    Returns:
        SchwabClient: Authenticated client
    """
    client = SchwabClient(
        app_key=app_key,
        app_secret=app_secret,
        redirect_uri=callback_url,
        token_path=token_path
    )

    # Check if we already have valid tokens
    if client.access_token:
        # Test the token by getting user preferences
        try:
            headers = {"Authorization": f"Bearer {client.access_token}"}
            response = requests.get(
                "https://api.schwabapi.com/trader/v1/userPreference",
                headers=headers
            )

            if response.status_code == 200:
                logger.info("Existing access token is valid")
                client._get_streamer_info()
                return client
            else:
                logger.info("Access token expired, trying refresh")
                success = client.refresh_auth_token()
                if success:
                    client._get_streamer_info()
                    return client
        except Exception as e:
            logger.error(f"Error testing token: {e}")

    # If we don't have tokens or they're invalid, authenticate
    logger.info("Starting authentication flow")
    success = client.authenticate(use_local_server=True)

    if success:
        logger.info("Authentication successful")
        return client
    else:
        logger.error("Authentication failed")
        return None