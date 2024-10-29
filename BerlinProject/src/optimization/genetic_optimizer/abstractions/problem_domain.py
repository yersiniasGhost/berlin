import numpy as np
from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass

from optimization.genetic_optimizer.abstractions.individual_base import IndividualBase
from optimization.genetic_optimizer.abstractions.fitness_calculator import FitnessCalculator
from optimization.genetic_optimizer.genetic_algorithm.individual_stats import IndividualStats


@dataclass
class ProblemDomain(ABC):
    fitness_calculator: FitnessCalculator

    @abstractmethod
    def create_initial_population(self, population_size: int) -> List[IndividualBase]:
        raise NotImplementedError

    @abstractmethod
    def post_iteration_cleanup(self, iteration: str):
        raise NotImplementedError

    @abstractmethod
    def cross_over_function(self, mom, dad, chance):
        raise NotImplementedError

    @abstractmethod
    def optimizer_results(self, best_individual: IndividualBase, metrics: List[float]):
        raise NotImplementedError

    def calculate_fitness_functions(self, iteration: int, population: List[IndividualBase]) -> List[IndividualStats]:
        return self.fitness_calculator.calculate_fitness_functions(iteration, population)

    def get_sorted_fitness_stats(self, stats: List[float]) -> np.array:
        return self.fitness_calculator.get_sorted_fitness_stats(stats)

    def get_sorted_individual_stats(self, stats: List[IndividualStats]) -> List[IndividualStats]:
        return self.fitness_calculator.get_sorted_individual_stats(stats)

    @abstractmethod
    def elitist_offspring(self, elitist: IndividualBase) -> IndividualBase:
        raise NotImplementedError

    @abstractmethod
    def mutation_function(self, individual: IndividualBase, mutate_probability: float, iteration: int) -> IndividualBase:
        raise NotImplementedError
