# models/monitor_configuration.py
from typing import List, Dict, Optional
from config.types import PyObjectId
from pydantic import BaseModel, Field as PydanticField, model_validator
from models.indicator_definition import IndicatorDefinition


class MonitorConfiguration(BaseModel):
    id: PyObjectId = PydanticField(None, alias="_id")
    name: str
    indicators: List[IndicatorDefinition]
    # Add the bars field to support your new structure
    bars: Dict[str, Dict[str, float]] = PydanticField(default_factory=dict)
    threshold: float = PydanticField(default=0.8)
    bear_threshold: float = PydanticField(default=0.8)
    description: str = PydanticField(default="")

    @model_validator(mode='before')
    def validate_definition(cls, values):
        # Convert the list of dictionaries to a list of IndicatorDefinitions
        if 'definition' in values and isinstance(values['indicators'], list):
            values['definition'] = [IndicatorDefinition(**item) for item in values['indicators']]
        return values

    def __eq__(self, other: "MonitorConfiguration"):
        return self.indicators == other.indicators