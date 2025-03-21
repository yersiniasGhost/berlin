import websocket
import json
import threading
import time
import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime


class SchwabStreamerClient:
    """
    Client for connecting to Schwab Streamer API and receiving market data.
    Uses WebSocket protocol to establish a connection and subscribe to various data streams.
    """

    def __init__(self, user_prefs: Dict, access_token: str):
        """
        Initialize the Schwab Streamer client with user preferences and access token.

        Args:
            user_prefs: Dictionary containing user preferences from GET User Preference endpoint
            access_token: Access token from POST Token endpoint
        """
        self.user_prefs = user_prefs
        self.access_token = access_token
        self.customer_id = user_prefs.get('schwabClientCustomerId')
        self.correl_id = user_prefs.get('schwabClientCorrelId')
        self.client_channel = user_prefs.get('channel')
        self.client_function_id = user_prefs.get('functionId')

        # WebSocket connection
        self.ws = None
        self.ws_url = user_prefs.get('streamerUrl', 'wss://streamer.schwab.com/streamer')
        self.is_connected = False
        self.request_id = 0

        # Callbacks for different services
        self.callbacks = {
            'LEVELONE_EQUITIES': [],
            'CHART_EQUITY': [],
            'ACCT_ACTIVITY': []
        }

        # Setup logging
        self.logger = logging.getLogger('SchwabStreamer')
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _get_next_request_id(self) -> str:
        """Get the next request ID as a string."""
        self.request_id += 1
        return str(self.request_id)

    def connect(self) -> bool:
        """
        Connect to the Schwab Streamer API and login.

        Returns:
            bool: True if login was successful, False otherwise
        """
        self.logger.info(f"Connecting to {self.ws_url}")

        # Define WebSocket callbacks
        def on_open(ws):
            self.logger.info("Connection opened")
            self.is_connected = True
            self._login()

        def on_message(ws, message):
            self._handle_message(message)

        def on_error(ws, error):
            self.logger.error(f"WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            self.logger.info(f"Connection closed: {close_status_code} - {close_msg}")
            self.is_connected = False

        # Create WebSocket connection
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )

        # Start WebSocket connection in a separate thread
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()

        # Wait for connection to be established
        timeout = 10
        start_time = time.time()
        while not self.is_connected:
            if time.time() - start_time > timeout:
                self.logger.error("Connection timeout")
                return False
            time.sleep(0.1)

        return True

    def _login(self):
        """Send login request to the Schwab Streamer API."""
        login_request = {
            "requests": [
                {
                    "service": "ADMIN",
                    "requestid": self._get_next_request_id(),
                    "command": "LOGIN",
                    "SchwabClientCustomerId": self.customer_id,
                    "SchwabClientCorrelId": self.correl_id,
                    "parameters": {
                        "Authorization": self.access_token,
                        "SchwabClientChannel": self.client_channel,
                        "SchwabClientFunctionId": self.client_function_id
                    }
                }
            ]
        }

        self.logger.info("Sending login request")
        self.ws.send(json.dumps(login_request))

    def _handle_message(self, message: str):
        """
        Handle incoming messages from the Schwab Streamer API.

        Args:
            message: JSON string message from the WebSocket
        """
        try:
            msg_data = json.loads(message)
            self.logger.debug(f"Received message: {msg_data}")

            # Handle response messages
            if 'response' in msg_data:
                for response in msg_data['response']:
                    self._handle_response(response)

            # Handle data messages
            if 'data' in msg_data:
                for data in msg_data['data']:
                    self._handle_data(data)

            # Handle notify messages (heartbeats)
            if 'notify' in msg_data:
                self.logger.debug(f"Heartbeat: {msg_data['notify']}")

        except json.JSONDecodeError:
            self.logger.error(f"Failed to decode message: {message}")
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

    def _handle_response(self, response: Dict):
        """
        Handle response messages from the Schwab Streamer API.

        Args:
            response: Dictionary containing response data
        """
        service = response.get('service')
        command = response.get('command')
        content = response.get('content', {})
        code = content.get('code')
        msg = content.get('msg', '')

        if service == 'ADMIN' and command == 'LOGIN':
            if code == 0:
                self.logger.info(f"Login successful: {msg}")
            else:
                self.logger.error(f"Login failed: {msg}")
        else:
            self.logger.info(f"Response for {service}/{command}: {content}")

    def _handle_data(self, data: Dict):
        """
        Handle data messages from the Schwab Streamer API.

        Args:
            data: Dictionary containing data
        """
        service = data.get('service')
        content = data.get('content', [])

        if service in self.callbacks:
            for callback in self.callbacks[service]:
                callback(content)

    def subscribe_quotes(self, symbols: List[str], callback: Callable[[List[Dict]], None]):
        """
        Subscribe to level one quotes for specified symbols.

        Args:
            symbols: List of stock symbols (e.g., ['AAPL', 'TSLA'])
            callback: Function to call when new quote data is received
        """
        if not self.is_connected:
            self.logger.error("Not connected to Schwab Streamer API")
            return

        self.callbacks['LEVELONE_EQUITIES'].append(callback)

        # Fields to request for quotes
        # 0=Symbol, 1=Bid Price, 2=Ask Price, 3=Last Price, 4=Bid Size, 5=Ask Size,
        # 8=Volume, 10=Last Size, 12=High Price, 13=Low Price, 14=Bid Tick, 15=Close Price,
        # 16=Exchange ID, 17=Marginable, 18=Shortable, 19=Island Bid, 24=Volatility, 38=Market Maker
        fields = "0,1,2,3,4,5,8,10,12,13,14,15,16,17,18,19,24,38"

        subscribe_request = {
            "requests": [
                {
                    "service": "LEVELONE_EQUITIES",
                    "requestid": self._get_next_request_id(),
                    "command": "SUBS",
                    "SchwabClientCustomerId": self.customer_id,
                    "SchwabClientCorrelId": self.correl_id,
                    "parameters": {
                        "keys": ",".join(symbols),
                        "fields": fields
                    }
                }
            ]
        }

        self.logger.info(f"Subscribing to quotes for: {symbols}")
        self.ws.send(json.dumps(subscribe_request))

    def subscribe_charts(self, symbols: List[str], callback: Callable[[List[Dict]], None]):
        """
        Subscribe to minute charts for specified symbols.

        Args:
            symbols: List of stock symbols (e.g., ['AAPL', 'TSLA'])
            callback: Function to call when new chart data is received
        """
        if not self.is_connected:
            self.logger.error("Not connected to Schwab Streamer API")
            return

        self.callbacks['CHART_EQUITY'].append(callback)

        # Fields for chart data:
        # 0=Sequence, 1=Chart Time (UNIX timestamp)
        # 2=Open Price, 3=High Price, 4=Low Price, 5=Close Price, 6=Volume
        # 7=Market DateTime (UNIX timestamp), 8=Cumulative Volume
        fields = "0,1,2,3,4,5,6,7,8"

        subscribe_request = {
            "requests": [
                {
                    "service": "CHART_EQUITY",
                    "requestid": self._get_next_request_id(),
                    "command": "SUBS",
                    "SchwabClientCustomerId": self.customer_id,
                    "SchwabClientCorrelId": self.correl_id,
                    "parameters": {
                        "keys": ",".join(symbols),
                        "fields": fields
                    }
                }
            ]
        }

        self.logger.info(f"Subscribing to charts for: {symbols}")
        self.ws.send(json.dumps(subscribe_request))

    def add_chart_symbols(self, symbols: List[str]):
        """
        Add symbols to an existing chart subscription.

        Args:
            symbols: List of additional stock symbols to subscribe to
        """
        if not self.is_connected:
            self.logger.error("Not connected to Schwab Streamer API")
            return

        add_request = {
            "requests": [
                {
                    "service": "CHART_EQUITY",
                    "requestid": self._get_next_request_id(),
                    "command": "ADD",
                    "SchwabClientCustomerId": self.customer_id,
                    "SchwabClientCorrelId": self.correl_id,
                    "parameters": {
                        "keys": ",".join(symbols)
                    }
                }
            ]
        }

        self.logger.info(f"Adding chart symbols: {symbols}")
        self.ws.send(json.dumps(add_request))

    def unsubscribe_charts(self, symbols: List[str]):
        """
        Unsubscribe from chart data for specified symbols.

        Args:
            symbols: List of stock symbols to unsubscribe from
        """
        if not self.is_connected:
            self.logger.error("Not connected to Schwab Streamer API")
            return

        unsub_request = {
            "requests": [
                {
                    "service": "CHART_EQUITY",
                    "requestid": self._get_next_request_id(),
                    "command": "UNSUBS",
                    "SchwabClientCustomerId": self.customer_id,
                    "SchwabClientCorrelId": self.correl_id,
                    "parameters": {
                        "keys": ",".join(symbols)
                    }
                }
            ]
        }

        self.logger.info(f"Unsubscribing from charts for: {symbols}")
        self.ws.send(json.dumps(unsub_request))

    def subscribe_account_activity(self, callback: Callable[[List[Dict]], None]):
        """
        Subscribe to account activity.

        Args:
            callback: Function to call when new account activity is received
        """
        if not self.is_connected:
            self.logger.error("Not connected to Schwab Streamer API")
            return

        self.callbacks['ACCT_ACTIVITY'].append(callback)

        subscribe_request = {
            "requests": [
                {
                    "service": "ACCT_ACTIVITY",
                    "requestid": self._get_next_request_id(),
                    "command": "SUBS",
                    "SchwabClientCustomerId": self.customer_id,
                    "SchwabClientCorrelId": self.correl_id,
                    "parameters": {
                        "keys": "Account Activity",
                        "fields": "0,1,2,3"
                    }
                }
            ]
        }

        self.logger.info("Subscribing to account activity")
        self.ws.send(json.dumps(subscribe_request))

    def disconnect(self):
        """Disconnect from the Schwab Streamer API."""
        if self.is_connected and self.ws:
            logout_request = {
                "requests": [
                    {
                        "service": "ADMIN",
                        "requestid": self._get_next_request_id(),
                        "command": "LOGOUT",
                        "SchwabClientCustomerId": self.customer_id,
                        "SchwabClientCorrelId": self.correl_id,
                        "parameters": {}
                    }
                ]
            }

            self.logger.info("Sending logout request")
            self.ws.send(json.dumps(logout_request))

            # Close WebSocket connection
            self.ws.close()
            self.is_connected = False
            self.logger.info("Disconnected from Schwab Streamer API")