from dataclasses import dataclass, field
import numpy as np
from typing import List, Dict

from optimization.genetic_optimizer.abstractions.individual_base import IndividualBase


@dataclass
class IndividualStats:
    index: int
    fitness_values: np.array
    individual: IndividualBase
    dominated_by_count: int = 0
    dominates_over: List["IndividualStats"] = field(repr=False, default_factory=list)
    crowding_distance: float = 0
    weighted_sum: float = 0
    additional_data: Dict = field(repr=False, default_factory=dict)

    def dominated_by_solution(self):
        """Increment the count of how many times this individual is dominated."""
        self.dominated_by_count += 1

    def reduce_dominated_by_count(self):
        """Decrement the count of dominations, ensuring it does not go below zero."""
        self.dominated_by_count -= 1
        # max(0, self.dominated_by_count - 1)


    def dominates(self, other: "IndividualStats"):
        """Record that this individual dominates another."""
        self.dominates_over.append(other)

    def calculate_sum(self, weights: List[float]) -> float:
        """Calculate the weighted sum of fitness values."""
        self.weighted_sum = np.sum(np.array(self.fitness_values) * np.array(weights))
        return self.weighted_sum

    # def __repr__(self):
    #     return json.dumps(self.__dict__)
