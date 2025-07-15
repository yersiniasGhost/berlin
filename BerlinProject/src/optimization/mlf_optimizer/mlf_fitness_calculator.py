from dataclasses import dataclass
import numpy as np
from typing import List, Optional, Dict

from optimization.genetic_optimizer.abstractions.fitness_calculator import FitnessCalculator, ObjectiveFunctionBase
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
from portfolios.portfolio_tool import Portfolio
from .mlf_individual import MlfIndividual
from data_streamer import DataStreamer
from operations.monitor_backtest_results import MonitorResultsBacktest
from optimization.calculators.bt_data_streamer import BacktestDataStreamer


@dataclass
class MlfFitnessCalculator(FitnessCalculator):
    backtest_streamer: Optional[BacktestDataStreamer] = None
    display_results: bool = False

    def __post_init__(self):
        pass

    def add_objective(self, obj: ObjectiveFunctionBase, weight: float = 1.0):
        self.objectives.append(obj)

    def initialize_objectives(self, population: List[MlfIndividual]):
        pass

    def set_final_result(self, display: bool):
        self.display_results = display

    # This is the entry point for all simulations to be executed for each of the
    # individual set of rules.  Calculate the state of the system for every time stamp
    # and send the data to the objective functions.  See __calculate_individual_stat
    # def calculate_fitness_functions_old(self, iteration_key: int, population: List[MlfIndividual]) -> List[IndividualStats]:
    #     fitness_results: List[IndividualStats] = []
    #     cnt = 0
    #     for individual in population:
    #         # Run through the monitor back test and collect the results
    #         bt = MonitorResultsBacktest("Optimizer", individual.monitor)
    #         self.data_streamer.replace_monitor_configuration(individual.monitor_configuration)
    #         # self.data_streamer.replace_external_tools(bt)
    #         self.data_streamer.run()
    #         if self.display_results:
    #             print("Final Result?")
    #             print(cnt, "fitness: ", bt.results, f"profit: %{(bt.get_total_percent_profits() * 100.0):.3f}", f"loss: %{(bt.get_total_percent_losses()*100.0):.3f}" )
    #             print("Bull triggers:", individual.monitor.triggers)
    #             print("Bear triggers:", individual.monitor.bear_triggers)
    #             print("Thresholds", individual.monitor.threshold, individual.monitor.bear_threshold)
    #             for indicator in individual.monitor_configuration.indicators:
    #                 print(indicator.name, indicator.parameters)
    #             print("-----------")
    #         cnt += 1
    #         individual_stats = self.__calculate_individual_stats(individual, bt, cnt)
    #         fitness_results.append(individual_stats)
    #     return fitness_results

    def calculate_fitness_functions(self, iteration_key: int, population: List[MlfIndividual]) -> List[IndividualStats]:
        fitness_results: List[IndividualStats] = []
        cnt = 0
        for individual in population:

            # Replace monitor config
            self.backtest_streamer.replace_monitor_config(individual.monitor_configuration)

            # Run backtest - returns Portfolio object
            portfolio = self.backtest_streamer.run()

            if self.display_results:
                print("Final Result?")
                print(cnt, "trades:", portfolio.get_winning_trades_count() + portfolio.get_losing_trades_count(),
                      f"profit: %{portfolio.get_total_percent_profits():.3f}",
                      f"loss: %{portfolio.get_total_percent_losses():.3f}")
                print("-----------")
            cnt += 1

            # Pass Portfolio object (not dictionary)
            individual_stats = self.__calculate_individual_stats(individual, portfolio, cnt)
            fitness_results.append(individual_stats)
        return fitness_results

    def __calculate_individual_stats(self, individual: MlfIndividual, portfolio: Portfolio, index: int):
        # portfolio is now consistently a Portfolio object
        fitness_values = np.array(
            [objective.calculate_objective(individual, portfolio) for objective in self.objectives])

        if fitness_values[0] == 100.0:
            fitness_values = np.ones_like(fitness_values) * 100.0

        individual_stats = IndividualStats(index=index,
                                           fitness_values=fitness_values,
                                           individual=individual)
        return individual_stats

    # def calculate_individual(self, individual: MlfIndividual):
    #     return self.__calculate_individual_stats(individual, 0)

    # def __calculate_individual_stats_old(self, individual: MlfIndividual, bt: MonitorResultsBacktest, index: int):
    #     # Calculate the objectives.
    #     fitness_values = np.array([objective.calculate_objective(individual, bt) for objective in self.objectives])
    #     if fitness_values[0] == 100.0:
    #         fitness_values = np.ones_like(fitness_values) * 100.0
    #     individual_stats = IndividualStats(index=index,
    #                                        fitness_values=fitness_values,
    #                                        individual=individual)
    #     return individual_stats
