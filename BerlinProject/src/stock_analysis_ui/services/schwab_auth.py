# In services/schwab_auth.py
import os
import base64
import requests
import logging
import json
import webbrowser
from typing import Dict, Optional
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger('SchwabAuth')


class SchwabAuthManager:
    """
    Schwab API authentication manager based on previous working implementations
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the authentication manager
        """
        # Credentials directly from the examples
        self.app_key = "QtfsQiLHpno726ZFgRDtvHA3ZItCAkcQ"
        self.app_secret = "RmwUJyBGGgW2r2C7"
        self.redirect_uri = "https://127.0.0.1"  # Original redirect URI
        self.access_token = None
        self.refresh_token = None
        self.user_prefs = None

        # Add token loading from ui_config path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_config_dir = os.path.join(os.path.dirname(current_dir), 'ui_config')
        self.token_path = os.path.join(ui_config_dir, 'schwab_tokens.json')

        # Try to load tokens
        self.load_tokens()

        logger.info("Schwab authentication initialized with credentials from working examples")

    def load_tokens(self) -> bool:
        """
        Load tokens from file

        Returns:
            bool: True if tokens were loaded successfully, False otherwise
        """
        if not os.path.exists(self.token_path):
            logger.warning(f"Token file not found: {self.token_path}")
            return False

        try:
            with open(self.token_path, 'r') as f:
                token_data = json.load(f)

            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
            self.user_prefs = token_data.get('streamer_info')

            # If we have access token but no user_prefs, try to get them
            if self.access_token and not self.user_prefs:
                self._get_streamer_info()

            if self.access_token and self.user_prefs:
                logger.info(f"Loaded tokens from {self.token_path}")
                return True
            else:
                logger.warning("Incomplete token data loaded")
                return False
        except Exception as e:
            logger.error(f"Error loading tokens: {e}")
            return False

    def save_tokens(self) -> bool:
        """
        Save tokens to file

        Returns:
            bool: True if tokens were saved successfully, False otherwise
        """
        try:
            # Make sure the directory exists
            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)

            # Save tokens
            token_data = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'streamer_info': self.user_prefs
            }

            with open(self.token_path, 'w') as f:
                json.dump(token_data, f, indent=2)

            logger.info(f"Saved tokens to {self.token_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")
            return False

    def authenticate(self):
        """
        Authenticate with Schwab API using console input method
        Returns True if successful, False otherwise
        """
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
                parsed_url = urlparse(returned_url)
                query_params = parse_qs(parsed_url.query)

                if 'code' in query_params:
                    # Get the first code value (should only be one)
                    response_code = query_params['code'][0]
                    print("Successfully extracted authorization code")
                else:
                    print("Could not find code parameter in URL")
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
                self._get_streamer_info()
                # Save tokens after successful authentication
                self.save_tokens()
                return True
            else:
                print("No access token in response")
                return False

        except Exception as e:
            print(f"Error processing authentication response: {e}")
            return False

    def _get_streamer_info(self):
        """
        Get streamer information from user preferences
        """
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

    def refresh_auth_token(self):
        """
        Refresh authentication token using refresh token

        Returns:
            bool: True if token was refreshed successfully, False otherwise
        """
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
                "refresh_token": self.refresh_token,
            }

            # Get new token
            logger.info("Refreshing access token...")
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
                # Get updated streamer info
                self._get_streamer_info()
                # Save updated tokens
                self.save_tokens()
                return True
            else:
                logger.error("No access token in refresh response")
                return False

        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False

    def is_authenticated(self) -> bool:
        """
        Check if authenticated

        Returns:
            bool: True if authenticated, False otherwise
        """
        return self.access_token is not None and self.user_prefs is not None

    def get_credentials(self) -> dict:
        """
        Get credentials for data service

        Returns:
            dict: Credentials dictionary
        """
        return {
            "access_token": self.access_token,
            "user_prefs": self.user_prefs
        }