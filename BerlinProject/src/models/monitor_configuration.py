# models/monitor_configuration.py
from typing import List, Dict, Optional, Set
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
        if 'indicators' in values and isinstance(values['indicators'], list):
            processed_indicators = []
            for item in values['indicators']:
                # Check if item is already an IndicatorDefinition
                if isinstance(item, IndicatorDefinition):
                    processed_indicators.append(item)
                else:
                    # Item is a dictionary, convert to IndicatorDefinition
                    processed_indicators.append(IndicatorDefinition(**item))
            values['indicators'] = processed_indicators
        return values

    def __eq__(self, other: "MonitorConfiguration"):
        return self.indicators == other.indicators

    def get_time_increments(self) -> Set[str]:
        """
        Iterate through all indicators and collect their time intervals.
        Returns a set of unique time increments used by indicators.
        """
        # Start with a default 1m timeframe
        time_increments = {"1m"}

        # Add time increments from individual indicators
        for indicator in self.indicators:
            if hasattr(indicator, 'time_increment') and indicator.time_increment:
                time_increments.add(indicator.time_increment)

        return time_increments