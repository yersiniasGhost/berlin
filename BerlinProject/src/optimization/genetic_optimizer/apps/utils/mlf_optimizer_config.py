# optimization/genetic_optimizer/apps/utils/mlf_optimizer_config.py - Updated for unified trade executor

from typing import Optional, List, Dict
from dataclasses import dataclass, field

from optimization.genetic_optimizer.support.types import Json
from optimization.genetic_optimizer.apps.utils.optimizer_config import GAHyperparameters
from optimization.genetic_optimizer.apps.utils.objectives import Objective

from optimization.mlf_optimizer import MlfProblem, MlfFitnessCalculator, MlfIndividual
from optimization.genetic_optimizer.genetic_algorithm.genetic_algorithm import GeneticAlgorithm
from optimization.genetic_optimizer.abstractions.objective_function_base import ObjectiveFunctionBase

from models.monitor_configuration import MonitorConfiguration
from models.indicator_definition import IndicatorDefinition
from optimization.calculators.bt_data_streamer import BacktestDataStreamer
from models.data_container import DataContainer
from candle_aggregator.csa_container import CSAContainer
from models.validation.parameter_constraints import (
    validate_and_constrain_monitor_config_parameters,
    format_constraint_warning_message
)
import logging

logger = logging.getLogger('MlfOptimizerConfig')


@dataclass
class MlfOptimizerConfig:
    objectives: Dict[str, Objective]
    hyper_parameters: GAHyperparameters
    data_config_file: str
    monitor_config: MonitorConfiguration
    configuration: Optional[Json] = None

    fitness_calculator: Optional[MlfFitnessCalculator] = None
    objectives_dict: Optional[Dict[str, ObjectiveFunctionBase]] = None
    model_config: dict = None

    def __post_init__(self):
        self.model_config = {"preprocess_config": "test_ds"}

    def create_project(self) -> GeneticAlgorithm:
        """Create genetic algorithm project with data splits"""
        # Load data and create splits
        dc = DataContainer.from_file(self.data_config_file)
        dc.create_splits(self.hyper_parameters.num_splits)

        # Create streamers for each split
        backtest_streamers: List[BacktestDataStreamer] = []
        aggregator_list = list(self.monitor_config.get_aggregator_configs().keys())

        for split_config in dc.split_configs:
            csa = CSAContainer(split_config, aggregator_list)
            streamer = BacktestDataStreamer()
            streamer.initialize(csa.get_aggregators(), split_config, self.monitor_config)

            # Only add streamer if it has non-empty TICK data
            if streamer.tick_history and len(streamer.tick_history) > 0:
                backtest_streamers.append(streamer)
            else:
                error_msg = (
                    f"ERROR: Skipping data streamer for {split_config['ticker']} "
                    f"({split_config['start_date']} to {split_config['end_date']}) - "
                    f"TICK data is empty. This split will not be used for training."
                )
                logger.error(error_msg)
                print(f"⚠️  {error_msg}")

        # Validate we have at least one valid streamer
        if not backtest_streamers:
            raise ValueError(
                f"ERROR: No valid data streamers created. All {len(dc.split_configs)} splits had empty TICK data. "
                f"Cannot proceed with optimization without training data."
            )

        logger.info(f"Created {len(backtest_streamers)} valid data streamers out of {len(dc.split_configs)} splits")

        # Create fitness calculator with worker configuration
        # If num_workers is 0, use sequential execution (force_sequential=True)
        # If num_workers > 0, use parallel execution with max_workers
        force_sequential = (self.hyper_parameters.num_workers == 0)
        max_workers = self.hyper_parameters.num_workers if self.hyper_parameters.num_workers > 0 else None

        self.fitness_calculator = MlfFitnessCalculator(
            backtest_streamers=backtest_streamers,
            force_sequential=force_sequential,
            max_workers=max_workers,
            split_repeat_count=self.hyper_parameters.split_repeats
        )

        # Add objectives to fitness calculator
        for obj_name, objective in self.objectives.items():
            obj_instance = objective.create_objective()
            self.fitness_calculator.add_objective(obj_instance)

        # Create problem instance
        problem = MlfProblem(
            monitor_configuration=self.monitor_config,
            fitness_calculator=self.fitness_calculator
        )

        # Create and return genetic algorithm with correct parameter name and random seed
        genetic_algorithm = GeneticAlgorithm(
            number_of_generations=self.hyper_parameters.number_of_iterations,
            problem_domain=problem,  # ← FIXED: Use 'problem_domain' not 'problem'
            population_size=self.hyper_parameters.population_size,
            propagation_fraction=self.hyper_parameters.propagation_fraction,
            elitist_size=self.hyper_parameters.elite_size,
            chance_of_mutation=self.hyper_parameters.chance_of_mutation,
            chance_of_crossover=self.hyper_parameters.chance_of_crossover,
            random_seed=self.hyper_parameters.random_seed
        )

        return genetic_algorithm

    def get_trade_executor_summary(self) -> Dict:
        """Get summary of trade executor configuration for logging"""
        trade_exec_config = self.monitor_config.trade_executor

        return {
            'default_position_size': trade_exec_config.default_position_size,
            'stop_loss_pct': f"{trade_exec_config.stop_loss_pct:.1%}",
            'take_profit_pct': f"{trade_exec_config.take_profit_pct:.1%}",
            'trailing_stop_loss': trade_exec_config.trailing_stop_loss,
            'trailing_stop_distance_pct': f"{trade_exec_config.trailing_stop_distance_pct:.1%}",
            'ignore_bear_signals': trade_exec_config.ignore_bear_signals,
            'signal_conflicts': 'Always Checked'  # Always True, not configurable
        }

    @staticmethod
    def from_json(resources: Json, data_config_file: str = None) -> 'MlfOptimizerConfig':
        """Load configuration using MonitorConfiguration with required trade_executor"""
        objectives: Dict[str, Objective] = {}
        hyper_parameters: Optional[GAHyperparameters] = None
        monitor_config: Optional[MonitorConfiguration] = None

        for key, value in resources.items():
            if key == "objectives":
                for objective in value:
                    obj = Objective.from_json(objective)
                    objectives[obj.name] = obj
            elif key == "ga_hyperparameters":
                hyper_parameters = GAHyperparameters.from_json(value)
            elif key == "monitor":
                # Create MonitorConfiguration with required trade_executor
                indicators = []
                if 'indicators' in resources:
                    for ind_def in resources['indicators']:
                        indicators.append(IndicatorDefinition(**ind_def))

                # Validate and constrain indicator parameters to their defined limits
                constrained_indicators, constraint_results = validate_and_constrain_monitor_config_parameters(
                    indicators
                )

                # Log warnings for any constrained parameters
                if constraint_results:
                    warning_message = format_constraint_warning_message(constraint_results)
                    logger.warning(warning_message)
                    print(warning_message)  # Also print to console for immediate visibility

                # Build monitor config dict with all required fields
                monitor_data = {
                    'name': value.get('name', 'GA Monitor'),
                    'description': value.get('description', ''),
                    'enter_long': value.get('enter_long', []),
                    'exit_long': value.get('exit_long', []),
                    'bars': value.get('bars', {}),
                    'indicators': constrained_indicators,  # Use constrained indicators
                    'trade_executor': value.get('trade_executor', {})  # This will be validated as required
                }

                # Create MonitorConfiguration (will validate trade_executor is present)
                monitor_config = MonitorConfiguration(**monitor_data)

        # Validation
        if not monitor_config:
            raise ValueError("No MonitorConfiguration was created.")
        if not hyper_parameters:
            raise ValueError("No GA hyperparameters were provided.")
        if not objectives:
            raise ValueError("No objectives were provided.")
        if not data_config_file:
            raise ValueError("data_config_file path must be provided")

        return MlfOptimizerConfig(
            objectives=objectives,
            hyper_parameters=hyper_parameters,
            data_config_file=data_config_file,
            monitor_config=monitor_config,
            configuration=resources
        )