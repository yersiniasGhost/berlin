from typing import List, Literal
from config.types import PyObjectId, CANDLE_STICK_PATTERN, INDICATOR_TYPE
from pydantic import BaseModel, Field as PydanticField, model_validator


class IndicatorDefinition(BaseModel):
    name: str
    type: Literal[CANDLE_STICK_PATTERN, INDICATOR_TYPE]
    function: str
    parameters: dict


class IndicatorConfiguration(BaseModel):
    id: PyObjectId = PydanticField(None, alias="_id")
    name: str
    indicators: List[IndicatorDefinition]

    @model_validator(mode='before')
    def validate_definition(cls, values):
        # Convert the list of dictionaries to a list of IndicatorDefinitions
        if 'definition' in values and isinstance(values['indicators'], list):
            values['definition'] = [IndicatorDefinition(**item) for item in values['indicators']]
        return values

