import random
from dataclasses import dataclass
from typing import List, Dict

from optimization.genetic_optimizer.abstractions.problem_domain import ProblemDomain, IndividualBase
from .mlf_individual import MlfIndividual
from models.monitor_configuration import MonitorConfiguration
from models.monitor_model import Monitor


@dataclass
class MlfProblem(ProblemDomain):
    monitor_configuration: MonitorConfiguration
    monitor: Monitor

    def optimizer_results(self, best_individual: IndividualBase, metrics: List[float]):
        pass


    def create_initial_population(self, population_size: int) -> List[MlfIndividual]:
        individuals = []
        for i in range(population_size):
            individuals.append(MlfIndividual.create_itself(self.monitor, self.monitor_configuration))
        return individuals

    def post_iteration_cleanup(self, iteration: str):
        pass

    def elitist_offspring(self, elite: MlfIndividual) -> MlfIndividual:
        ...

    def check_population(self, population: List[MlfIndividual]) -> bool:
        ...


    def cross_over_function(self, mom: MlfIndividual, dad: MlfIndividual, chance: float) -> List[MlfIndividual]:
        swap_cnt = 0
        for key in mom.monitor.triggers:
            if random.random() < chance:
                swap_cnt += 1
                mom.monitor.triggers[key], dad.monitor.triggers[key] = dad.monitor.triggers[key], mom.monitor.triggers[key]

        for idx, indicator in enumerate(mom.monitor_configuration.indicators):
            for key in indicator.parameters:
                if random.random() < chance:
                    swap_cnt += 1
                    dad_indicator = dad.monitor_configuration.indicators[idx]
                    indicator.parameters[key], dad_indicator.parameters[key] = dad_indicator.parameters[key], indicator.parameters[key]

        return [mom, dad]


    def mutation_function(self, individual: MlfIndividual, mutate_probability: float, iteration: int):
        for indicator in individual.monitor_configuration.indicators:
            for name, range in indicator.ranges.items():
                if range['t'] != 'skip':
                    if random.random() < mutate_probability:
                        low, high = range['r']
                        delta = 0.2 * (high - low)
                        value = indicator.parameters[name]
                        new_value = 0
                        if range['t'] == "int":
                            delta = int(delta)
                            new_value = value + random.randint(-delta, delta)
                        elif range['t'] == 'float':
                            new_value = value + random.uniform(-delta, delta)
                        new_value = max(low, min(new_value, high))
                        indicator.parameters[name] = new_value

