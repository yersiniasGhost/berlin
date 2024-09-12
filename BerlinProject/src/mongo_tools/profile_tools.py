from typing import Dict, List, Optional
from bson import ObjectId
from config.types import PYMONGO_ID, PROFILE_COLLECTION
from models.profile import Profile
from pymongo.collection import Collection
from mongo_tools.mongo import Mongo
import json


class ProfileTools:
    @classmethod
    def get_collection(cls) -> Collection:
        return Mongo().database[PROFILE_COLLECTION]

    @classmethod
    def create_profile(cls, json_file_path: str) -> Optional[str]:
        """
        Creates a new profile document from a JSON file if a profile with the same name doesn't exist.

        json_file_path: Path to the JSON file containing profile data
        returns: ID of the created profile document, or None if a profile with the same name already exists
        """
        try:
            with open(json_file_path, 'r') as file:
                profile_data = json.load(file)

            if "name" not in profile_data or "definition" not in profile_data:
                raise ValueError("JSON file must contain 'name' and 'definition' fields")

            collection = cls.get_collection()

            # Check if a profile with the same name already exists
            existing_profile = collection.find_one({"name": profile_data["name"]})
            if existing_profile:
                print(f"A profile with the name '{profile_data['name']}' already exists.")
                return None

            # If no existing profile found, insert the new one
            result = collection.insert_one(profile_data)
            return str(result.inserted_id)

        except FileNotFoundError:
            raise FileNotFoundError(f"JSON file not found: {json_file_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in file: {json_file_path}")

    @classmethod
    def get_profile(cls, profile_id: PYMONGO_ID) -> Optional[Dict]:
        collection = cls.get_collection()
        profile = collection.find_one(
            {"_id": ObjectId(profile_id)},
            {"_id": 0, "name": 1, "definition": 1}
        )
        return profile

    @classmethod
    def delete_profile(cls, profile_id: PYMONGO_ID) -> bool:
        collection = cls.get_collection()
        result = collection.delete_one({"_id": ObjectId(profile_id)})
        return result.deleted_count > 0

    @classmethod
    def list_profiles(cls) -> List[Dict]:
        collection = cls.get_collection()
        profiles = collection.find({}, {"_id": 1, "name": 1})
        return list(profiles)

    @classmethod
    def update_profile(cls, profile: Profile) -> bool:
        collection = cls.get_collection()
        profile_dict = profile.dict(by_alias=True, exclude_unset=True)
        result = collection.update_one(
            {"_id": profile.id},
            {"$set": profile_dict}
        )
        return result.modified_count > 0