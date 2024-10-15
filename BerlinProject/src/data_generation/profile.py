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

    def get_sections(self):
        return self.definition

    def number_of_sections(self):
        return len(self.definition)

    @classmethod
    def from_json(cls, path: Path) -> "Profile":
        if not path.exists():
            raise ValueError(f'Path does not exist: {path}')
        with open(path, 'r') as file:
            profile_definition = json.load(file)
            return Profile(**profile_definition)


from config.types import PyObjectId
profile_data = {
    "_id": "65282509bfe2a75cfc13f623",
    "name": "example_profile",
    "definition": [
        {"trend": [0.0, 0.05], "price_variation": 0.005, "length_fraction": [0.2, 0.15]},
        {"trend": [5, 0.5], "price_variation": 0.005, "length_fraction": [0.6, 0.2]},
        {"trend": [0.0, 0.05], "price_variation": 0.005, "length_fraction": [0.2, 0.15]}
    ]
}

profile = Profile(**profile_data)