from typing import List
from config.types import PyObjectId
from pydantic import BaseModel, Field as PydanticField, model_validator
from models.indicator_definition import IndicatorDefinition


class MonitorConfiguration(BaseModel):
    id: PyObjectId = PydanticField(None, alias="_id")
    name: str
    indicators: List[IndicatorDefinition]

    @model_validator(mode='before')
    def validate_definition(cls, values):
        # Convert the list of dictionaries to a list of IndicatorDefinitions
        if 'definition' in values and isinstance(values['indicators'], list):
            values['definition'] = [IndicatorDefinition(**item) for item in values['indicators']]
        return values

