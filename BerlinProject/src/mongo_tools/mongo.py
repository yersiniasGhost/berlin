import re
from typing import Tuple
import pymongo.errors
from pymongo import MongoClient
from config.singleton import Singleton
from config.log_wrapper import log
from config.env_vars import get_required_env_var


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


DATABASE = "MTA_devel"
MONGOCLIENT = "localhost"

class Mongo(metaclass=Singleton):

    def __init__(self):
        # connection_url = get_required_env_var("MTA_MONGO_URL")
        # stripped = re.sub(r'//.*@', '//', connection_url)
        # user, pw, db = get_info_from_url(connection_url)
        try:
            # log(__name__).info(f"Connecting to MongoDB at: {stripped}")
            db = DATABASE
            self._client = MongoClient(MONGOCLIENT, 27017)
            log(__name__).info(f"Using database: {db}")
            self._db = self._client[db]
        except pymongo.errors.ConfigurationError as e:
            log(__name__).error(f"An invalid mongoDB URI host error was received.")
            raise e
        # self.connection_url = connection_url

    @property
    def client(self):
        return self._client

    @property
    def database(self):
        return self._db
