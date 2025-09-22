from typing import Optional
from dotenv import load_dotenv
from pathlib import Path
import os
import sys

from .singleton import Singleton


class EnvVars(metaclass=Singleton):

    def __init__(self):
        # Look for .env file in the project root directory
        project_root = Path(__file__).parent.parent.parent  # Go up from src/config/ to project root
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            print(f"Warning: .env file not found at {env_path}. Using defaults and environment variables.")
        self.env_variables = {}

        # Data provider selection
        self.data_provider = self.get_env('DATA_PROVIDER')

        # MongoDB settings
        self.mongo_host = self.get_env('MONGO_HOST', 'localhost')
        self.mongo_port = int(self.get_env('MONGO_PORT', '27017'))
        self.mongo_database = self.get_env('MONGO_DATABASE', 'MTA_devel')
        self.mongo_collection = self.get_env("MONGO_COLLECTION", "tick_history_polygon")

        # schwab settings
        self.schwab_app_key = self.get_env('SCHWAB_APP_KEY')
        self.schwab_app_secret = self.get_env('SCHWAB_APP_SECRET')
        self.schwab_redirect_uri = self.get_env('SCHWAB_REDIRECT_URI')


        # ibkr settings
        self.ibkr_host = self.get_env("IBKR_HOST")
        self.ibkr_port = self.get_env("IBKR_PORT")
        self.ibkr_client_id = self.get_env("IBKR_CLIENT_ID")

        self.ibkr_extended_hours = self.get_env("IBKR_EXTENDED_HOURS")

        # Application settings
        self.debug = self.get_bool('DEBUG', "False")
        self.log_level = self.get_env('LOG_LEVEL', 'INFO')



    def get_env(self, variable: str, default: Optional[str] = None) -> Optional[str]:
        return self.env_variables.get(variable) or self.env_variables.setdefault(
            variable,
            os.getenv(variable, default)
        )


    def _get_required(self, key: str) -> str:
        value = self.get_env(key)
        if value is None:
            raise ValueError(f"Missing required environment variable: {key}")
        return value

    def get_bool(self, key: str, default: str) -> bool:
        value = self.get_env(key, default)
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return value.lower() in ('true', '1', 'yes', 'y')
