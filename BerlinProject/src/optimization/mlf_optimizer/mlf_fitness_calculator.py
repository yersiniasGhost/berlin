from dataclasses import dataclass
import numpy as np
from typing import List, Optional
import logging

from optimization.genetic_optimizer.abstractions.fitness_calculator import FitnessCalculator, ObjectiveFunctionBase
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
from portfolios.portfolio_tool import Portfolio
from .mlf_individual import MlfIndividual
from optimization.calculators.bt_data_streamer import BacktestDataStreamer

logger = logging.getLogger('MlfFitnessCalculator')


@dataclass
@dataclass
class MlfFitnessCalculator(FitnessCalculator):
    backtest_streamer: [BacktestDataStreamer] = None
    display_results: bool = False
    data_config_file: str = ""

    def __post_init__(self):
        pass

    def add_objective(self, obj: ObjectiveFunctionBase, weight: float = 1.0):
        self.objectives.append(obj)

    def initialize_objectives(self, population: List[MlfIndividual]):
        pass

    def set_final_result(self, display: bool):
        self.display_results = display

    def calculate_fitness_functions(self, iteration_key: int, population: List[MlfIndividual]) -> List[IndividualStats]:
        """
        SIMPLIFIED: Always use shared streamer since data is always the same
        """
        fitness_results: List[IndividualStats] = []

        logger.debug(f"Evaluating population of {len(population)} individuals for iteration {iteration_key}")

        for cnt, individual in enumerate(population):
            try:
                # Always use shared streamer - data loaded once, config swapped per individual
                self.backtest_streamer.replace_monitor_config(individual.monitor_configuration)
                portfolio = self.backtest_streamer.run()

                # Progress logging
                if self.display_results or cnt % 50 == 0:
                    total_trades = portfolio.get_winning_trades_count() + portfolio.get_losing_trades_count()
                    profit_pct = portfolio.get_total_percent_profits()
                    loss_pct = portfolio.get_total_percent_losses()

                    logger.info(f"Individual {cnt + 1}/{len(population)}: "
                                f"{total_trades} trades, "
                                f"profit: {profit_pct:.3f}%, "
                                f"loss: {loss_pct:.3f}%")

                # Calculate fitness
                individual_stats = self.__calculate_individual_stats(individual, portfolio, cnt)
                fitness_results.append(individual_stats)

            except Exception as e:
                logger.error(f"Error evaluating individual {cnt}: {e}")
                # Penalty for failed individuals
                fitness_values = np.array([100.0] * len(self.objectives))
                individual_stats = IndividualStats(index=cnt, fitness_values=fitness_values, individual=individual)
                fitness_results.append(individual_stats)

        logger.info(f"Completed evaluation of {len(population)} individuals")
        return fitness_results

    def __calculate_individual_stats(self, individual: MlfIndividual, portfolio: Portfolio, index: int):
        """Calculate fitness values for an individual"""
        try:
            fitness_values = np.array([
                objective.calculate_objective(individual, portfolio)
                for objective in self.objectives
            ])

            if fitness_values[0] == 100.0:
                fitness_values = np.ones_like(fitness_values) * 100.0

            return IndividualStats(
                index=index,
                fitness_values=fitness_values,
                individual=individual
            )

        except Exception as e:
            logger.error(f"Error calculating individual stats: {e}")
            fitness_values = np.array([100.0] * len(self.objectives))
            return IndividualStats(index=index, fitness_values=fitness_values, individual=individual)