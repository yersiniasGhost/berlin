"""
ObjectiveRegistry: Singleton registry for managing available objective functions.

Mirrors IndicatorRegistry pattern for consistency across the codebase.
Provides discovery, UI schema generation, and objective instantiation.
"""

from typing import Dict, Type, List, Any, Optional
from mlf_utils.singleton import Singleton
from .objective_function_base import ObjectiveFunctionBase


class ObjectiveRegistry(metaclass=Singleton):
    """Registry for managing available objective functions.

    Provides:
    - Registration and lookup of objective classes
    - UI schema generation for frontend forms
    - Metadata for objective selection dropdowns
    """

    def __init__(self):
        self._objectives: Dict[str, Type[ObjectiveFunctionBase]] = {}
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization - register all objectives on first use."""
        if not self._initialized:
            self._register_all_objectives()
            self._initialized = True

    def _register_all_objectives(self):
        """Register all available objective functions."""
        # Import here to avoid circular imports
        from optimization.mlf_optimizer.mlf_objectives import OBJECTIVE_CLASSES
        for name, cls in OBJECTIVE_CLASSES.items():
            self._objectives[name] = cls

    def register(self, objective_class: Type[ObjectiveFunctionBase]):
        """Register an objective class manually."""
        self._objectives[objective_class.__name__] = objective_class

    def get_objective_class(self, name: str) -> Type[ObjectiveFunctionBase]:
        """Get objective class by name.

        Args:
            name: The class name of the objective (e.g., 'MaximizeProfit')

        Returns:
            The objective class

        Raises:
            ValueError: If objective name is not found
        """
        self._ensure_initialized()
        if name not in self._objectives:
            raise ValueError(f"Unknown objective: {name}. Available: {list(self._objectives.keys())}")
        return self._objectives[name]

    def create_objective(self, name: str, weight: float = 1.0,
                         parameters: Optional[Dict[str, Any]] = None) -> ObjectiveFunctionBase:
        """Create an objective instance from name and parameters.

        Args:
            name: The class name of the objective
            weight: Weight for this objective in multi-objective optimization
            parameters: Optional dict of parameter values

        Returns:
            Configured objective instance
        """
        objective_class = self.get_objective_class(name)
        return objective_class(weight=weight, parameters=parameters or {})

    def get_available_objectives(self) -> List[Dict[str, Any]]:
        """Get list of available objectives with metadata for UI dropdowns.

        Returns:
            List of dicts with keys: name, display_name, description, has_parameters
        """
        self._ensure_initialized()
        results = []

        for name, cls in self._objectives.items():
            try:
                # Create temp instance to access display_name and description
                temp_instance = cls()
                specs = cls.get_parameter_specs()

                results.append({
                    'name': name,
                    'display_name': temp_instance.display_name,
                    'description': temp_instance.description,
                    'has_parameters': len(specs) > 0
                })
            except Exception as e:
                # Fallback if instantiation fails
                results.append({
                    'name': name,
                    'display_name': name,
                    'description': '',
                    'has_parameters': False
                })

        # Sort alphabetically by display name
        results.sort(key=lambda x: x['display_name'])
        return results

    def get_ui_schema(self, name: str) -> Dict[str, Any]:
        """Get UI schema for a specific objective.

        Args:
            name: The class name of the objective

        Returns:
            UI schema dict with parameter groups for form generation
        """
        objective_class = self.get_objective_class(name)
        temp_instance = objective_class()
        return temp_instance.get_ui_schema()

    def get_ui_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get UI schemas for all registered objectives.

        Returns:
            Dict mapping objective name to UI schema
        """
        self._ensure_initialized()
        schemas = {}

        for name, cls in self._objectives.items():
            try:
                temp_instance = cls()
                schemas[name] = temp_instance.get_ui_schema()
            except Exception:
                # Skip objectives that fail to instantiate
                pass

        return schemas

    def get_objectives_with_parameters(self) -> List[str]:
        """Get list of objective names that have configurable parameters.

        Returns:
            List of objective class names that have parameters
        """
        self._ensure_initialized()
        return [
            name for name, cls in self._objectives.items()
            if len(cls.get_parameter_specs()) > 0
        ]

    def list_objectives(self) -> List[str]:
        """Get list of all registered objective names.

        Returns:
            List of objective class names
        """
        self._ensure_initialized()
        return list(self._objectives.keys())
