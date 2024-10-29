
from config.pyobject_id import PyObjectId
from bson import ObjectId
from pydantic import BaseModel, Field as PydanticField


class Sample(BaseModel):
    id: PyObjectId = PydanticField(None, alias="_id")
    profile_id: PyObjectId
    data: list  # This is a list of TickData
    stats: dict