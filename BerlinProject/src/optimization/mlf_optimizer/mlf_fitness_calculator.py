from dataclasses import dataclass
import numpy as np
from typing import List, Optional

from optimization.genetic_optimizer.abstractions.fitness_calculator import FitnessCalculator, ObjectiveFunctionBase
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
from .mlf_individual import MlfIndividual
from data_streamer import DataStreamer
from operations.monitor_backtest_results import MonitorResultsBacktest


@dataclass
class MlfFitnessCalculator(FitnessCalculator):
    data_streamer: Optional[DataStreamer] = None

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
        cnt = 0
        for individual in population:
            # Run through the monitor back test and collect the results
            bt = MonitorResultsBacktest("Optimizer", individual.monitor)
            self.data_streamer.replace_monitor_configuration(individual.monitor_configuration)
            self.data_streamer.replace_external_tools(bt)
            self.data_streamer.run()
            print(cnt, "fitness: ", bt.results)
            cnt += 1
            individual_stats = self.__calculate_individual_stats(individual, bt)
            fitness_results.append(individual_stats)
        return fitness_results

    def calculate_individual(self, individual: MlfIndividual):
        return self.__calculate_individual_stats(individual)

    def __calculate_individual_stats(self, individual: MlfIndividual, bt: MonitorResultsBacktest):
        # Calculate the objectives.
        fitness_values = np.array([objective.calculate_objective(individual, bt) for objective in self.objectives])
        individual_stats = IndividualStats(index=0,
                                           fitness_values=fitness_values,
                                           individual=individual)
        return individual_stats
