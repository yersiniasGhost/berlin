from dataclasses import dataclass
import numpy as np
from typing import List, Optional, Dict, Any
import logging
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
import pickle
import os
import platform

from optimization.genetic_optimizer.abstractions.fitness_calculator import FitnessCalculator, ObjectiveFunctionBase
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
from portfolios.portfolio_tool import Portfolio
from .mlf_individual import MlfIndividual
from optimization.calculators.bt_data_streamer import BacktestDataStreamer

logger = logging.getLogger('MlfFitnessCalculator')


def evaluate_individual_worker(args):
    """
    Worker function that runs in separate process.
    This function must be pickleable (defined at module level).
    """
    individual, source_streamer_data, objectives_data, worker_id = args

    try:
        # Create a new BacktestDataStreamer for this worker
        backtest_streamer = BacktestDataStreamer()
        # Copy precomputed data from the source streamer
        backtest_streamer.copy_data_from(source_streamer_data)

        # Set the monitor configuration and run backtest
        backtest_streamer.replace_monitor_config(individual.monitor_configuration)
        portfolio = backtest_streamer.run()

        # Calculate fitness values using the objectives
        fitness_values = np.array([
            obj.calculate_objective(individual, portfolio)
            for obj in objectives_data
        ])

        # Apply penalty if first objective indicates failure
        if fitness_values[0] == 100.0:
            fitness_values = np.ones_like(fitness_values) * 100.0

        # Return success result
        return {
            'success': True,
            'fitness_values': fitness_values,
            'individual': individual,
            'portfolio_stats': {
                'winning_trades': portfolio.get_winning_trades_count(),
                'losing_trades': portfolio.get_losing_trades_count(),
                'profit_pct': portfolio.get_total_percent_profits(),
                'loss_pct': portfolio.get_total_percent_losses()
            }
        }

    except Exception as e:
        # Return error result
        print(f"{worker_id}: exception {e}")
        return {
            'success': False,
            'error': str(e),
            'individual': individual,
            'fitness_values': None
        }


@dataclass
class MlfFitnessCalculator(FitnessCalculator):
    backtest_streamer: BacktestDataStreamer = None
    display_results: bool = False
    data_config_file: str = ""
    max_workers: Optional[int] = None
    _executor: Optional[ProcessPoolExecutor] = None
    force_sequential: bool = False


    def __post_init__(self):
        # Set default number of workers to CPU count
        if self.max_workers is None:
            self.max_workers = mp.cpu_count()

        logger.info(f"Initialized parallel fitness calculator with {self.max_workers} workers")



    def add_objective(self, obj: ObjectiveFunctionBase, weight: float = 1.0):
        self.objectives.append(obj)



    def initialize_objectives(self, population: List[MlfIndividual]):
        pass



    def set_final_result(self, display: bool):
        self.display_results = display



    def _get_executor(self):
        """Get or create the process pool executor"""
        if self._executor is None:
            self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
            logger.info(f"Created process pool with {self.max_workers} workers")
        return self._executor



    def shutdown_executor(self):
        """Shutdown the executor when done with all generations"""
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None
            logger.info("Process pool executor shutdown complete")



    def calculate_fitness_functions(self, iteration_key: int, population: List[MlfIndividual]) -> List[IndividualStats]:
        """
        Parallel evaluation of population fitness using ProcessPoolExecutor
        """
        if self.force_sequential:
            return self._calculate_fitness_sequential(iteration_key, population)

        fitness_results: List[IndividualStats] = []

        logger.info(
            f"Evaluating population of {len(population)} individuals for iteration {iteration_key} using {self.max_workers} workers")

        try:
            # Prepare data for workers (serialize once)
            source_streamer_data = self.backtest_streamer  # Pass entire streamer for copying
            objectives_data = self.objectives

            # Create arguments for each worker
            worker_args = [
                (individual, source_streamer_data, objectives_data, i % self.max_workers)
                for i, individual in enumerate(population)
            ]

            # Get executor and submit all jobs
            executor = self._get_executor()

            # Submit all jobs and collect results
            logger.debug(f"Submitting {len(worker_args)} jobs to process pool")
            print(f"DEBUG: About to call executor.map with {len(worker_args)} jobs")
            print(f"DEBUG: Executor type: {type(executor)}")
            print(f"DEBUG: Max workers: {self.max_workers}")

            try:
                future_results = list(executor.map(evaluate_individual_worker, worker_args))
                print(f"DEBUG: executor.map completed successfully, got {len(future_results)} results")
            except Exception as map_error:
                print(f"DEBUG: executor.map failed with error: {map_error}")
                raise map_error

            # Process results
            for cnt, result in enumerate(future_results):

                try:
                    if result['success']:
                        # Successful evaluation
                        individual_stats = IndividualStats(
                            index=cnt,
                            fitness_values=result['fitness_values'],
                            individual=result['individual']
                        )
                        # Progress logging
                        if self.display_results or cnt % 50 == 0:
                            stats = result['portfolio_stats']
                            total_trades = stats['winning_trades'] + stats['losing_trades']
                            logger.info(f"Individual {cnt + 1}/{len(population)}: "
                                        f"{total_trades} trades, "
                                        f"profit: {stats['profit_pct']:.3f}%, "
                                        f"loss: {stats['loss_pct']:.3f}%")
                    else:
                        # Failed evaluation - apply penalty
                        logger.error(f"Error evaluating individual {cnt}: {result['error']}")
                        fitness_values = np.array([100.0] * len(self.objectives))
                        individual_stats = IndividualStats(
                            index=cnt,
                            fitness_values=fitness_values,
                            individual=result['individual']
                        )

                    fitness_results.append(individual_stats)

                except Exception as e:
                    logger.error(f"Error processing result for individual {cnt}: {e}")
                    # Create penalty result
                    fitness_values = np.array([100.0] * len(self.objectives))
                    individual_stats = IndividualStats(
                        index=cnt,
                        fitness_values=fitness_values,
                        individual=population[cnt]
                    )
                    fitness_results.append(individual_stats)

        except Exception as e:
            logger.error(f"Critical error in parallel fitness calculation: {e}")
            # Fallback to sequential processing
            logger.warning("Falling back to sequential processing")
            return self._calculate_fitness_sequential(iteration_key, population)

        logger.info(f"Completed parallel evaluation of {len(population)} individuals")
        return fitness_results



    def _calculate_fitness_sequential(self, iteration_key: int, population: List[MlfIndividual]) -> List[
        IndividualStats]:
        """
        Fallback sequential implementation (your original code)
        """
        fitness_results: List[IndividualStats] = []

        logger.debug(
            f"Sequential evaluation of population of {len(population)} individuals for iteration {iteration_key}")

        for cnt, individual in enumerate(population):
            try:
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
                fitness_values = np.array([100.0] * len(self.objectives))
                individual_stats = IndividualStats(index=cnt, fitness_values=fitness_values, individual=individual)
                fitness_results.append(individual_stats)

        return fitness_results



    def __calculate_individual_stats(self, individual: MlfIndividual, portfolio: Portfolio, index: int):
        """Calculate fitness values for an individual (used in sequential fallback)"""
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



    def __del__(self):
        """Cleanup executor when object is destroyed"""
        self.shutdown_executor()