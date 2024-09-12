import numpy as np
from mongo_tools.sample_tools import SampleTools
from config.types import PYMONGO_ID, SAMPLE_COLLECTION
from models.profile import Profile
from mongo_tools.mongo import Mongo
from pymongo.collection import Collection


class DataStreamer:

    @classmethod
    def get_collection(cls) -> Collection:
        return Mongo().database[SAMPLE_COLLECTION]

