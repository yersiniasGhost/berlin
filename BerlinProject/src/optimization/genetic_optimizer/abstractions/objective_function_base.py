from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from enum import Enum


class ObjectiveParameterType(Enum):
    """Parameter types for objective function configuration."""
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"
    CHOICE = "choice"


@dataclass
class ObjectiveParameterSpec:
    """Specification for an objective function parameter with UI metadata.

    Mirrors ParameterSpec from indicator_base.py for consistency.
    """
    name: str
    display_name: str
    parameter_type: ObjectiveParameterType
    default_value: Any
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    step: Optional[Union[int, float]] = None
    choices: Optional[List[str]] = None
    description: str = ""
    ui_group: str = "General"

    def validate(self, value: Any) -> bool:
        """Validate a parameter value against this specification."""
        if self.parameter_type == ObjectiveParameterType.INTEGER:
            if not isinstance(value, int) or isinstance(value, bool):
                return False
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False
        elif self.parameter_type == ObjectiveParameterType.FLOAT:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False
        elif self.parameter_type == ObjectiveParameterType.BOOLEAN:
            if not isinstance(value, bool):
                return False
        elif self.parameter_type == ObjectiveParameterType.STRING:
            if not isinstance(value, str):
                return False
        elif self.parameter_type == ObjectiveParameterType.CHOICE:
            if self.choices and value not in self.choices:
                return False
        return True


@dataclass
class ObjectiveFunctionBase(ABC):
    """Base class for all objective functions with parameter management."""
    normalization_factor: float = 1.0
    weight: float = 1.0
    name: str = "Unnamed"
    display_name: str = "Unnamed Objective"
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Apply default parameter values for any missing parameters."""
        specs = self.get_parameter_specs()
        for spec in specs:
            if spec.name not in self.parameters:
                self.parameters[spec.name] = spec.default_value

    @abstractmethod
    def calculate_objective(self, *args) -> float:
        raise NotImplementedError

    @staticmethod
    def get_metric(metric: float) -> float:
        return metric

    def post_initialize(self, *args):
        return

    def set_normalization(self, norm: float):
        self.normalization_factor = norm

    @classmethod
    def get_parameter_specs(cls) -> List[ObjectiveParameterSpec]:
        """Return list of parameter specifications for this objective.

        Override in subclasses to define configurable parameters.
        Returns empty list if objective has no configurable parameters.
        """
        return []

    @classmethod
    def get_parameters(cls) -> Dict:
        """Legacy method - returns default parameter values from specs."""
        specs = cls.get_parameter_specs()
        return {spec.name: spec.default_value for spec in specs}

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """Get parameter value by name with optional default."""
        return self.parameters.get(name, default)

    def get_ui_schema(self) -> Dict[str, Any]:
        """Generate UI schema for form generation.

        Mirrors BaseIndicator.get_ui_schema() for frontend consistency.
        """
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
            'objective_name': self.__class__.__name__,
            'display_name': self.display_name,
            'description': self.description,
            'has_parameters': len(specs) > 0,
            'parameter_groups': groups
        }

    def preprocess(self, *args):
        return
