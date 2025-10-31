from dataclasses import dataclass
import numpy as np
from typing import List, Optional, Dict, Any
import logging
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
import random

from optimization.genetic_optimizer.abstractions.fitness_calculator import FitnessCalculator, ObjectiveFunctionBase
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
from portfolios.portfolio_tool import Portfolio
from .mlf_individual import MlfIndividual
from optimization.calculators.bt_data_streamer import BacktestDataStreamer

from mlf_utils.log_manager import LogManager


def evaluate_individual_worker(args):
    """
    Worker function that runs in separate process.
    This function must be pickleable (defined at module level).
    """
    individual, source_streamer_data, objectives_data, worker_id = args
    maximum_drawdown = source_streamer_data.get_maximum_drawdown()
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
            obj.calculate_objective(individual, portfolio, backtest_streamer)
            for obj in objectives_data
        ])

        # Apply penalty if first objective indicates failure
        # if fitness_values[0] == 100.0:
        #     fitness_values = np.ones_like(fitness_values) * 100.0
        success = not all(fv == 100 for fv in fitness_values)

        # Return success result
        return {
            'success': success,
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
        print(f"HERE {worker_id}: exception {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e),
            'individual': individual,
            'fitness_values': None
        }


@dataclass
class MlfFitnessCalculator(FitnessCalculator):
    backtest_streamers: List[BacktestDataStreamer] = None
    display_results: bool = False
    max_workers: Optional[int] = None
    _executor: Optional[ProcessPoolExecutor] = None
    force_sequential: bool = True
    selected_streamer: Optional[BacktestDataStreamer] = None
    split = None
    repeat_split: int = 0

    def __post_init__(self):
        # Set default number of workers to CPU count
        self.logger = LogManager().get_logger("MLF Fitness")
        if self.max_workers is None:
            self.max_workers = mp.cpu_count()

        self.logger.info(f"Initialized parallel fitness calculator with {self.max_workers} workers")
        self.logger.info(f"Got {len(self.backtest_streamers)} data split streamers")

    def _select_random_streamer(self) -> BacktestDataStreamer:
        """Randomly select one of the available data streamers"""
        self.repeat_split += 1
        if self.repeat_split >= 3 or not self.split:
            self.split = random.choice(self.backtest_streamers)
            self.repeat_split = 0
        return self.split



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
            self.logger.info(f"Created process pool with {self.max_workers} workers")
        return self._executor



    def shutdown_executor(self):
        """Shutdown the executor when done with all generations"""
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None
            self.logger.info("Process pool executor shutdown complete")



    def calculate_fitness_functions(self, iteration_key: int, population: List[MlfIndividual]) -> List[IndividualStats]:
        """
        Parallel evaluation of population fitness using ProcessPoolExecutor
        """
        if self.force_sequential:
            return self._calculate_fitness_sequential(iteration_key, population)

        fitness_results: List[IndividualStats] = []

        self.logger.info(
            f"Evaluating population of {len(population)} individuals for iteration {iteration_key} using {self.max_workers} workers")

        try:
            # Prepare data for workers (serialize once)
            self.selected_streamer = self._select_random_streamer()
            source_streamer_data = self.selected_streamer  # Pass selected streamer for copying
            self.logger.info(f"🔄 Using: {self.selected_streamer.ticker} {self.selected_streamer.start_date} to {self.selected_streamer.end_date}")
            objectives_data = self.objectives
            for obj in self.objectives:
                obj.preprocess(source_streamer_data.tick_history)

            # Create arguments for each worker
            worker_args = [
                (individual, source_streamer_data, objectives_data, i % self.max_workers)
                for i, individual in enumerate(population)
            ]

            # Get executor and submit all jobs
            executor = self._get_executor()

            # Submit all jobs and collect results
            self.logger.debug(f"Submitting {len(worker_args)} jobs to process pool")
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
                            self.logger.info(f"Individual {cnt + 1}/{len(population)}: "
                                        f"{total_trades} trades, "
                                        f"profit: {stats['profit_pct']:.3f}%, "
                                        f"loss: {stats['loss_pct']:.3f}%")
                    else:
                        # Failed evaluation - apply penalty
                        self.logger.error(f"Error evaluating individual {cnt}: {result['error']}")
                        continue  # do not add to the fitness results
                        # fitness_values = np.array([100.0] * len(self.objectives))
                        # individual_stats = IndividualStats(
                        #     index=cnt,
                        #     fitness_values=fitness_values,
                        #     individual=result['individual']
                        # )

                    fitness_results.append(individual_stats)

                except Exception as e:
                    self.logger.error(f"Error processing result for individual {cnt}: {e}")
                    # Create penalty result
                    fitness_values = np.array([100.0] * len(self.objectives))
                    individual_stats = IndividualStats(
                        index=cnt,
                        fitness_values=fitness_values,
                        individual=population[cnt]
                    )
                    fitness_results.append(individual_stats)

        except Exception as e:
            self.logger.error(f"Critical error in parallel fitness calculation: {e}")
            # Fallback to sequential processing
            self.logger.warning("Falling back to sequential processing")
            return self._calculate_fitness_sequential(iteration_key, population)

        self.logger.info(f"Completed evaluation of {len(population)} individuals, got {len(fitness_results)} valid")
        return fitness_results



    def _calculate_fitness_sequential(self, iteration_key: int, population: List[MlfIndividual]) -> List[IndividualStats]:
        """
        Fallback sequential implementation (your original code)
        """
        fitness_results: List[IndividualStats] = []

        self.logger.debug(f"Sequential calculation of {len(population)} individuals for iteration {iteration_key}")
        self.selected_streamer = self._select_random_streamer()

        for cnt, individual in enumerate(population):
            try:
                self.selected_streamer.replace_monitor_config(individual.monitor_configuration)
                portfolio = self.selected_streamer.run()

                # Progress logging
                if self.display_results or cnt % 50 == 0:
                    total_trades = portfolio.get_winning_trades_count() + portfolio.get_losing_trades_count()
                    profit_pct = portfolio.get_total_percent_profits()
                    loss_pct = portfolio.get_total_percent_losses()

                    self.logger.info(f"Individual {cnt + 1}/{len(population)}: "
                                f"{total_trades} trades, "
                                f"profit: {profit_pct:.3f}%, "
                                f"loss: {loss_pct:.3f}%")

                # Calculate fitness
                individual_stats = self.__calculate_individual_stats(individual, portfolio, cnt, self.selected_streamer)
                fitness_results.append(individual_stats)

            except Exception as e:
                self.logger.error(f"Error evaluating individual {cnt}: {e}")
                fitness_values = np.array([99.0] * len(self.objectives))
                individual_stats = IndividualStats(index=cnt, fitness_values=fitness_values, individual=individual)
                fitness_results.append(individual_stats)

        return fitness_results



    def __calculate_individual_stats(self, individual: MlfIndividual, portfolio: Portfolio, index: int, bt: BacktestDataStreamer):
        """Calculate fitness values for an individual (used in sequential fallback)"""
        try:
            fitness_values = np.array([
                objective.calculate_objective(individual, portfolio, bt)
                for objective in self.objectives
            ])

            # if fitness_values[0] == 100.0:
            #     fitness_values = np.ones_like(fitness_values) * 100.0

            return IndividualStats(
                index=index,
                fitness_values=fitness_values,
                individual=individual
            )

        except Exception as e:
            self.logger.error(f"Error calculating individual stats: {e}")
            fitness_values = np.array([100.0] * len(self.objectives))
            return IndividualStats(index=index, fitness_values=fitness_values, individual=individual)



    def __del__(self):
        """Cleanup executor when object is destroyed"""
        self.shutdown_executor()