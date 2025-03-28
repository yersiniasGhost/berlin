# In services/schwab_auth.py
import os
import base64
import requests
import logging
import webbrowser
from typing import Dict, Optional

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

        logger.info("Schwab authentication initialized with credentials from working examples")

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
                import urllib.parse
                parsed_url = urllib.parse.urlparse(returned_url)
                query_params = urllib.parse.parse_qs(parsed_url.query)

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

    def is_authenticated(self) -> bool:
        """Check if authenticated"""
        return self.access_token is not None and self.user_prefs is not None

    def get_credentials(self) -> dict:
        """Get credentials for data service"""
        return {
            "access_token": self.access_token,
            "user_prefs": self.user_prefs
        }