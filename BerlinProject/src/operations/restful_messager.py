import requests
from typing import Dict, Any, Optional
import json


class RestfulMessenger:

    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None):
        """
        Initialize the RestfulMessenger with a base URL and optional headers.

        Args:
            base_url: Base URL for all API calls
            headers: Optional dictionary of headers to include in all requests
        """
        self.base_url = base_url.rstrip('/')
        self.headers = headers or {}
        if 'Content-Type' not in self.headers:
            self.headers['Content-Type'] = 'application/json'
        # headers = {
        #     'X-Api-Key': 'your_secret_key_here',
        #     'Content-Type': 'application/json'
        # }


    def post(self, endpoint: str, data: Dict[str, Any],
             additional_headers: Optional[Dict[str, str]] = None) -> requests.Response:
        """
        Send a POST request to the specified endpoint.

        Args:
            endpoint: API endpoint to call
            data: Dictionary of data to send in the request body
            additional_headers: Optional headers to merge with default headers

        Returns:
            Response object from the request

        Raises:
            requests.exceptions.RequestException: For network/API errors
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Merge headers
        request_headers = {**self.headers}
        if additional_headers:
            request_headers.update(additional_headers)

        try:
            response = requests.post(
                url,
                data=json.dumps(data),
                headers=request_headers,
                timeout=30
            )
            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            # Log error here if needed
            raise