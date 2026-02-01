"""
Objective wrapper class for GA configuration.

Provides JSON deserialization and objective instantiation using ObjectiveRegistry.
"""

from dataclasses import dataclass
from typing import Dict, Any
from optimization.genetic_optimizer.support.types import Json
from optimization.genetic_optimizer.abstractions.objective_registry import ObjectiveRegistry


@dataclass
class Objective:
    """Wrapper for objective configuration from JSON.

    Attributes:
        name: The class name of the objective (e.g., 'MaximizeProfit')
        weight: Weight for this objective in multi-objective optimization
        parameters: Dictionary of parameter values for the objective
    """
    name: str
    weight: float
    parameters: Dict[str, Any]

    @staticmethod
    def from_json(json: Json) -> 'Objective':
        """Create Objective from JSON configuration.

        Args:
            json: Dict with keys 'objective', 'weight', and optionally 'parameters'

        Returns:
            Configured Objective instance
        """
        return Objective(
            name=json['objective'],
            weight=json['weight'],
            parameters=json.get('parameters', {})
        )

    def create_objective(self):
        """Create the actual objective function instance.

        Uses ObjectiveRegistry to dynamically instantiate the objective class.
        Parameters from the configuration are passed to the constructor.

        Returns:
            Configured ObjectiveFunctionBase instance

        Raises:
            ValueError: If objective name is not found in registry
        """
        registry = ObjectiveRegistry()
        return registry.create_objective(
            name=self.name,
            weight=self.weight,
            parameters=self.parameters
        )

