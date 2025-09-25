import re
from typing import Tuple
import pymongo.errors
from pymongo import MongoClient
from mlf_utils.singleton import Singleton
from mlf_utils.log_manager import LogManager
from config.env_vars import EnvVars


def get_info_from_url(url: str) -> Tuple[str, str, str]:
    pattern = r'mongodb\+srv://(\w+):(\w+)@(\w+).'
    match = re.search(pattern, url)
    if match:
        # Extract the values of word1 and word2
        user = match.group(1)
        pw = match.group(2)
        db = match.group(3)
        return user, pw, db
    raise Exception(f"Not able to find user/pass form URL")


class Mongo(metaclass=Singleton):

    def __init__(self):
        # Get configuration from environment variables
        self.logger = LogManager().get_logger("Mongo")
        env = EnvVars()

        try:
            self.logger.info(f"Connecting to MongoDB at: {env.mongo_host}:{env.mongo_port}")
            self._client = MongoClient(env.mongo_host, env.mongo_port)
            self.logger.info(f"Using database: {env.mongo_database}")
            self._db = self._client[env.mongo_database]
        except pymongo.errors.ConfigurationError as e:
            self.logger.error(f"An invalid mongoDB URI host error was received.")
            raise e

    @property
    def client(self):
        return self._client

    @property
    def database(self):
        return self._db
