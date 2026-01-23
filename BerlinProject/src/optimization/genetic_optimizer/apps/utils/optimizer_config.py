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
    num_splits: int
    random_seed: int = 0
    num_workers: int = 0
    split_repeats: int = 3
    daily_splits: bool = False
    seed_with_original: bool = True  # Include original monitor config as first individual

    @staticmethod
    def from_json(json: Json) -> 'GAHyperparameters':
        number_of_iterations = json.get("number_of_iterations", 1000)
        population_size = json.get("population_size", 300)
        propagation_fraction = json.get('propagation_fraction', 0.4)
        elite_size = json.get('elite_size', 4)
        chance_of_mutation = json.get('chance_of_mutation', 0.075)
        chance_of_crossover = json.get('chance_of_crossover', 0.075)
        num_splits = json.get('num_splits', 4)
        random_seed = json.get('random_seed', 0)
        num_workers = json.get('num_workers', 0)
        split_repeats = json.get('split_repeats', 3)
        daily_splits = json.get('daily_splits', False)
        seed_with_original = json.get('seed_with_original', True)
        return GAHyperparameters(number_of_iterations=number_of_iterations,
                                 population_size=population_size,
                                 propagation_fraction=propagation_fraction,
                                 elite_size=elite_size,
                                 chance_of_crossover=chance_of_crossover,
                                 chance_of_mutation=chance_of_mutation,
                                 num_splits=num_splits,
                                 random_seed=random_seed,
                                 num_workers=num_workers,
                                 split_repeats=split_repeats,
                                 daily_splits=daily_splits,
                                 seed_with_original=seed_with_original)

