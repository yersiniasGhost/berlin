import os
import base64
import requests
import websocket
import json
import threading
import time
import webbrowser
import urllib.parse
from datetime import datetime
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("SchwabDemo")


class SimpleSchwabDemo:
    def __init__(self, auth_file_path='authentication_info.json'):
        self.auth_file_path = auth_file_path
        self.app_key = None
        self.app_secret = None
        self.redirect_uri = None
        self.access_token = None
        self.refresh_token = None
        self.ws = None
        self.is_connected = False
        self.request_id = 0
        self.user_prefs = None

        # Load authentication info
        self.load_auth_info()

    def load_auth_info(self):
        """Load authentication credentials from JSON file"""
        try:
            with open(self.auth_file_path, 'r') as auth_file:
                auth_info = json.load(auth_file)

            self.app_key = auth_info.get('api_key', '')
            self.app_secret = auth_info.get('api_secret', '')
            self.redirect_uri = auth_info.get('redirect_uri', 'https://127.0.0.1')

            print(f"Loaded authentication info for API key: {self.app_key}")
            return True
        except Exception as e:
            print(f"Error loading authentication info: {e}")
            return False

    def authenticate(self):
        """Authenticate with Schwab API using console input"""
        print("Starting authentication process...")

        # Construct auth URL
        auth_url = f"https://api.schwabapi.com/v1/oauth/authorize?client_id={self.app_key}&redirect_uri={self.redirect_uri}"

        # Open browser
        print(f"Opening browser to: {auth_url}")
        webbrowser.open(auth_url)

        # Get redirect URL with code
        print("\nAfter logging in, please copy the full URL from your browser's address bar")
        print("and paste it here (it should contain 'code='):")
        returned_url = input()

        # Extract code from URL
        try:
            if "code=" in returned_url:
                # Parse the URL
                parsed_url = urllib.parse.urlparse(returned_url)
                query_params = urllib.parse.parse_qs(parsed_url.query)

                if 'code' in query_params:
                    response_code = query_params['code'][0]
                    print("Successfully extracted authorization code")
                else:
                    print("Authorization code not found in URL parameters")
                    return False
            else:
                print("URL does not contain authorization code")
                return False

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
            print("Requesting access token...")
            token_response = requests.post(
                "https://api.schwabapi.com/v1/oauth/token",
                headers=headers,
                data=payload
            )

            # Process response
            token_data = token_response.json()

            if 'error' in token_data:
                print(f"Token error: {token_data}")
                return False

            self.access_token = token_data.get("access_token")
            self.refresh_token = token_data.get("refresh_token")

            if self.access_token:
                print("Successfully obtained access token")
                return self._get_streamer_info()
            else:
                print("No access token in response")
                return False

        except Exception as e:
            print(f"Error processing authentication response: {e}")
            return False

    def _get_streamer_info(self):
        """Get streamer information from user preferences"""
        headers = {"Authorization": f"Bearer {self.access_token}"}

        try:
            # Get user preferences
            response = requests.get(
                "https://api.schwabapi.com/trader/v1/userPreference",
                headers=headers
            )

            if response.status_code == 200:
                user_prefs = response.json()
                print("Successfully got user preferences")

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
                print(f"Error getting user preferences: {response.status_code} - {response.text}")

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
            print(f"Error getting streamer info: {e}")
            return False

    def connect_stream(self):
        """Connect to the Schwab streaming API"""
        if not self.user_prefs:
            print("No streaming configuration available")
            return False

        streamer_url = self.user_prefs.get('streamerUrl')
        print(f"Connecting to streamer URL: {streamer_url}")

        # Define WebSocket callbacks
        def on_open(ws):
            print("WebSocket connection opened")
            self.is_connected = True
            self._login()

        def on_message(ws, message):
            self._handle_message(message)

        def on_error(ws, error):
            print(f"WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            print(f"WebSocket closed: {close_status_code} - {close_msg}")
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
                print("Connection timeout")
                return False
            time.sleep(0.5)

        return True

    def _get_next_request_id(self):
        """Get next request ID"""
        self.request_id += 1
        return str(self.request_id)

    def _login(self):
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

        print("Sending login request to streamer")
        self.ws.send(json.dumps(login_request))

    def _handle_message(self, message):
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
                            print("Login to streamer successful")
                            self.subscribe_to_nvda_chart()
                        else:
                            print(f"Login to streamer failed: {content.get('msg', '')}")
                    else:
                        print(f"Response for {service}/{command}: {content}")

            # Handle data messages (chart updates)
            if 'data' in msg_data:
                for data in msg_data['data']:
                    service = data.get('service')
                    content = data.get('content', [])

                    if service == 'CHART_EQUITY' and content:
                        self.process_chart_data(content)

            # Handle notifications
            if 'notify' in msg_data:
                print(f"Notification: {msg_data['notify']}")

        except json.JSONDecodeError:
            print(f"Failed to decode message: {message}")
        except Exception as e:
            print(f"Error handling message: {e}")

    def subscribe_to_nvda_chart(self):
        """Subscribe to NVDA chart data"""
        subscribe_request = {
            "requests": [
                {
                    "service": "CHART_EQUITY",
                    "requestid": self._get_next_request_id(),
                    "command": "SUBS",
                    "SchwabClientCustomerId": self.user_prefs.get('schwabClientCustomerId'),
                    "SchwabClientCorrelId": self.user_prefs.get('schwabClientCorrelId'),
                    "parameters": {
                        "keys": "NVDA",
                        "fields": "0,1,2,3,4,5,6,7,8"
                    }
                }
            ]
        }

        print("Subscribing to NVDA chart data")
        self.ws.send(json.dumps(subscribe_request))

    def process_chart_data(self, content):
        """Process and print chart data"""
        for entry in content:
            symbol = entry.get('key', '')

            if symbol == 'NVDA':
                # Extract OHLCV data
                sequence = entry.get('0', 'N/A')
                chart_time = entry.get('1', 0)
                open_price = entry.get('2', 0.0)
                high_price = entry.get('3', 0.0)
                low_price = entry.get('4', 0.0)
                close_price = entry.get('5', 0.0)
                volume = entry.get('6', 0)
                market_time = entry.get('7', 0)

                # Convert timestamps to readable format
                chart_time_str = "N/A"
                market_time_str = "N/A"

                if market_time:
                    try:
                        market_time_str = datetime.fromtimestamp(int(market_time) / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass

                # Print the candle data
                print(f"\nNVDA Candle Data:")
                print(f"Time: {market_time_str}")
                print(f"Open: ${float(open_price):.2f}")
                print(f"High: ${float(high_price):.2f}")
                print(f"Low: ${float(low_price):.2f}")
                print(f"Close: ${float(close_price):.2f}")
                print(f"Volume: {volume}")
                print("-" * 40)

    def run(self):
        """Run the demo"""
        # Step 1: Authenticate with Schwab
        if not self.authenticate():
            print("Authentication failed")
            return

        # Step 2: Connect to the streaming API
        if not self.connect_stream():
            print("Failed to connect to streaming API")
            return

        # Step 3: Keep the script running
        print("Streaming started. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping...")

            # Disconnect from the streaming API
            if self.ws:
                self.ws.close()


if __name__ == "__main__":
    demo = SimpleSchwabDemo()
    demo.run()