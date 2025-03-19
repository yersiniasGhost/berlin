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

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SchwabClient')


class SchwabClient:
    def __init__(self, config_path=None):
        # Hardcoded credentials that work
        self.app_key = "QtfsQiLHpno726ZFgRDtvHA3ZItCAkcQ"
        self.app_secret = "RmwUJyBGGgW2r2C7"
        self.redirect_uri = "https://127.0.0.1"

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

    def authenticate(self):
        """Authenticate using the approach from the working example"""
        # Construct auth URL
        auth_url = f"https://api.schwabapi.com/v1/oauth/authorize?client_id={self.app_key}&redirect_uri={self.redirect_uri}"

        # Print authorization URL instead of opening browser
        logger.info(f"Please manually visit this URL to authenticate:")
        logger.info(auth_url)

        # Get redirect URL with code
        logger.info("After authenticating, paste the URL you were redirected to:")
        returned_url = input()

        try:
            # Extract code
            code_start = returned_url.index('code=') + 5
            code_end = returned_url.index('%40')
            response_code = f"{returned_url[code_start:code_end]}@"

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
                # Try to get streamer info from GET user preferences
                self._get_streamer_info()
                return True
            else:
                logger.error("No access token in response")
                return False

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    def _get_streamer_info(self):
        # After authentication, try to get streaming info
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

    def connect_stream(self):
        """Connect to streaming API"""
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
            logger.error(f"Failed to decode message: {message}")
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