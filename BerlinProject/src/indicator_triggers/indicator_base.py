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
    LIST = "list"


class IndicatorType(Enum):
    """Classification of indicator types for different calculation flows."""
    SIGNAL = "signal"  # Traditional trigger indicators (crossovers, patterns, etc.)
    TREND = "trend"    # Trend direction/strength indicators (ADX, EMA slope, etc.)


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

    @classmethod
    def get_layout_type(cls) -> str:
        """Return layout type for visualization: 'overlay' or 'stacked'."""
        return "overlay"  # Default to overlay for most indicators

    @classmethod
    def get_indicator_type(cls) -> IndicatorType:
        """Return indicator type: SIGNAL or TREND.

        SIGNAL indicators generate entry/exit triggers (crossovers, patterns).
        TREND indicators provide direction/strength for gating signal indicators.

        Override in subclasses to change the type.
        """
        return IndicatorType.SIGNAL  # Default for backward compatibility

    @classmethod
    def get_chart_config(cls) -> Dict[str, Any]:
        """Return chart configuration for frontend visualization.

        Override in subclasses to customize chart appearance. The frontend uses
        this config to render charts data-driven, without hardcoded class name checks.

        Returns:
            Dict with chart configuration:
            - chart_type: Type identifier (e.g., "adx", "macd", "generic")
            - title_suffix: Suffix for chart title (e.g., "ADX Trend Analysis")
            - components: List of component configs with keys, colors, line styles
            - y_axis: Y-axis configuration (min, max, title)
            - reference_lines: List of horizontal reference lines with thresholds
        """
        return {
            "chart_type": "generic",
            "title_suffix": "Raw Values",
            "components": [],  # Empty = auto-discover components from component_history
            "y_axis": {},
            "reference_lines": []
        }

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
        """
        Validate all parameters against specifications.
        Raises ValueError with detailed message if validation fails.
        - ALL parameters must be present (no auto-fill with defaults)
        - ALL values must match their specs (type, range, choices, etc.)
        """
        specs = {spec.name: spec for spec in self.get_parameter_specs()}
        errors = []

        # Check for MISSING required parameters
        for spec_name in specs:
            if spec_name not in self.config.parameters:
                errors.append(f"Missing required parameter: '{spec_name}'")

        # Validate each PROVIDED parameter
        for param_name, param_value in self.config.parameters.items():
            if param_name not in specs:
                errors.append(f"Unknown parameter: '{param_name}' (not defined in indicator specs)")
                continue

            spec = specs[param_name]
            validation_error = self._validate_single_parameter(spec, param_value)
            if validation_error:
                errors.append(validation_error)

        # Raise exception with ALL errors if any validation failed
        if errors:
            error_msg = f"Parameter validation failed for {self.__class__.__name__}:\n"
            error_msg += "\n".join(f"  • {error}" for error in errors)
            raise ValueError(error_msg)

    def _validate_single_parameter(self, spec: ParameterSpec, value: Any) -> Optional[str]:
        """
        Validate a single parameter against its specification.
        Returns error message if invalid, None if valid.
        """
        # Type validation
        if spec.parameter_type == ParameterType.INTEGER:
            if not isinstance(value, int) or isinstance(value, bool):
                return f"Parameter '{spec.name}' must be INTEGER, got {type(value).__name__}"
            if spec.min_value is not None and value < spec.min_value:
                return f"Parameter '{spec.name}' value {value} is below minimum {spec.min_value}"
            if spec.max_value is not None and value > spec.max_value:
                return f"Parameter '{spec.name}' value {value} is above maximum {spec.max_value}"

        elif spec.parameter_type == ParameterType.FLOAT:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return f"Parameter '{spec.name}' must be FLOAT, got {type(value).__name__}"
            if spec.min_value is not None and value < spec.min_value:
                return f"Parameter '{spec.name}' value {value} is below minimum {spec.min_value}"
            if spec.max_value is not None and value > spec.max_value:
                return f"Parameter '{spec.name}' value {value} is above maximum {spec.max_value}"

        elif spec.parameter_type == ParameterType.BOOLEAN:
            if not isinstance(value, bool):
                return f"Parameter '{spec.name}' must be BOOLEAN, got {type(value).__name__}"

        elif spec.parameter_type == ParameterType.STRING:
            if not isinstance(value, str):
                return f"Parameter '{spec.name}' must be STRING, got {type(value).__name__}"

        elif spec.parameter_type == ParameterType.CHOICE:
            if spec.choices and value not in spec.choices:
                return f"Parameter '{spec.name}' value '{value}' not in allowed choices: {spec.choices}"

        elif spec.parameter_type == ParameterType.LIST:
            if not isinstance(value, list):
                return f"Parameter '{spec.name}' must be LIST, got {type(value).__name__}"
            # For LIST type, items should be validated (e.g., pattern names for CDL)

        return None  # Valid
    
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
            'layout_type': self.__class__.get_layout_type(),
            'indicator_type': self.__class__.get_indicator_type().value,
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
    
    def get_available_indicators(self, indicator_type: Optional[IndicatorType] = None) -> List[Dict[str, str]]:
        """Get list of available indicators with basic info.

        Args:
            indicator_type: Optional filter by IndicatorType (SIGNAL or TREND).
                           If None, returns all indicators.
        """
        results = []
        for name, cls in self._indicators.items():
            # Filter by type if specified
            if indicator_type is not None and cls.get_indicator_type() != indicator_type:
                continue
            # Create temp instance to access property values (display_name, description)
            try:
                temp_instance = cls()
                results.append({
                    'name': name,
                    'display_name': temp_instance.display_name,
                    'description': temp_instance.description,
                    'indicator_type': cls.get_indicator_type().value
                })
            except Exception:
                # Fallback if instantiation fails
                results.append({
                    'name': name,
                    'display_name': name,
                    'description': '',
                    'indicator_type': cls.get_indicator_type().value
                })
        return results

    def get_signal_indicators(self) -> List[Dict[str, str]]:
        """Get list of SIGNAL type indicators (entry/exit triggers)."""
        return self.get_available_indicators(IndicatorType.SIGNAL)

    def get_trend_indicators(self) -> List[Dict[str, str]]:
        """Get list of TREND type indicators (trend direction/strength)."""
        return self.get_available_indicators(IndicatorType.TREND)
    
    def get_ui_schemas(self, indicator_type: Optional[IndicatorType] = None) -> Dict[str, Dict[str, Any]]:
        """Get UI schemas for registered indicators.

        Args:
            indicator_type: Optional filter by IndicatorType (SIGNAL or TREND).
                           If None, returns all indicators.
        """
        schemas = {}
        for name, cls in self._indicators.items():
            # Filter by type if specified
            if indicator_type is not None and cls.get_indicator_type() != indicator_type:
                continue
            temp_instance = cls()
            schemas[name] = temp_instance.get_ui_schema()
        return schemas

    def get_signal_ui_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get UI schemas for SIGNAL type indicators only."""
        return self.get_ui_schemas(IndicatorType.SIGNAL)

    def get_trend_ui_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get UI schemas for TREND type indicators only."""
        return self.get_ui_schemas(IndicatorType.TREND)
