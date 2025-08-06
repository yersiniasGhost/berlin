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
from portfolios.trade_executor_no_bear import TradeExecutorNoBear


@dataclass
class MlfOptimizerConfig:
    objectives: Dict[str, Objective]
    hyper_parameters: GAHyperparameters
    data_config_file: str
    monitor_config: MonitorConfiguration  # REMOVED: monitor: Monitor
    configuration: Optional[Json] = None

    fitness_calculator: Optional[MlfFitnessCalculator] = None
    objectives_dict: Optional[Dict[str, ObjectiveFunctionBase]] = None
    model_config: dict = None

    def __post_init__(self):
        self.model_config = {"preprocess_config": "test_ds"}

    def create_project(self) -> GeneticAlgorithm:
        trade_executor = TradeExecutorNoBear(
            monitor_config=self.monitor_config,
            default_position_size=100.0,
            stop_loss_pct=0.01,
            take_profit_pct=0.01
        )

        # Always create shared streamer
        backtest_streamer = BacktestDataStreamer(
            monitor_config=self.monitor_config,
            data_config_file=self.data_config_file,
            trade_executor=trade_executor
        )

        # Always pass shared streamer
        self.fitness_calculator = MlfFitnessCalculator(
            backtest_streamer=backtest_streamer
        )

        self.objectives_dict = {}
        for objective in self.objectives.values():
            obj = objective.create_objective()
            self.fitness_calculator.add_objective(obj, objective.weight)
            self.objectives_dict[obj.name] = obj

        # FIXED: Only pass monitor_configuration
        problem_domain = MlfProblem(
            fitness_calculator=self.fitness_calculator,  # Add this line
            monitor_configuration=self.monitor_config
        )

        ga = GeneticAlgorithm(
            number_of_generations=self.hyper_parameters.number_of_iterations,
            problem_domain=problem_domain,
            population_size=self.hyper_parameters.population_size,
            propagation_fraction=self.hyper_parameters.propagation_fraction,
            elitist_size=self.hyper_parameters.elite_size,
            chance_of_mutation=self.hyper_parameters.chance_of_mutation,
            chance_of_crossover=self.hyper_parameters.chance_of_crossover
        )
        return ga

    @staticmethod
    def from_json(resources: Json, data_config_file: str = None) -> 'MlfOptimizerConfig':
        """Load configuration using only MonitorConfiguration"""
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
                # FIXED: Create MonitorConfiguration directly from monitor data
                indicators = []
                if 'indicators' in resources:
                    for ind_def in resources['indicators']:
                        indicators.append(IndicatorDefinition(**ind_def))

                monitor_config = MonitorConfiguration(
                    name=value.get('name', 'GA Monitor'),
                    description=value.get('description', ''),
                    enter_long=value.get('enter_long', []),
                    exit_long=value.get('exit_long', []),
                    bars=value.get('bars', {}),
                    indicators=indicators
                )

        # Validation - REMOVED monitor validation
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