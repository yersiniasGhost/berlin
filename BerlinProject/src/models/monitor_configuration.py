# models/monitor_configuration.py
import json
from typing import List, Dict, Optional, Set, Any
from config.types import PyObjectId
from pydantic import BaseModel, Field as PydanticField, model_validator
from models.indicator_definition import IndicatorDefinition
import os



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

def load_monitor_config(config_file: str) -> Optional[MonitorConfiguration]:
        """Load monitor configuration from JSON file"""
        try:
            possible_paths: List[str] = [
                config_file,
                os.path.join(os.path.dirname(__file__), '..', config_file),
                os.path.join(os.path.dirname(__file__), '..', '..', config_file)
            ]

            config_path: Optional[str] = None
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break

            if not config_path:
                return None

            with open(config_path, 'r') as f:
                config_data: Dict[str, Any] = json.load(f)

            monitor_data: Dict[str, Any] = config_data.get('monitor', {})
            indicators_data: List[Dict[str, Any]] = config_data.get('indicators', [])

            indicators: List[IndicatorDefinition] = []
            for ind_data in indicators_data:
                indicator = IndicatorDefinition(
                    name=ind_data['name'],
                    type=ind_data['type'],
                    function=ind_data['function'],
                    parameters=ind_data['parameters'],
                    time_increment=ind_data.get('time_increment', '1m')
                )
                indicators.append(indicator)

            monitor_config = MonitorConfiguration(
                name=monitor_data.get('name', 'Trading Signals'),
                indicators=indicators
            )

            if 'bars' in monitor_data:
                monitor_config.bars = monitor_data['bars']

            return monitor_config

        except Exception as e:
            return None
