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
        """
        Create genetic algorithm project with unified trade executor.
        Trade executor configuration is now handled within monitor_config.
        """
        # NEW: Create backtest streamer with unified trade executor (no separate trade_executor parameter)
        backtest_streamer = BacktestDataStreamer(
            monitor_config=self.monitor_config,
            data_config_file=self.data_config_file
        )

        # Create fitness calculator
        self.fitness_calculator = MlfFitnessCalculator(
            backtest_streamer=backtest_streamer,
            data_config_file=self.data_config_file
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

        # Create and return genetic algorithm with correct parameter name
        genetic_algorithm = GeneticAlgorithm(
            number_of_generations=self.hyper_parameters.number_of_iterations,
            problem_domain=problem,  # ← FIXED: Use 'problem_domain' not 'problem'
            population_size=self.hyper_parameters.population_size,
            propagation_fraction=self.hyper_parameters.propagation_fraction,
            elitist_size=self.hyper_parameters.elite_size,
            chance_of_mutation=self.hyper_parameters.chance_of_mutation,
            chance_of_crossover=self.hyper_parameters.chance_of_crossover
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

                # Build monitor config dict with all required fields
                monitor_data = {
                    'name': value.get('name', 'GA Monitor'),
                    'description': value.get('description', ''),
                    'enter_long': value.get('enter_long', []),
                    'exit_long': value.get('exit_long', []),
                    'bars': value.get('bars', {}),
                    'indicators': indicators,
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