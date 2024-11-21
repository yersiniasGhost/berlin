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


@dataclass
class MlfOptimizerConfig:
    objectives: Dict[str, Objective]
    hyper_parameters: GAHyperparameters
    data_config: dict
    monitor_config: MonitorConfiguration
    monitor: Monitor
    configuration: Optional[Json] = None

    fitness_calculator: Optional[MlfFitnessCalculator] = None
    objectives_dict: Optional[Dict[str, ObjectiveFunctionBase]] = None
    model_config: dict = None

    def __post_init__(self):
        self.model_config = { "preprocess_config": "test_ds" }


    def write_configuration(self, path: Path):
        with open(path, 'w') as f:
            f.write(json.dumps(self.configuration, indent=2))

    def create_project(self) -> GeneticAlgorithm:

        data_streamer = DataStreamer(self.data_config, self.model_config)
        self.fitness_calculator = MlfFitnessCalculator(data_streamer=data_streamer)
        self.objectives_dict = {}
        for objective in self.objectives.values():
            obj = objective.create_objective()
            self.fitness_calculator.add_objective(obj, objective.weight)
            self.objectives_dict[obj.name] = obj

        # TODO:  Check if the objectives with thresholds are less than the max PoF
        problem_domain = MlfProblem(self.fitness_calculator,
                                    monitor_configuration=self.monitor_config, monitor=self.monitor)

        ga = GeneticAlgorithm(number_of_generations=self.hyper_parameters.number_of_iterations,
                              problem_domain=problem_domain,
                              population_size=self.hyper_parameters.population_size,
                              propagation_fraction=self.hyper_parameters.propagation_fraction,
                              elitist_size=self.hyper_parameters.elite_size,
                              chance_of_mutation=self.hyper_parameters.chance_of_mutation,
                              chance_of_crossover=self.hyper_parameters.chance_of_crossover)
        return ga

    def create_backtest_env(self):
        data_streamer = DataStreamer(self.data_config, self.model_config, self.monitor_config)

        bt = MonitorResultsBacktest("Optimizer", self.monitor, )
        data_streamer.connect_tool(bt)
        return data_streamer, bt

    @staticmethod
    def from_json(resources: Json) -> 'MlfOptimizerConfig':
        objectives: Dict[str, Objective] = {}
        hyper_parameters: Optional[GAHyperparameters] = None
        monitor: Optional[Monitor] = None
        data_config: Optional[dict] = None
        for key, value in resources.items():
            if key == "objectives":
                for objective in value:
                    obj = Objective.from_json(objective)
                    objectives[obj.name] = obj
            elif key == "ga_hyperparameters":
                hyper_parameters = GAHyperparameters.from_json(value)
            elif key == "monitor":
                monitor = Monitor(**value)
            elif key == "data":
                data_config = value
            elif key == 'indicators':
                indicators = []
                for ind_def in value:
                    indicators.append(IndicatorDefinition(**ind_def))
                monitor_config = MonitorConfiguration(name="fuckoff", indicators=indicators)

        if not monitor:
            raise ValueError("No Monitor configuration was created.")

        return MlfOptimizerConfig(objectives=objectives,
                                  hyper_parameters=hyper_parameters,
                                  data_config=data_config,
                                  monitor=monitor,
                                  monitor_config=monitor_config,

                                  )

    @staticmethod
    def from_file(filepath: Path, ga_config: Path = None) -> "MlfOptimizerConfig":
        ga_config_json: Json = None
        if ga_config:
            with open(ga_config) as f:
                ga_config_json = json.load(f)
        with open(filepath) as f:
            input_json = json.load(f)
            if ga_config:
                input_json = {**input_json, **ga_config_json}
            return MlfOptimizerConfig.from_json(input_json)
