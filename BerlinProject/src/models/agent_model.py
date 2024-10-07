from config.pyobject_id import PyObjectId
from pydantic import BaseModel, Field as PydanticField


class AgentModel(BaseModel):
    id: PyObjectId = PydanticField(None, alias="_id")
    name: str

