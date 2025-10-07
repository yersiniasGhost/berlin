"""
Base classes and infrastructure for configurable technical indicators.
Provides parameter metadata, validation, and serialization for UI integration.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Union, Optional, Type, Tuple
from enum import Enum
import json
import numpy as np
from models.tick_data import TickData
from mlf_utils.singleton import Singleton


class ParameterType(Enum):
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"
    CHOICE = "choice"


@dataclass
class ParameterSpec:
    """Specification for an indicator parameter with UI metadata."""
    name: str
    display_name: str
    parameter_type: ParameterType
    default_value: Any
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    step: Optional[Union[int, float]] = None
    choices: Optional[List[str]] = None
    description: str = ""
    ui_group: str = "General"
    
    def validate(self, value: Any) -> bool:
        """Validate a parameter value against this specification."""
        if self.parameter_type == ParameterType.INTEGER:
            if not isinstance(value, int):
                return False
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False
        elif self.parameter_type == ParameterType.FLOAT:
            if not isinstance(value, (int, float)):
                return False
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False
        elif self.parameter_type == ParameterType.BOOLEAN:
            if not isinstance(value, bool):
                return False
        elif self.parameter_type == ParameterType.STRING:
            if not isinstance(value, str):
                return False
        elif self.parameter_type == ParameterType.CHOICE:
            if self.choices and value not in self.choices:
                return False
        return True


@dataclass
class IndicatorConfiguration:
    """Complete configuration for an indicator instance."""
    indicator_name: str
    display_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'indicator_name': self.indicator_name,
            'display_name': self.display_name,
            'parameters': self.parameters,
            'enabled': self.enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IndicatorConfiguration':
        """Create from dictionary (JSON deserialization)."""
        return cls(
            indicator_name=data['indicator_name'],
            display_name=data['display_name'],
            parameters=data.get('parameters', {}),
            enabled=data.get('enabled', True)
        )
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'IndicatorConfiguration':
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


class BaseIndicator(ABC):
    """Base class for all technical indicators with parameter management."""
    
    def __init__(self, config: Optional[IndicatorConfiguration] = None):
        self.config = config or self._create_default_config()
        self._validate_parameters()
    
    @classmethod
    @abstractmethod
    def name(cls) -> str:
        pass

    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for UI display."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this indicator does."""
        pass
    
    @classmethod
    @abstractmethod
    def get_parameter_specs(cls) -> List[ParameterSpec]:
        """Return list of parameter specifications for this indicator."""
        pass
    
    @abstractmethod
    def calculate(self, tick_data: List[TickData]) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Calculate indicator values for given tick data."""
        pass
    
    def _create_default_config(self) -> IndicatorConfiguration:
        """Create default configuration with default parameter values."""
        default_params = {
            spec.name: spec.default_value
            for spec in self.get_parameter_specs()
        }
        return IndicatorConfiguration(
            indicator_name=self.__class__.name(),
            display_name=self.display_name,
            parameters=default_params
        )
    
    def _validate_parameters(self):
        """Validate all parameters against specifications."""
        specs = {spec.name: spec for spec in self.get_parameter_specs()}
        
        for param_name, param_value in self.config.parameters.items():
            if param_name not in specs:
                continue
                # raise ValueError(f"Unknown parameter: {param_name}")
            
            if not specs[param_name].validate(param_value):
                raise ValueError(f"Invalid value for parameter {param_name}: {param_value}")
    
    def get_parameter(self, name: str) -> Any:
        """Get parameter value by name."""
        return self.config.parameters.get(name)
    
    def set_parameter(self, name: str, value: Any):
        """Set parameter value with validation."""
        specs = {spec.name: spec for spec in self.get_parameter_specs()}
        if name not in specs:
            raise ValueError(f"Unknown parameter: {name}")
        
        if not specs[name].validate(value):
            raise ValueError(f"Invalid value for parameter {name}: {value}")
        
        self.config.parameters[name] = value
    
    def get_ui_schema(self) -> Dict[str, Any]:
        """Generate UI schema for form generation."""
        specs = self.get_parameter_specs()
        groups = {}
        
        for spec in specs:
            if spec.ui_group not in groups:
                groups[spec.ui_group] = []
            
            field_schema = {
                'name': spec.name,
                'display_name': spec.display_name,
                'type': spec.parameter_type.value,
                'default': spec.default_value,
                'description': spec.description
            }
            
            if spec.min_value is not None:
                field_schema['min'] = spec.min_value
            if spec.max_value is not None:
                field_schema['max'] = spec.max_value
            if spec.step is not None:
                field_schema['step'] = spec.step
            if spec.choices is not None:
                field_schema['choices'] = spec.choices
            
            groups[spec.ui_group].append(field_schema)
        
        return {
            'indicator_name': self.__class__.name(),
            'display_name': self.display_name,
            'description': self.description,
            'parameter_groups': groups
        }


class IndicatorRegistry(metaclass=Singleton):
    """Registry for managing available indicators."""
    
    def __init__(self):
        self._indicators: Dict[str, Type[BaseIndicator]] = {}
    
    def register(self, indicator_class: Type[BaseIndicator]):
        """Register an indicator class."""
        self._indicators[indicator_class.__name__] = indicator_class
    
    def get_indicator_class(self, name: str) -> Type[BaseIndicator]:
        """Get indicator class by name."""
        if name not in self._indicators:
            raise ValueError(f"Unknown indicator: {name}")
        return self._indicators[name]
    
    def create_indicator(self, config: IndicatorConfiguration) -> BaseIndicator:
        """Create indicator instance from configuration."""
        indicator_class = self.get_indicator_class(config.indicator_name)
        return indicator_class(config)
    
    def get_available_indicators(self) -> List[Dict[str, str]]:
        """Get list of available indicators with basic info."""
        return [
            {
                'name': name,
                'display_name': cls.display_name,
                'description': cls.description
            }
            for name, cls in self._indicators.items()
        ]
    
    def get_ui_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get UI schemas for all registered indicators."""
        schemas = {}
        for name, cls in self._indicators.items():
            temp_instance = cls()
            schemas[name] = temp_instance.get_ui_schema()
        return schemas
