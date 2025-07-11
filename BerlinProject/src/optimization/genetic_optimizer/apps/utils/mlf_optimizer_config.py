from typing import Optional, List, Dict
from dataclasses import dataclass, field
from pathlib import Path
import json

from operations.monitor_backtest_results import MonitorResultsBacktest
from optimization.genetic_optimizer.support.types import Json
from optimization.genetic_optimizer.apps.utils.optimizer_config import GAHyperparameters
from optimization.genetic_optimizer.apps.utils.objectives import Objective

from optimization.mlf_optimizer import MlfProblem, MlfFitnessCalculator, MlfIndividual
from optimization.genetic_optimizer.genetic_algorithm.genetic_algorithm import GeneticAlgorithm
from optimization.genetic_optimizer.abstractions.objective_function_base import ObjectiveFunctionBase

from models.monitor_configuration import MonitorConfiguration
from models.monitor_model import Monitor
from models.indicator_definition import IndicatorDefinition
from data_streamer import DataStreamer
from optimization.calculators.bt_data_streamer import BacktestDataStreamer
from portfolios.trade_executor_new import TradeExecutorNew


@dataclass
class MlfOptimizerConfig:
    objectives: Dict[str, Objective]
    hyper_parameters: GAHyperparameters
    data_config_file: str  # FIXED: Consistent field name
    monitor_config: MonitorConfiguration
    monitor: Monitor
    configuration: Optional[Json] = None

    fitness_calculator: Optional[MlfFitnessCalculator] = None
    objectives_dict: Optional[Dict[str, ObjectiveFunctionBase]] = None
    model_config: dict = None

    def __post_init__(self):
        self.model_config = {"preprocess_config": "test_ds"}

    def write_configuration(self, path: Path):
        with open(path, 'w') as f:
            f.write(json.dumps(self.configuration, indent=2))

    def create_project(self) -> GeneticAlgorithm:
        trade_executor = TradeExecutorNew(
            monitor_config=self.monitor_config,
            default_position_size=100.0,
            stop_loss_pct=0.01,
            take_profit_pct=0.02
        )

        backtest_streamer = BacktestDataStreamer(
            monitor_config=self.monitor_config,
            data_config_file=self.data_config_file,  # FIXED: Uses correct field name
            trade_executor=trade_executor
        )

        self.fitness_calculator = MlfFitnessCalculator(
            backtest_streamer=backtest_streamer
        )

        self.objectives_dict = {}
        for objective in self.objectives.values():
            obj = objective.create_objective()
            self.fitness_calculator.add_objective(obj, objective.weight)
            self.objectives_dict[obj.name] = obj

        problem_domain = MlfProblem(
            self.fitness_calculator,
            monitor_configuration=self.monitor_config,
            monitor=self.monitor
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
        """
        Simplified version now that Monitor model uses 'bars' directly
        """
        objectives: Dict[str, Objective] = {}
        hyper_parameters: Optional[GAHyperparameters] = None
        monitor: Optional[Monitor] = None
        monitor_config: Optional[MonitorConfiguration] = None

        for key, value in resources.items():
            if key == "objectives":
                for objective in value:
                    obj = Objective.from_json(objective)
                    objectives[obj.name] = obj
            elif key == "ga_hyperparameters":
                hyper_parameters = GAHyperparameters.from_json(value)
            elif key == "monitor":
                # Now this works directly since Monitor expects 'bars'
                monitor = Monitor(**value)
            elif key == 'indicators':
                indicators = []
                for ind_def in value:
                    indicators.append(IndicatorDefinition(**ind_def))
                # Use monitor name if available
                monitor_name = monitor.name if monitor else "Unnamed Monitor"
                monitor_config = MonitorConfiguration(name=monitor_name, indicators=indicators)

        # Validation
        if not monitor:
            raise ValueError("No Monitor configuration was created.")
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
            monitor=monitor,
            monitor_config=monitor_config,
            configuration=resources
        )

    @staticmethod
    def from_file(filepath: Path, ga_config: Path = None, data_config_file: str = None) -> "MlfOptimizerConfig":
        """
        FIXED: Updated to pass data_config_file through to from_json
        """
        ga_config_json: Json = None
        if ga_config:
            with open(ga_config) as f:
                ga_config_json = json.load(f)

        with open(filepath) as f:
            input_json = json.load(f)
            if ga_config:
                input_json = {**input_json, **ga_config_json}

            # FIXED: Pass data_config_file to from_json
            return MlfOptimizerConfig.from_json(input_json, data_config_file)