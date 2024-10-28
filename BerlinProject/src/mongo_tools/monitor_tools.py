from typing import Dict, List, Optional
from bson import ObjectId
from config.types import PYMONGO_ID, MONITOR_COLLECTION, PyObjectId
from models.monitor_model import Monitor
from pymongo.collection import Collection
from mongo_tools.mongo import Mongo
import json


class MonitorTools:

    @classmethod
    def get_collection(cls) -> Collection:
        return Mongo().database[MONITOR_COLLECTION]

    @classmethod
    def create_monitor(cls, monitor: Monitor):
        if not monitor.name:
            raise ValueError("Entry file must contain 'name' field")

        collection = cls.get_collection()
        monitor_dict = monitor.dict()  # Convert Monitor to dict here

        # Check if a profile with the same name already exists
        existing_profile = collection.find_one({"name": monitor_dict["name"]})
        if existing_profile:
            raise ValueError(f"Entry has document with name {monitor_dict['name']} already!")

        result = collection.insert_one(monitor_dict)  # Insert the dict instead of monitor
        monitor.id = result.inserted_id

    @classmethod
    def get_profile(cls, name: str) -> Monitor:
        data = cls.get_collection().find_one(name)
        monitor = Monitor(**data)
        return monitor

    @classmethod
    def list_profiles(cls) -> List[Dict]:
        collection = cls.get_collection()
        profiles = collection.find({}, {"_id": 1, "name": 1})
        return list(profiles)

    @classmethod
    def update_profile(cls, monitor: Monitor):
        collection = cls.get_collection()
        monitor_dict = monitor.dict(by_alias=True)
        monitor_dict.pop('_id', None)  # Remove _id field

        result = collection.update_one(
            {"_id": monitor.id},
            {"$set": monitor_dict}
        )

        return bool(result.modified_count)

