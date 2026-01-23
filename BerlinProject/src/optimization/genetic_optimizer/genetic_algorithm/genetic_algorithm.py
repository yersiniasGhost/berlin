from typing import Iterable, NamedTuple
import time
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import random

from .observer import StatisticsObserver, Observer
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats

from optimization.genetic_optimizer.abstractions import ProblemDomain, IndividualBase
from optimization.genetic_optimizer.genetic_algorithm import collect_fronts, crowd_sort, collect_domination_statistics
from optimization.genetic_optimizer.genetic_algorithm.pareto_front import (
    calculate_elite_diversity, select_distinct_elites
)
from optimization.genetic_optimizer.support.types import Json
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("GeneticAlgorithm")


class IterationStats(NamedTuple):
    iteration_count: int
    time_for_iterations: int
    objective_metrics: List[float]


@dataclass
class GeneticAlgorithm:

    number_of_generations: int
    problem_domain: ProblemDomain
    population_size: int
    propagation_fraction: float
    elitist_size: int = 0
    chance_of_mutation: float = 0.5
    chance_of_crossover: float = 0.5
    number_of_elitist_mutations: int = 3
    propagation_size: int = None
    statistics_observer: Optional[StatisticsObserver] = None
    iteration_index: int = None
    max_stalled_metric: int = 15,
    mutation_decay_factor: float = 0.93
    crossover_decay_factor: float = 0.95
    random_seed: int = 0
    # Diversity reinjection settings
    diversity_threshold: float = 0.80  # Trigger reinjection when similarity > 80%
    diversity_mutation_multiplier: float = 3.0  # Heavy mutation rate for diversity individuals
    diversity_random_fraction: float = 0.30  # Fraction of reinjected individuals that are random


    def __post_init__(self):
        # Set random seeds for reproducibility if seed > 0
        if self.random_seed > 0:
            import numpy as np
            np.random.seed(self.random_seed)
            random.seed(self.random_seed)
            logger.info(f"🎲 Random seed set to {self.random_seed} for reproducibility")

        self.propagation_size = int(self.propagation_fraction * self.population_size)
        self.statistics_observer = StatisticsObserver(objectives=self.problem_domain.fitness_calculator)

    def run_ga_algorithm(self, skip: int = 5) -> Iterable[IterationStats]:
        sum_dt = 0
        s = time.time_ns()
        last_metric = None
        stalled_metric = 0
        for stats in self.run_ga_iterations(skip):
            e = time.time_ns()
            dt = (e - s) / 1e9
            sum_dt += dt
            metrics = stats[1].best_metric_iteration
            if last_metric == metrics[-1]:
                stalled_metric += skip
            else:
                stalled_metric = 0
            last_metric = metrics[-1]

            eta = (sum_dt / (stats[0].iteration + 1)) * (self.number_of_generations - stats[0].iteration)
            out_str = f"GA: {stats[0].iteration}/{self.number_of_generations}, {stalled_metric}/{self.max_stalled_metric}, " \
                      f"{dt:.2f}s, eta: {eta / 60:.2f}"
            s = e
            logger.info(out_str)

            best = stats[1].best_front[0]

            yield IterationStats(stats[0].iteration, dt, metrics)

            if stalled_metric == self.max_stalled_metric or stats[0].iteration == self.number_of_generations - 1:
                self.problem_domain.optimizer_results(best.individual, metrics)
                # plot_combined_results(io, best.individual, plots_path, tn, show_graphs, io.start_date, io.time_frame)
                break

    def run_ga_iterations(self, show_step: int) -> Iterable[Tuple[Observer, StatisticsObserver]]:
        population = self.__initial_generation()
        for iteration in range(0, self.number_of_generations):
            self.iteration_index = iteration
            observer = Observer(iteration=iteration)
            fitness_results = self.__calculate_fitness(iteration=iteration, population=population)
            if not fitness_results:
                observer.success = False
                yield observer, None
                continue
            collect_domination_statistics(fitness_results)
            fronts = collect_fronts(fitness_results)
            observer.individual_stats = fitness_results
            self.statistics_observer.collect_metrics(fronts)
            if iteration % show_step == 0 or iteration == self.number_of_generations-1:
                observer.complete(fronts=fronts)
                yield observer, self.statistics_observer

            self.__post_iteration_cleanup(iteration=iteration)

            # TODO:  Should be putting objectives as a stopping criteria??
            if iteration != self.number_of_generations - 1:
                population = self.prepare_next_generation(fronts)


    @staticmethod
    def debug_population(population, caller):
        return
        # for i in range(len(population)):
        #     for j in range(i + 1, len(population)):  # Start from i + 1 to avoid comparing the same object
        #         if population[i] == population[j]:  # Use the overridden __eq__ method
        #             print("\n\nWTF", caller)
        #             print(population[i].instance_id, population[i].source, "other", population[j].instance_id, population[j].source, "\n----------------")
        #             # break  # No need to check the rest if we found a duplicate


    def prepare_next_generation(self, fronts: Dict[int, List]) -> List[IndividualBase]:
        com = max(1.0e-6, self.chance_of_mutation * self.mutation_decay_factor ** float(self.iteration_index))
        print("New mutation rate: ", com)
        coc = max(1.0e-6, self.chance_of_crossover * self.crossover_decay_factor ** self.iteration_index)
        print("New crossover rate: ", coc)

        elitists, parents = self.select_winning_population(fronts)

        # ===== DIVERSITY REINJECTION CHECK =====
        # Analyze elite diversity and reinject if needed to prevent premature convergence
        elitists = self._check_and_reinject_diversity(elitists, fronts)

        self.debug_population(elitists, 'e1')
        self.debug_population(parents, "p1")
        self.debug_population(elitists+parents, 'ep')
        mutate_these_elitist = []
        original_elites = [e.copy_individual('original elite') for e in elitists]
        for grp in range(self.number_of_elitist_mutations):
            for e in elitists:
                mutate_these_elitist.append(e.copy_individual(f"mutate elite #{grp}"))

        self.mutate_population(mutate_these_elitist)
        elitists += mutate_these_elitist
        self.mutate_population(parents)
        offspring1 = self.create_offspring(self.population_size-20, original_elites)
        elitists += offspring1
        offspring = self.create_offspring(len(elitists), parents)
        self.debug_population(offspring, 'off')
        elitists += offspring
        self.debug_population(elitists, 'e2')
        left = self.population_size - len(elitists)
        if left > 0:
            self.mutate_population(parents)
            elitists += parents[:left]
        self.debug_population(elitists, 'e4')

        left = self.population_size - len(elitists)
        last_left = left
        while left > 0:
            print("MUTATING more to fill population: ", left)
            for p in original_elites + parents:
                p2 = p.copy_individual("missing")
                self.mutate_population([p2])
                elitists += [p2]
                left = self.population_size - len(elitists)
                if left <= 0:
                    break
            if last_left == left:
                print('WTF')
            last_left = left

        self.debug_population(elitists, 'e3')

        return elitists

    def _check_and_reinject_diversity(self, elitists: List[IndividualBase],
                                       fronts: Dict[int, List]) -> List[IndividualBase]:
        """
        Check elite diversity and reinject diverse individuals if needed.

        When similarity_score > diversity_threshold, the elites have converged
        too much and we need to inject fresh genetic material:
        - Keep only distinct elites (one per cluster)
        - Fill remaining slots with heavy mutations (70%) and random individuals (30%)

        Args:
            elitists: Current elite population (IndividualBase instances)
            fronts: Pareto fronts containing IndividualStats

        Returns:
            Modified elite population with diversity reinjection if needed
        """
        if len(elitists) < 3:
            return elitists  # Not enough elites to analyze

        # Get IndividualStats from first front for diversity analysis
        front_0_stats = fronts.get(0, [])
        if len(front_0_stats) < 3:
            return elitists

        # Calculate diversity metrics
        diversity_info = calculate_elite_diversity(front_0_stats[:self.elitist_size], threshold=0.05)

        # Store diversity metrics for reporting (can be accessed by visualization)
        self._last_diversity_info = diversity_info

        similarity = diversity_info['similarity_score']
        if similarity <= self.diversity_threshold:
            # Diversity is acceptable
            logger.info(f"✅ Elite diversity OK: similarity={similarity:.2f}, "
                       f"distinct={diversity_info['distinct_count']}")
            return elitists

        # Low diversity detected - need reinjection
        logger.warning(f"⚠️ Low elite diversity: similarity={similarity:.2f} > threshold={self.diversity_threshold}")
        logger.info(f"🔄 Performing diversity reinjection...")

        # Select distinct elites (one representative per cluster)
        distinct_stats = select_distinct_elites(front_0_stats, diversity_info, max_keep=5)
        distinct_elites = [stat.individual.copy_individual("distinct_elite") for stat in distinct_stats]

        logger.info(f"   Kept {len(distinct_elites)} distinct elites from {len(elitists)} total")

        # Calculate how many to reinject
        num_to_reinject = self.elitist_size - len(distinct_elites)
        if num_to_reinject <= 0:
            return distinct_elites[:self.elitist_size]

        # Create diverse variants
        reinjected = self._create_diverse_variants(distinct_elites, num_to_reinject)
        logger.info(f"   Created {len(reinjected)} diverse variants for reinjection")

        # Combine distinct elites with reinjected variants
        new_elitists = distinct_elites + reinjected

        return new_elitists[:self.elitist_size]

    def _create_diverse_variants(self, source_elites: List[IndividualBase],
                                  count: int) -> List[IndividualBase]:
        """
        Create diverse variants through heavy mutation and random generation.

        Strategy:
        - 30% fresh random individuals (new genetic material)
        - 70% heavily mutated existing elites (explore nearby space more aggressively)

        Args:
            source_elites: Elite individuals to base mutations on
            count: Number of variants to create

        Returns:
            List of diverse IndividualBase instances
        """
        variants = []
        num_random = int(count * self.diversity_random_fraction)
        num_mutated = count - num_random

        # Create fresh random individuals using initial population generator
        if num_random > 0:
            try:
                random_individuals = self.problem_domain.create_initial_population(num_random)
                for ind in random_individuals:
                    ind.source = "diversity_random"
                variants.extend(random_individuals)
                logger.info(f"   Created {len(random_individuals)} fresh random individuals")
            except Exception as e:
                logger.warning(f"Failed to create random individuals: {e}")

        # Create heavily mutated variants
        for i in range(num_mutated):
            if not source_elites:
                break
            source = source_elites[i % len(source_elites)]
            mutated = source.copy_individual("diversity_mutation")

            # Apply heavy mutation (multiple times normal rate)
            heavy_mutation_rate = min(1.0, self.chance_of_mutation * self.diversity_mutation_multiplier)
            for _ in range(3):  # Multiple mutation passes
                self.problem_domain.mutation_function(mutated, heavy_mutation_rate, self.iteration_index)

            variants.append(mutated)

        return variants

    def mutate_population(self, population: List[IndividualBase]):
        com = max(0.01, self.chance_of_mutation * self.mutation_decay_factor ** float(self.iteration_index))
        for i in range(len(population)):
            self.problem_domain.mutation_function(population[i], com, self.iteration_index)
        return population

    def create_elitist_offspring(self, elitists: List[IndividualBase]) -> List[IndividualBase]:
        next_population = []
        for e in elitists:
            next_population += self.problem_domain.elitist_offspring(e)

    def create_offspring(self, retained_population_size: int, parents: List[IndividualBase]) -> List[IndividualBase]:
        coc = max(0.01, self.chance_of_crossover * self.crossover_decay_factor ** self.iteration_index)

        next_population = []
        num_children = self.population_size - retained_population_size
        # TODO replace this with tournament selection
        random.shuffle(parents)
        for i in range(int(len(parents)/2)):
            mom = parents[i]
            dad = parents[len(parents)-1-i]
            if mom == dad:
                continue
            next_population += self.problem_domain.cross_over_function(mom, dad, coc)
            self.debug_population(next_population, f"{i}")
            if len(next_population) >= num_children:
                break
        return next_population

    def select_winning_population(self, fronts: Dict[int, List]) -> Tuple[List[IndividualBase], List[IndividualBase]]:
        elitists: List[IndividualBase] = []
        parents: List[IndividualBase] = []

        for front in fronts.values():
            sorted_front = crowd_sort(front)
            for stat in sorted_front:
                if len(elitists) < self.elitist_size:
                    elitists.append(stat.individual.copy_individual("keep elite"))
                elif len(parents) < self.propagation_size:
                    parents.append(stat.individual.copy_individual("prop"))
        return elitists, parents

    @staticmethod
    def __crowd_sort(front: List[IndividualStats], size: int) -> List[IndividualStats]:
        sorted_front = crowd_sort(front)
        return sorted_front[0:size]

    def __post_iteration_cleanup(self, iteration: str):
        self.problem_domain.post_iteration_cleanup(iteration)

    def __initial_generation(self) -> List[IndividualBase]:
        return self.problem_domain.create_initial_population(self.population_size)

    def __calculate_fitness(self, iteration: int, population: List[IndividualBase]) -> List[IndividualStats]:
        fitness = self.problem_domain.calculate_fitness_functions(iteration_key=iteration,
                                                                  population=population)
        return fitness

    def response(self) -> Json:
        return {'type': 'geneticAlgorithm',
                'numberOfGenerations': self.number_of_generations,
                'populationSize': self.population_size,
                'propagationFraction': self.propagation_fraction,
                'elitistSize': self.elitist_size,
                'propagationSize': self.propagation_size,
                'chanceOfMutation': self.chance_of_mutation,
                'chanceOfCrossover': self.chance_of_crossover}

