# models/monitor_configuration.py
import json
from typing import List, Dict, Optional, Set, Any
from config.types import PyObjectId
from pydantic import BaseModel, Field as PydanticField, model_validator
from models.indicator_definition import IndicatorDefinition
import os

# models/monitor_configuration.py
import json
from typing import List, Dict, Optional, Set, Any
from config.types import PyObjectId
from pydantic import BaseModel, Field as PydanticField, model_validator
from models.indicator_definition import IndicatorDefinition
import os


class TradeExecutorConfig(BaseModel):
    """Configuration for trade executor parameters"""
    default_position_size: float = PydanticField(default=100.0)
    stop_loss_pct: float = PydanticField(default=0.01)
    take_profit_pct: float = PydanticField(default=0.02)

    # Take profit type: "percent" (default) or "dollars"
    take_profit_type: str = PydanticField(default="percent")
    # Dollar amount target for take profit (used when take_profit_type="dollars")
    take_profit_dollars: float = PydanticField(default=0.0)
    # Halt trading after hitting dollar target (only applies when take_profit_type="dollars")
    halt_after_target: bool = PydanticField(default=False)

    # Behavior flags
    ignore_bear_signals: bool = PydanticField(default=False)
    # Exit all positions by end of day (market close)
    exit_by_end_of_day: bool = PydanticField(default=False)
    # Note: check_signal_conflicts is always True and not configurable

    # Trailing stop loss configuration
    trailing_stop_loss: bool = PydanticField(default=False)
    trailing_stop_distance_pct: float = PydanticField(default=0.01)
    trailing_stop_activation_pct: float = PydanticField(default=0.005)


class MonitorConfiguration(BaseModel):
    id: Optional[PyObjectId] = PydanticField(None, alias="_id")
    name: str
    description: str = PydanticField(default="")

    # NEW: Required trade executor configuration
    trade_executor: TradeExecutorConfig

    # Arrays of conditions instead of single objects
    enter_long: List[Dict[str, Any]] = PydanticField(default_factory=list)
    exit_long: List[Dict[str, Any]] = PydanticField(default_factory=list)

    bars: Dict[str, Any] = PydanticField(default_factory=dict)
    indicators: List[IndicatorDefinition] = PydanticField(default_factory=list)

    user_id: Optional[PyObjectId] = PydanticField(None)

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

        # ENFORCE: trade_executor configuration is required
        if 'trade_executor' in values and isinstance(values['trade_executor'], dict):
            values['trade_executor'] = TradeExecutorConfig(**values['trade_executor'])
        elif 'trade_executor' not in values:
            raise ValueError(
                "trade_executor configuration is required - please add trade_executor section to your JSON config")

        return values

    def __eq__(self, other: "MonitorConfiguration"):
        return (self.indicators == other.indicators and
                self.trade_executor == other.trade_executor)

    def get_time_increments(self) -> Set[str]:
        """Get all unique timeframes from indicators"""
        timeframes = set()
        for indicator in self.indicators:
            timeframes.add(indicator.get_timeframe())
        return timeframes

    def get_aggregator_configs(self) -> Dict[str, str]:
        """
        Get mapping of unique aggregator keys to aggregator types

        Returns:
            Dict like {'1m-normal': 'normal', '1m-heiken': 'heiken'}
        """
        configs = {}
        for indicator in self.indicators:
            timeframe = indicator.get_timeframe()
            agg_type = indicator.get_aggregator_type()

            # Create unique key for this timeframe+aggregator combination
            agg_key = f"{timeframe}-{agg_type}"  # ← This creates unique keys!

            configs[agg_key] = agg_type

        return configs


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

        # Process indicators
        indicators: List[IndicatorDefinition] = []
        for ind_data in indicators_data:
            indicator = IndicatorDefinition(
                name=ind_data['name'],
                type=ind_data['type'],
                indicator_class=ind_data['indicator_class'],
                parameters=ind_data['parameters'],
                agg_config=ind_data.get('agg_config'),
                calc_on_pip=ind_data.get('calc_on_pip', False),
                ranges=ind_data.get('ranges')
            )
            indicators.append(indicator)

        # Build configuration dictionary - NEW STRUCTURE
        config_dict = {
            'name': monitor_data.get('name', 'Trading Signals'),
            'description': monitor_data.get('description', ''),
            'indicators': indicators,
        }

        # Handle new enter_long array structure
        if 'enter_long' in monitor_data:
            enter_long = monitor_data['enter_long']
            if isinstance(enter_long, list):
                # Already an array
                config_dict['enter_long'] = enter_long
            elif isinstance(enter_long, dict):
                # Convert single object to array
                config_dict['enter_long'] = [enter_long]
        else:
            config_dict['enter_long'] = []

        # Handle new exit_long array structure
        if 'exit_long' in monitor_data:
            exit_long = monitor_data['exit_long']
            if isinstance(exit_long, list):
                # Already an array
                config_dict['exit_long'] = exit_long
            elif isinstance(exit_long, dict):
                # Convert single object to array
                config_dict['exit_long'] = [exit_long]
        else:
            config_dict['exit_long'] = []

        # Only add bars if they exist in JSON
        if 'bars' in monitor_data:
            config_dict['bars'] = monitor_data['bars']

        # REQUIRED: Add trade_executor configuration
        if 'trade_executor' in monitor_data:
            config_dict['trade_executor'] = monitor_data['trade_executor']
        else:
            raise ValueError("trade_executor configuration is required - please add trade_executor section to your JSON config")

        # Create MonitorConfiguration and let Pydantic handle defaults
        monitor_config = MonitorConfiguration(**config_dict)

        print(f"Successfully loaded config: {monitor_config.name}")
        print(f"  Description: {monitor_config.description}")
        print(f"  Enter conditions: {len(monitor_config.enter_long)}")
        print(f"  Exit conditions: {len(monitor_config.exit_long)}")
        print(f"  Indicators: {len(indicators)}")
        print(f"  Bars: {list(monitor_config.bars.keys())}")

        return monitor_config

    except Exception as e:
        print(f"Error loading monitor config: {e}")
        import traceback
        traceback.print_exc()
        return None
