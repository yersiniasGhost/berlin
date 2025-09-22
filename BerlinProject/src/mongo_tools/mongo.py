import re
from typing import Tuple
import pymongo.errors
from pymongo import MongoClient
from config.singleton import Singleton
from config.log_wrapper import log
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
        env = EnvVars()

        try:
            log(__name__).info(f"Connecting to MongoDB at: {env.mongo_host}:{env.mongo_port}")
            self._client = MongoClient(env.mongo_host, env.mongo_port)
            log(__name__).info(f"Using database: {env.mongo_database}")
            self._db = self._client[env.mongo_database]
        except pymongo.errors.ConfigurationError as e:
            log(__name__).error(f"An invalid mongoDB URI host error was received.")
            raise e

    @property
    def client(self):
        return self._client

    @property
    def database(self):
        return self._db
