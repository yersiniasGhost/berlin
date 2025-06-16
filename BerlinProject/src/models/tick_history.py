from typing import Dict, Optional
from datetime import datetime, timedelta

from bson import ObjectId
from pydantic import BaseModel, Field as PydanticField, model_validator

from models.tick_data import TickData


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


    def process_timestamps(self):
        for day, day_dict in self.data.items():
            base_date = datetime(
                year=int(self.year),
                month=int(self.month),
                day=int(day)
            )
            for seconds_from_midnight, tick in day_dict.items():
                t = base_date + timedelta(seconds=int(seconds_from_midnight))
                tick.timestamp = int(t.timestamp() * 1000)

#  TIck history tools, give it a interval date range and tickers and it should run through them.