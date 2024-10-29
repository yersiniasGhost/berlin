from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ObjectiveFunctionBase(ABC):
    normalization_factor: float = 1.0
    weight: float = 1.0
    name: str = "Unnamed"

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

