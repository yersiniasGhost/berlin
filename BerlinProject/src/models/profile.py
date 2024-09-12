
from config.pyobject_id import PyObjectId
from bson import ObjectId
from pydantic import BaseModel, Field as PydanticField


class Profile(BaseModel):
    id: PyObjectId = PydanticField(None, alias="_id")
    name: str
    definition: dict
