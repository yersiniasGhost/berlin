from typing import List
import json
from pathlib import Path
from config.types import PyObjectId
from pydantic import BaseModel, Field as PydanticField, model_validator


class DefinitionItem(BaseModel):
    trend: List[float]
    price_variation: float
    length_fraction: List[float]


class Profile(BaseModel):
    id: PyObjectId = PydanticField(None, alias="_id")
    name: str
    definition: List[DefinitionItem]

    @model_validator(mode='before')
    def validate_definition(cls, values):
        # Convert the list of dictionaries to a list of DefinitionItem
        if 'definition' in values and isinstance(values['definition'], list):
            values['definition'] = [DefinitionItem(**item) for item in values['definition']]
        return values
