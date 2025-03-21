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
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from collections import deque
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SchwabDashboard')


class CandleDashboard:
    def __init__(self, auth_file_path='../../src/schwab_api/authentication_info.json'):
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

        # Data storage
        self.symbols = ['NVDA', 'PLTR']
        self.candle_data = {}
        for symbol in self.symbols:
            self.candle_data[symbol] = {
                'timestamps': deque(maxlen=100),
                'open': deque(maxlen=100),
                'high': deque(maxlen=100),
                'low': deque(maxlen=100),
                'close': deque(maxlen=100),
                'volume': deque(maxlen=100)
            }

        # UI components
        self.root = None
        self.fig = None
        self.canvas = None
        self.axes = {}

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
                    logger.info("Successfully extracted authorization code")
                else:
                    logger.error("Authorization code not found in URL parameters")
                    return False
            else:
                logger.error("URL does not contain authorization code")
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
                return self._get_streamer_info()
            else:
                logger.error("No access token in response")
                return False

        except Exception as e:
            logger.error(f"Error processing authentication response: {e}")
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
                return False

        except Exception as e:
            logger.error(f"Error getting streamer info: {e}")
            return False

    def connect_stream(self):
        """Connect to the Schwab streaming API"""
        if not self.user_prefs:
            logger.error("No streaming configuration available")
            return False

        streamer_url = self.user_prefs.get('streamerUrl')
        logger.info(f"Connecting to streamer URL: {streamer_url}")

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

        logger.info("Sending login request to streamer")
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
                            logger.info("Login to streamer successful")
                            self.subscribe_to_symbols()
                        else:
                            logger.error(f"Login to streamer failed: {content.get('msg', '')}")
                    else:
                        logger.info(f"Response for {service}/{command}: {content}")

            # Handle data messages (chart updates)
            if 'data' in msg_data:
                for data in msg_data['data']:
                    service = data.get('service')
                    content = data.get('content', [])

                    if service == 'CHART_EQUITY' and content:
                        self.process_chart_data(content)
                        self.update_charts()

        except json.JSONDecodeError:
            logger.error(f"Failed to decode message: {message}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def subscribe_to_symbols(self):
        """Subscribe to chart data for symbols"""
        subscribe_request = {
            "requests": [
                {
                    "service": "CHART_EQUITY",
                    "requestid": self._get_next_request_id(),
                    "command": "SUBS",
                    "SchwabClientCustomerId": self.user_prefs.get('schwabClientCustomerId'),
                    "SchwabClientCorrelId": self.user_prefs.get('schwabClientCorrelId'),
                    "parameters": {
                        "keys": ",".join(self.symbols),
                        "fields": "0,1,2,3,4,5,6,7,8"
                    }
                }
            ]
        }

        logger.info(f"Subscribing to chart data for: {self.symbols}")
        self.ws.send(json.dumps(subscribe_request))

    def process_chart_data(self, content):
        """Process chart data and store in data structure"""
        for entry in content:
            symbol = entry.get('key', '')

            if symbol in self.symbols:
                # Extract OHLCV data
                sequence = entry.get('0', 'N/A')
                chart_time = entry.get('1', 0)
                open_price = float(entry.get('2', 0.0))
                high_price = float(entry.get('3', 0.0))
                low_price = float(entry.get('4', 0.0))
                close_price = float(entry.get('5', 0.0))
                volume = float(entry.get('6', 0))
                market_time = entry.get('7', 0)

                # Convert timestamps to readable format
                market_time_str = "N/A"
                if market_time:
                    try:
                        market_time_str = datetime.fromtimestamp(int(market_time) / 1000).strftime('%Y-%m-%d %H:%M:%S')
                        # Store data
                        self.candle_data[symbol]['timestamps'].append(datetime.fromtimestamp(int(market_time) / 1000))
                        self.candle_data[symbol]['open'].append(open_price)
                        self.candle_data[symbol]['high'].append(high_price)
                        self.candle_data[symbol]['low'].append(low_price)
                        self.candle_data[symbol]['close'].append(close_price)
                        self.candle_data[symbol]['volume'].append(volume)

                        # Log the data
                        logger.info(
                            f"{symbol} Candle: O:{open_price:.2f} H:{high_price:.2f} L:{low_price:.2f} C:{close_price:.2f} V:{volume}")
                    except Exception as e:
                        logger.error(f"Error processing time for {symbol}: {e}")

    def init_ui(self):
        """Initialize the user interface"""
        # Create root window
        self.root = tk.Tk()
        self.root.title("Real-time Stock Dashboard")
        self.root.geometry("1200x800")

        # Create a frame for the charts
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Create a status bar
        self.status_var = tk.StringVar(value="Connecting...")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Create matplotlib figure with subplots
        self.fig = Figure(figsize=(12, 8), constrained_layout=True)

        # Create subplots
        rows = len(self.symbols)
        for i, symbol in enumerate(self.symbols):
            self.axes[symbol] = self.fig.add_subplot(rows, 1, i + 1)
            self.axes[symbol].set_title(f"{symbol} Price Chart")
            self.axes[symbol].set_xlabel("Time")
            self.axes[symbol].set_ylabel("Price")
            self.axes[symbol].grid(True, alpha=0.3)

            # Add initial empty text
            self.axes[symbol].text(0.5, 0.5, "Waiting for data...",
                                   horizontalalignment='center',
                                   verticalalignment='center',
                                   transform=self.axes[symbol].transAxes,
                                   fontsize=14)

        # Add the figure to the Tkinter window
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas.draw()

        # Schedule the first update
        self.root.after(1000, self.update_status)

        return True

    def update_status(self):
        """Update the status bar"""
        if self.is_connected:
            self.status_var.set("Connected to Schwab API - Streaming data")
        else:
            self.status_var.set("Disconnected")

        # Schedule the next update
        self.root.after(1000, self.update_status)

    def update_charts(self):
        """Update the matplotlib charts with new data"""
        for symbol in self.symbols:
            if len(self.candle_data[symbol]['timestamps']) > 0:
                ax = self.axes[symbol]
                ax.clear()

                # Format title with latest price
                latest_close = self.candle_data[symbol]['close'][-1] if self.candle_data[symbol]['close'] else 0
                ax.set_title(f"{symbol} - ${latest_close:.2f}")

                # Plot price line
                ax.plot(self.candle_data[symbol]['timestamps'],
                        self.candle_data[symbol]['close'],
                        'b-', label='Price')

                # Add candlesticks
                width = 0.0005  # Width of candles in datetime units
                for i in range(len(self.candle_data[symbol]['timestamps'])):
                    # Determine if candle is up or down
                    if self.candle_data[symbol]['close'][i] >= self.candle_data[symbol]['open'][i]:
                        color = 'g'  # Green for up
                    else:
                        color = 'r'  # Red for down

                    # Plot candle body
                    ax.bar(self.candle_data[symbol]['timestamps'][i],
                           abs(self.candle_data[symbol]['close'][i] - self.candle_data[symbol]['open'][i]),
                           width,
                           bottom=min(self.candle_data[symbol]['open'][i], self.candle_data[symbol]['close'][i]),
                           color=color,
                           alpha=0.6)

                    # Plot wicks
                    ax.plot([self.candle_data[symbol]['timestamps'][i], self.candle_data[symbol]['timestamps'][i]],
                            [self.candle_data[symbol]['low'][i], self.candle_data[symbol]['high'][i]],
                            color='black',
                            linewidth=1)

                # Format axes
                ax.grid(True, alpha=0.3)
                ax.set_xlabel("Time")
                ax.set_ylabel("Price")

                # Format time axis
                ax.tick_params(axis='x', rotation=45)

                # Set y-limits with some padding
                if len(self.candle_data[symbol]['high']) > 0:
                    y_min = min(self.candle_data[symbol]['low']) * 0.998
                    y_max = max(self.candle_data[symbol]['high']) * 1.002
                    ax.set_ylim(y_min, y_max)

        # Draw the updated figure
        self.canvas.draw()

    def run(self):
        """Run the dashboard"""
        # Step 1: Authenticate with Schwab
        if not self.authenticate():
            logger.error("Authentication failed")
            return

        # Step 2: Connect to the streaming API
        if not self.connect_stream():
            logger.error("Failed to connect to streaming API")
            return

        # Step 3: Initialize the UI
        if not self.init_ui():
            logger.error("Failed to initialize UI")
            return

        # Step 4: Start the main loop
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            logger.info("Stopping...")

            # Disconnect from the streaming API
            if self.ws:
                self.ws.close()


if __name__ == "__main__":
    dashboard = CandleDashboard()
    dashboard.run()