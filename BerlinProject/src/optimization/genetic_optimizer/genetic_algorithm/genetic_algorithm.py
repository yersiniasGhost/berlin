from typing import Iterable, NamedTuple
import time
import logging
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import random

from .observer import StatisticsObserver, Observer
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats

from optimization.genetic_optimizer.abstractions import ProblemDomain, IndividualBase
from optimization.genetic_optimizer.genetic_algorithm import collect_fronts, crowd_sort, collect_domination_statistics
from optimization.genetic_optimizer.support.types import Json


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
    max_stalled_metric: int = 50

    def __post_init__(self):
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
            logging.info(out_str)

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
            collect_domination_statistics(fitness_results)
            fronts = collect_fronts(fitness_results)

            self.statistics_observer.collect_metrics(fronts)
            if iteration % show_step == 0 or iteration == self.number_of_generations-1:
                observer.complete(fronts=fronts)
                yield observer, self.statistics_observer

            self.__post_iteration_cleanup(iteration=iteration)

            # TODO:  Should be putting objectives as a stopping criteria??
            if iteration != self.number_of_generations - 1:
                population = self.prepare_next_generation(fronts)

    def prepare_next_generation(self, fronts: Dict[int, List]) -> List[IndividualBase]:
        e = time.time_ns()
        elitists, parents = self.select_winning_population(fronts)
        mutate_these_elitist = []
        for _ in range(self.number_of_elitist_mutations):
            for e in elitists:
                mutate_these_elitist.append(e.copy_individual())

        for _ in range(len(elitists)):
            mutate_these_elitist.append(elitists[0].copy_individual())
        for _ in range(len(elitists)):
            mutate_these_elitist.append(elitists[1].copy_individual())

        # offspring = self.create_offspring(len(elitists)+len(parents), mutate_these_elitist[0]+parents)
        offspring = self.create_offspring(len(elitists)+len(parents), mutate_these_elitist+parents)
        self.mutate_population(parents)
        self.mutate_population(mutate_these_elitist)
        # for temp_elitists in mutate_these_elitist:
        #     self.mutate_population(temp_elitists)
        #     elitists += temp_elitists
        elitists += mutate_these_elitist
        elitists += offspring
        elitists += parents[:-len(mutate_these_elitist)]

        return elitists

    def mutate_population(self, population: List[IndividualBase]):
        for i in range(len(population)):
            self.problem_domain.mutation_function(population[i], self.chance_of_mutation, self.iteration_index)
        return population

    def create_elitist_offspring(self, elitists: List[IndividualBase]) -> List[IndividualBase]:
        next_population = []
        for e in elitists:
            next_population += self.problem_domain.elitist_offspring(e)

    def create_offspring(self, retained_population_size: int, parents: List[IndividualBase]) -> List[IndividualBase]:
        next_population = []
        random.shuffle(parents)
        num_children = self.population_size - retained_population_size
        num_breeds = int((num_children / (len(parents) / 2)))
        # TODO replace this with tournament selection
        while len(next_population) < num_children:
            for i in range(int(len(parents)/2)):
                mom = parents[i]
                dad = parents[len(parents)-1-i]
                next_population += self.problem_domain.cross_over_function(mom, dad, self.chance_of_crossover)
                if len(next_population) >= num_children:
                    break
        return next_population

    def select_winning_population(self, fronts: Dict[int, List]) -> Tuple[List[IndividualBase],List[IndividualBase]]:
        elitists: List[IndividualBase] = []
        parents: List[IndividualBase] = []
        if self.elitist_size > 0:
            for front in fronts.values():
                if len(elitists) >= self.elitist_size:
                    break
                stats_in_front = [i_stats for i_stats in front]
                sorted_stats = self.problem_domain.get_sorted_individual_stats(stats_in_front)
                # sorted_front = self.__crowd_sort(front, self.elitist_size-len(new_population))
                for stat in sorted_stats:
                    if len(elitists) < self.elitist_size:
                        elitists += [stat.individual.copy_individual()]
                        continue
                    break
        # for i in elitists:
        #     parents += [i]
            # parents += [i.copy_individual()]

        for front in fronts.values():
            n = len(front) + len(parents)
            if n > self.propagation_size:
                sorted_front = self.__crowd_sort(front, self.propagation_size - len(parents))
                parents += [stat.individual for stat in sorted_front]
                break
            parents += [stat.individual for stat in front]

        return elitists, parents

    @staticmethod
    def __crowd_sort(front: List[IndividualStats], size: int) -> List[IndividualStats]:
        sorted_front = crowd_sort(front)
        r = sorted_front[0:size]
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

