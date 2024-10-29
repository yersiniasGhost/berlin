import numpy as np
from typing import Optional, List, Dict
from dataclasses import dataclass
from pathlib import Path
import json

from optimization.genetic_optimizer.support.types import Json
from optimization.genetic_optimizer.apps.utils.optimizer_config import GAHyperparameters
from optimization.genetic_optimizer.apps.utils.objectives import Objective

from optimization.mlf_optimizer import MlfProblem, MlfFitnessCalculator, MlfIndividual
from optimization.genetic_optimizer.genetic_algorithm.genetic_algorithm import GeneticAlgorithm
from optimization.genetic_optimizer.abstractions.objective_function_base import ObjectiveFunctionBase

from models import MonitorConfiguration


@dataclass
class MlfOptimizerConfig:
    objectives: Dict[str, Objective]
    hyper_parameters: GAHyperparameters
    monitor: MonitorConfiguration
    configuration: Optional[Json] = None

    fitness_calculator: Optional[MlfFitnessCalculator] = None
    objectives_dict: Optional[Dict[str, ObjectiveFunctionBase]] = None

    def write_configuration(self, path: Path):
        with open(path, 'w') as f:
            f.write(json.dumps(self.configuration, indent=2))

    def create_project(self) -> GeneticAlgorithm:

        self.fitness_calculator = MlfFitnessCalculator()
        self.objectives_dict = {}
        for objective in self.objectives.values():
            obj = objective.create_objective()
            self.fitness_calculator.add_objective(obj, objective.weight)
            self.objectives_dict[obj.name] = obj

        # TODO:  Check if the objectives with thresholds are less than the max PoF
        problem_domain = MlfProblem(self.fitness_calculator, monitor=monitor_configuration)

        ga = GeneticAlgorithm(number_of_generations=self.hyper_parameters.number_of_iterations,
                              problem_domain=problem_domain,
                              population_size=self.hyper_parameters.population_size,
                              propagation_fraction=self.hyper_parameters.propagation_fraction,
                              elitist_size=self.hyper_parameters.elite_size,
                              chance_of_mutation=self.hyper_parameters.chance_of_mutation,
                              chance_of_crossover=self.hyper_parameters.chance_of_crossover)
        return ga

    @staticmethod
    def from_json(resources: Json) -> 'MlfOptimizerConfig':
        objectives: Dict[str, Objective] = {}
        hyper_parameters: Optional[GAHyperparameters] = None
        monitor: Optional[MonitorConfiguration] = None
        for key, value in resources.items():
            if key == "objectives":
                for objective in value:
                    obj = Objective.from_json(objective)
                    objectives[obj.name] = obj
            elif key == "ga_hyperparameters":
                hyper_parameters = GAHyperparameters.from_json(value)
            elif key == "monitor_configuration":
                monitor_id = value
                monitor = MonitorConfiguration()

        if not monitor:
            raise ValueError("No Monitor configuration was created.")

        return MlfOptimizerConfig(objectives=objectives,
                                  hyper_parameters=hyper_parameters,
                                  configuration=resources,
                                  monitor=monitor
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
