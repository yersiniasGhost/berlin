from dataclasses import dataclass
from optimization.genetic_optimizer.support.types import Json


@dataclass
class GAHyperparameters:
    number_of_iterations: int
    population_size: int
    propagation_fraction: float
    elite_size: int
    chance_of_mutation: float
    chance_of_crossover: float


    @staticmethod
    def from_json(json: Json) -> 'GAHyperparameters':
        number_of_iterations = json.get("number_of_iterations", 1000)
        population_size = json.get("population_size", 300)
        propagation_fraction = json.get('propagation_fraction', 0.4)
        elite_size = json.get('elite_size', 4)
        chance_of_mutation = json.get('chance_of_mutation', 0.075)
        chance_of_crossover = json.get('chance_of_crossover', 0.075)
        return GAHyperparameters(number_of_iterations=number_of_iterations,
                                 population_size=population_size,
                                 propagation_fraction=propagation_fraction,
                                 elite_size=elite_size,
                                 chance_of_crossover=chance_of_crossover,
                                 chance_of_mutation=chance_of_mutation)

