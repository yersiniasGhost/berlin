from typing import Dict, List, Optional, Union
from bson import ObjectId
from config.types import PYMONGO_ID, SAMPLE_COLLECTION
from data_preprocessor.data_preprocessor import TickData
from models.profile import Profile
from pymongo.collection import Collection
from mongo_tools.mongo import Mongo
import json
from pymongo import InsertOne
import logging


class SampleTools:

    def __init__(self, samples: List):
        self.samples = samples
        self.index: int = 0

    @classmethod
    def get_collection(cls) -> Collection:
        return Mongo().database[SAMPLE_COLLECTION]

    @classmethod
    def save_candle_data(cls, profile_id: PYMONGO_ID, candle_data: List[List[tuple]]) -> None:
        """
        Saves the generated candle data into the Samples collection.

        :param profile_id: The ID of the profile used to generate this data
        :param candle_data: A list of candle data lists, where each inner list represents a profile
        """
        collection = cls.get_collection()

        # Disable MongoDB operation logging
        logging.getLogger("pymongo").setLevel(logging.WARNING)

        # Prepare bulk insert operations
        operations = []
        for profile_sample in candle_data:
            doc = {
                "profile_id": ObjectId(profile_id),
                "data": [
                    {
                        "open": candle[0],
                        "high": candle[1],
                        "low": candle[2],
                        "close": candle[3]
                    }
                    for candle in profile_sample
                ]
            }
            operations.append(InsertOne(doc))

        # Perform bulk insert
        if operations:
            collection.bulk_write(operations, ordered=False)

    @classmethod
    def get_tools(cls, profiles: List[dict]) -> "SampleTools":
        samples = cls.get_samples(profiles)
        return SampleTools(samples)

    @classmethod
    def get_samples(cls, profiles: List[Dict]) -> List[Dict]:
        """
        Retrieves a specified number of random samples from the collection for multiple profiles,
        returning only the OHLC data from the nested 'data' array.

        profiles: A list of dictionaries, each containing 'profile_id' and 'number' keys
        returns: List of OHLC data dictionaries
        """
        collection = cls.get_collection()

        all_samples = []
        for profile in profiles:
            profile_id = profile['profile_id']
            sample_size = profile['number']

            query = {"profile_id": ObjectId(profile_id)}

            # Get the total count of matching documents
            total_docs = collection.count_documents(query)

            # Ensure we don't try to sample more documents than exist
            sample_size = min(sample_size, total_docs)

            # Randomly sample the documents and extract OHLC data
            pipeline = [
                {"$match": query},
                {"$sample": {"size": sample_size}},
                {"$unwind": "$data"},
                {"$project": {
                    "_id": 0,
                    "open": "$data.open",
                    "high": "$data.high",
                    "low": "$data.low",
                    "close": "$data.close"
                }}
            ]

            samples = list(collection.aggregate(pipeline))
            all_samples.extend(samples)

        return all_samples

    def reset_index(self):
        self.index=0

    def get_next(self) -> Optional[TickData]:
        if self.index < len(self.samples):
            tick_data = self.samples[self.index]
            tick = TickData(
                open=tick_data['open'],
                high=tick_data['high'],
                low=tick_data['low'],
                close=tick_data['close']
            )
            self.index += 1
            return tick
        else:
            return None

    def serve_next_tick(self):
        for tick_data in self.samples:
            tick = TickData(
                open=tick_data['open'],
                high=tick_data['high'],
                low=tick_data['low'],
                close=tick_data['close']
            )
            yield tick

    # Returns one specific sample given a pymongo id

    @classmethod
    def get_specific_sample(cls, sample_id: PYMONGO_ID) -> Optional["SampleTools"]:
        """
        Retrieves a specific sample from the collection based on its ObjectId,
        and returns a SampleTools instance with this sample's OHLC data.

        :param sample_id: The ObjectId of the specific sample to fetch
        :return: A SampleTools instance containing the sample's OHLC data, or None if no sample is found
        """
        collection = cls.get_collection()

        query = {"_id": ObjectId(sample_id)}

        # Fetch the specific document and project only the 'data' field
        sample = collection.find_one(
            query,
            projection={
                "_id": 0,
                "data": 1
            }
        )

        if sample and 'data' in sample:
            formatted_sample = [{
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"]
            } for candle in sample["data"]]

            return SampleTools(formatted_sample)
        return None