from typing import Dict, List, Optional

from config.pyobject_id import PyObjectId
from bson import ObjectId
from pydantic import BaseModel, Field as PydanticField, model_validator

from environments.tick_data import TickData




class TickHistory(BaseModel):
    id: Optional[ObjectId] = PydanticField(default_factory=ObjectId, alias="_id")
    month: int
    year: int
    ticker: str
    time_increments: int
    # Data is a dict of day of month to dict of number of seconds from midnight to tickdata
    data: Dict[str, Dict[str, TickData]]

    class Config:
        arbitrary_types_allowed = True  # Allows ObjectId
        json_encoders = {ObjectId: str}  # Serializes ObjectId to string for MongoDB

    @model_validator(mode='before')
    def validate_definition(cls, values):
        if 'data' in values and isinstance(values['data'], list):
            new_data = {}
            for item in values['data']:
                time = item.pop('time')  # Remove time from the dictionary
                new_data[time] = TickData(**item)  # Create TickData without time
            values['data'] = new_data
        return values



#  TIck history tools, give it a interval date range and tickers and it should run through them.