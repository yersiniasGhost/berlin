from typing import Dict, List, Optional, Union, Any
from bson import ObjectId
from config.types import PYMONGO_ID, SAMPLE_COLLECTION
from data_preprocessor.data_preprocessor import TickData
from models.profile import Profile
from pymongo.collection import Collection
from mongo_tools.mongo import Mongo
import json
from pymongo import InsertOne
import logging
from typing import List, Dict, Optional
from bson import ObjectId

class SampleTools:
    def __init__(self, samples: List[Dict[str, any]] = None):
        self.samples = samples or []
        self.tick_index: int = 0
        self.sample_index: int = 0

    @classmethod
    def get_collection(cls) -> Collection:
        return Mongo().database[SAMPLE_COLLECTION]

    @classmethod
    def get_tools(cls, profiles: List[dict]) -> "SampleTools":
        all_samples = []
        for profile in profiles:
            samples = cls.get_samples2(profile)
            all_samples.extend(samples.samples)
        return SampleTools(all_samples)

    @classmethod
    def get_samples2(cls, profile: Dict) -> 'SampleTools':
        collection = cls.get_collection()

        profile_id = profile['profile_id']
        sample_size = profile['number']

        query = {"profile_id": ObjectId(profile_id)}

        pipeline = [
            {"$match": query},
            {"$sample": {"size": sample_size}},
            {"$project": {
                "_id": 0,
                "data": 1,
                "stats": 1
            }}
        ]

        samples = list(collection.aggregate(pipeline))

        processed_samples = [
            {
                "ticks": [
                    TickData(
                        open=tick['open'],
                        high=tick['high'],
                        low=tick['low'],
                        close=tick['close'],
                        volume=tick.get('volume')
                    )
                    for tick in sample["data"]
                ],
                "stats": sample["stats"]
            }
            for sample in samples
        ]

        return cls(processed_samples)

    def get_stats(self):
        if self.sample_index >= len(self.samples):
            raise ValueError("No more samples available")
        return self.samples[self.sample_index]["stats"]

    def get_next2(self) -> Optional[TickData]:
        if self.sample_index >= len(self.samples):
            return None

        current_sample = self.samples[self.sample_index]["ticks"]

        if self.tick_index < len(current_sample):
            tick_data = current_sample[self.tick_index]
            self.tick_index += 1
            return tick_data

        # Move to the next sample
        self.sample_index += 1
        self.tick_index = 0
        return self.get_next2()

    def reset_index(self):
        self.tick_index = 0
        self.sample_index = 0

    @classmethod
    def save_candle_data(cls, profile_id: str, candle_data: List[Dict[str, Any]]) -> None:
        """
        Saves the generated candle data and stats into the Samples collection.

        :param profile_id: The ID of the profile used to generate this data
        :param candle_data: A list of dictionaries, each containing 'data' and 'stats' for a profile
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
                    for candle in profile_sample['data']
                ],
                "stats": profile_sample['stats']
            }
            operations.append(InsertOne(doc))

        # Perform bulk insert
        if operations:
            collection.bulk_write(operations, ordered=False)

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
    def get_specific_sample(cls, profile_id: str) -> 'SampleTools':
        collection = cls.get_collection()
        query = {"profile_id": ObjectId(profile_id)}
        samples = list(collection.find(query).limit(1))
        if not samples:
            print(f"No sample found for profile_id: {profile_id}")
            return cls([])  # Return an empty SampleTools instance

        processed_samples = [
            [
                TickData(
                    open=tick['open'],
                    high=tick['high'],
                    low=tick['low'],
                    close=tick['close'],
                    volume=tick.get('volume')
                )
                for tick in sample["data"]
            ]
            for sample in samples
        ]

        print(
            f"Retrieved {len(processed_samples)} samples with {sum(len(sample) for sample in processed_samples)} total ticks for profile_id: {profile_id}")
        return cls(processed_samples)

    # @classmethod
    # def get_tools(cls, profiles: List[dict]) -> "SampleTools":
    #     samples = cls.get_samples2(profiles)
    #     return SampleTools(samples)

    # @classmethod
    # def get_samples(cls, profiles: List[Dict]) -> List[Dict]:
    #     """
    #     Retrieves a specified number of random samples from the collection for multiple profiles,
    #     returning only the OHLC data from the nested 'data' array.
    #
    #     profiles: A list of dictionaries, each containing 'profile_id' and 'number' keys
    #     returns: List of OHLC data dictionaries
    #     """
    #     collection = cls.get_collection()
    #
    #     all_samples = []
    #     for profile in profiles:
    #         profile_id = profile['profile_id']
    #         sample_size = profile['number']
    #
    #         query = {"profile_id": ObjectId(profile_id)}
    #
    #         # Get the total count of matching documents
    #         total_docs = collection.count_documents(query)
    #
    #         # Ensure we don't try to sample more documents than exist
    #         sample_size = min(sample_size, total_docs)
    #
    #         # Randomly sample the documents and extract OHLC data
    #         pipeline = [
    #             {"$match": query},
    #             {"$sample": {"size": sample_size}},
    #             {"$unwind": "$data"},
    #             {"$project": {
    #                 "_id": 0,
    #                 "open": "$data.open",
    #                 "high": "$data.high",
    #                 "low": "$data.low",
    #                 "close": "$data.close"
    #             }}
    #         ]
    #
    #         samples = list(collection.aggregate(pipeline))
    #         all_samples.extend(samples)
    #
    #     return all_samples
    #
    # def get_next(self) -> Optional[TickData]:
    #     if self.tick_index < len(self.samples):
    #         tick_data = self.samples[self.tick_index]
    #         tick = TickData(
    #             open=tick_data['open'],
    #             high=tick_data['high'],
    #             low=tick_data['low'],
    #             close=tick_data['close']
    #         )
    #         self.tick_index += 1
    #         return tick
    #     else:
    #         return None
