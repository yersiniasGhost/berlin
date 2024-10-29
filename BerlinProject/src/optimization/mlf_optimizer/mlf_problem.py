import numpy as np
from dataclasses import dataclass
from typing import List, Dict

from optimization.genetic_optimizer.abstractions.problem_domain import ProblemDomain, IndividualBase
from .mlf_individual import MlfIndividual
from models import MonitorConfiguration


@dataclass
class MlfProblem(ProblemDomain):
    monitor: MonitorConfiguration

    def optimizer_results(self, best_individual: IndividualBase, metrics: List[float]):
        pass


    def create_initial_population(self, population_size: int) -> List[MlfIndividual]:
        individuals = []
        for i in range(population_size):
            individuals.append(MlfIndividual.create_itself(self.monitor))
        return individuals

    def post_iteration_cleanup(self, iteration: str):
        pass

    def elitist_offspring(self, elite: MlfIndividual) -> MlfIndividual:
        ...

    def check_population(self, population: List[MlfIndividual]) -> bool:
        ...


    def cross_over_function(self, mom: MlfIndividual, dad: MlfIndividual, chance: float) -> List[MlfIndividual]:
        pass


    def mutation_function(self, individual: MlfIndividual, mutate_probability: float, iteration: int):
        return individual.mutate_function(mutate_probability)