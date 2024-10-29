from dataclasses import dataclass
import numpy as np
from typing import List, Dict

from optimization.genetic_optimizer.abstractions.fitness_calculator import FitnessCalculator, ObjectiveFunctionBase
from optimization.genetic_optimizer.genetic_algorithm.individual_stats import IndividualStats
from .mlf_individual import MlfIndividual


@dataclass
class MlfFitnessCalculator(FitnessCalculator):

    def __post_init__(self):
        pass

    def add_objective(self, obj: ObjectiveFunctionBase, weight: float = 1.0):
        self.objectives.append(obj)

    def initialize_objectives(self, population: List[MlfIndividual]):
        pass

    # This is the entry point for all simulations to be executed for each of the
    # individual set of rules.  Calculate the state of the system for every time stamp
    # and send the data to the objective functions.  See __calculate_individual_stat
    def calculate_fitness_functions(self, iteration_key: int, population: List[MlfIndividual]) -> List[IndividualStats]:
        fitness_results: List[IndividualStats] = []
        for individual in population:
            # Run through the monitor back test and collect the results
            individual_stats = self.__calculate_individual_stats(individual)
            fitness_results.append(individual_stats)
        return fitness_results

    def calculate_individual(self, individual: MlfIndividual):
        return self.__calculate_individual_stats(individual)

    def __calculate_individual_stats(self, individual: MlfIndividual):
        # Calculate the objectives. r
        fitness_values = np.array([objective.calculate_objective(individual) for objective in self.objectives])
        individual_stats = IndividualStats(index=0,
                                           fitness_values=fitness_values,
                                           individual=individual)
        return individual_stats
