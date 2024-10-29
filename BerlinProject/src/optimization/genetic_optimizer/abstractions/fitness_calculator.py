from abc import ABC, abstractmethod
from typing import List
import numpy as np
from dataclasses import dataclass, field
from optimization.genetic_optimizer.abstractions.individual_base import IndividualBase
from optimization.genetic_optimizer.genetic_algorithm.individual_stats import IndividualStats
from optimization.genetic_optimizer.abstractions.objective_function_base import ObjectiveFunctionBase


@dataclass
class FitnessCalculator(ABC):
    objectives: List[ObjectiveFunctionBase] = field(default_factory=list)


    def add_objective(self, obj: ObjectiveFunctionBase, weight: float = 1.0):
        self.objectives.append(obj)

    def get_objective_weights(self):
        return [o.weight for o in self.objectives]

    def get_number_of_objectives(self):
        return len(self.objectives)

    def print_objectives(self):
        for o in self.objectives:
            print(str(o))

    @abstractmethod
    def calculate_fitness_functions(self, iteration_key: int,
                                    population: List[IndividualBase]) -> List[IndividualStats]:
        raise NotImplementedError

    def collect_metrics(self, i_stats: IndividualStats) -> List[float]:
        result = []
        for idx, metric in enumerate(i_stats.fitness_values):
            result.append(self.objectives[idx].get_metric(metric))
        return result

    def transform_metrics(self, metrics: List[float]) -> List[float]:
        return [self.objectives[idx].get_metric(metric) for idx, metric in enumerate(metrics)]

    def get_sorted_fitness_stats(self, stats: List[List[float]]) -> np.array:
        weights = self.get_objective_weights()
        stats_by_ind = np.array(stats)
        stats_by_ind = stats_by_ind * weights
        return stats_by_ind

    def get_sorted_individual_stats(self, stats: List[IndividualStats]) -> List[IndividualStats]:
        weights = self.get_objective_weights()
        for stat in stats:
            stat.calculate_sum(weights)
        sorted_stats = sorted(stats, key=lambda s: s.weighted_sum)
        return sorted_stats
