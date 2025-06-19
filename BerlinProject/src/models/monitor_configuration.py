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
    """Load monitor configuration from JSON file with improved path resolution"""
    try:
        import os

        # First, try the path as-is (absolute or relative to current working directory)
        if os.path.exists(config_file):
            config_path = config_file
        else:
            # Try multiple possible locations
            current_dir = os.path.dirname(os.path.abspath(__file__))
            possible_paths = [
                # Same directory as this module
                os.path.join(current_dir, config_file),
                # Parent directory of this module
                os.path.join(os.path.dirname(current_dir), config_file),
                # Two levels up from this module (BerlinProject/src/models -> BerlinProject)
                os.path.join(os.path.dirname(os.path.dirname(current_dir)), config_file),
                # Current working directory
                os.path.join(os.getcwd(), config_file),
                # Check if it's in the project root
                os.path.join(os.getcwd(), "src", config_file),
                # Check common config locations
                os.path.join(os.getcwd(), "config", config_file),
                os.path.join(os.getcwd(), "configs", config_file),
            ]

            config_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    print(f"Found config file at: {config_path}")
                    break

            if not config_path:
                print(f"Config file not found: {config_file}")
                print(f"Searched in the following locations:")
                for path in possible_paths:
                    print(f"  - {path}")
                return None

        # Load and parse the config file
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
                time_increment=ind_data.get('time_increment'),
                calc_on_pip=ind_data.get('calc_on_pip')
            )
            indicators.append(indicator)

        # FIXED: Properly extract threshold and bear_threshold from monitor_data
        monitor_config = MonitorConfiguration(
            name=monitor_data.get('name', 'Trading Signals'),
            indicators=indicators,
            threshold=monitor_data.get('threshold', 0.8),  # Get from JSON or default
            bear_threshold=monitor_data.get('bear_threshold', 0.8),  # Get from JSON or default
            description=monitor_data.get('description', '')
        )

        # FIXED: Properly set bars from monitor_data
        if 'bars' in monitor_data:
            monitor_config.bars = monitor_data['bars']

        print(f"Successfully loaded config: {monitor_config.name}")
        print(f"  Threshold: {monitor_config.threshold}")
        print(f"  Bear Threshold: {monitor_config.bear_threshold}")
        print(f"  Indicators: {len(indicators)}")
        print(f"  Bars: {list(monitor_config.bars.keys())}")

        return monitor_config

    except Exception as e:
        print(f"Error loading monitor config: {e}")
        import traceback
        traceback.print_exc()
        return None