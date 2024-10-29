import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict
import time
import copy

from optimization.genetic_optimizer.genetic_algorithm import IndividualStats
from optimization.genetic_optimizer.abstractions.fitness_calculator import FitnessCalculator


def get_fitness_metrics_from_fronts(fronts: Dict[int, List[IndividualStats]]) -> List[List[float]]:
    return [i_stats.fitness_values for front in fronts.values() for i_stats in front]


@dataclass
class Observer:

    iteration: int
    fronts: Dict[int, List[IndividualStats]] = None
    fitness_values: np.array = None   # List[List[float]] = None
    start_time = None
    delta_time = None

    def __post_init__(self):
        self.start_time = time.time()

    def get_best_results(self) -> List[IndividualStats]:
        return self.fronts[0]

    def complete(self, fronts: Dict[int, List[IndividualStats]]):
        self.fronts = copy.deepcopy(fronts)
        self.fitness_values = np.transpose(np.array(get_fitness_metrics_from_fronts(self.fronts)))
        self.delta_time = time.time() - self.start_time


@dataclass
class StatisticsObserver:
    objectives: FitnessCalculator

    best_metric_iteration: List[float] = None
    worst_metric_iteration: List[float] = None
    average_metric_iteration: List[float] = None

    best_metrics: List[List[float]] = field(default_factory=list)
    worst_metrics: List[List[float]] = field(default_factory=list)
    average_metrics: List[List[float]] = field(default_factory=list)

    best_individual: IndividualStats = None
    best_front: List[IndividualStats] = None
    best_word: List[int] = None

    def collect_metrics(self, fronts: Dict[int, List[IndividualStats]]):
        # stats = []
        # for front in fronts.values():
        #     for i_stats in front:
        #         stats.append(self.objectives.collect_metrics(i_stats))

        stats = get_fitness_metrics_from_fronts(fronts)
        stats_by_ind = self.objectives.get_sorted_fitness_stats(stats)
        ind_sums = stats_by_ind.sum(1)[..., None]
        x = np.append(stats_by_ind, ind_sums, 1)
        num_objectives = self.objectives.get_number_of_objectives()
        sorted_stats = x[x[:, num_objectives].argsort()]
        self.best_metric_iteration = sorted_stats[0]
        self.worst_metric_iteration = sorted_stats[-1]
        self.average_metric_iteration = sorted_stats[int(len(sorted_stats)/2)]

        # self.best_word = sorted_stats[0].word

        # self.best_metric_iteration = self.objectives.transform_metrics([np.min(row) for row in stats_by_metric])
        # self.worst_metric_iteration = self.objectives.transform_metrics([np.max(row) for row in stats_by_metric])
        # self.average_metric_iteration=self.objectives.transform_metrics([np.average(row) for row in stats_by_metric])

        self.best_metrics.append(self.best_metric_iteration)
        self.worst_metrics.append(self.worst_metric_iteration)
        self.average_metrics.append(self.average_metric_iteration)

        self.best_front = copy.deepcopy(fronts[0])

