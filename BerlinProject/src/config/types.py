from typing import Union
from bson.objectid import ObjectId
from config.pyobject_id import PyObjectId

PYMONGO_ID = Union[str, PyObjectId]
MONGO_ID = Union[str, ObjectId]
# DATETIME must be iso formatted string.
DATETIME = str

# Add collection names here
PROFILE_COLLECTION = ("Profiles")
SAMPLE_COLLECTION = ("Samples")

AgentActions = float
