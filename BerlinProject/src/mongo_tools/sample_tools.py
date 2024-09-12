from typing import Dict, List, Optional, Union
from bson import ObjectId
from config.types import PYMONGO_ID, SAMPLE_COLLECTION
from models.profile import Profile
from pymongo.collection import Collection
from mongo_tools.mongo import Mongo
import json
from pymongo import InsertOne
import logging


class SampleTools:
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
    def get_samples(cls, profile_ids: Union[str, List[str]], num_samples: Union[int, List[int]]) -> List[Dict]:
        """
        Retrieves a specified number of random samples from the collection for one or multiple profile IDs.

        profile_ids: A single profile ID string or a list of profile ID strings
        num_samples: A single integer or a list of integers specifying the number of samples for each profile ID
        returns: List of sample documents
        """
        collection = cls.get_collection()

        # Convert inputs to lists if they're not already
        if isinstance(profile_ids, str):
            profile_ids = [profile_ids]
        if isinstance(num_samples, int):
            num_samples = [num_samples]

        # Ensure profile_ids and num_samples have the same length
        if len(profile_ids) != len(num_samples):
            raise ValueError("The number of profile IDs must match the number of sample sizes")

        samples = []
        for profile_id, sample_size in zip(profile_ids, num_samples):
            query = {"profile_id": ObjectId(profile_id)}

            # Get the total count of matching documents
            total_docs = collection.count_documents(query)

            # Ensure we don't try to sample more documents than exist
            sample_size = min(sample_size, total_docs)

            # Randomly sample the documents
            pipeline = [
                {"$match": query},
                {"$sample": {"size": sample_size}}
            ]

            samples.extend(list(collection.aggregate(pipeline)))

        return samples

