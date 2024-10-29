from typing import Tuple, List, Dict
import numpy as np

from optimization.genetic_optimizer.genetic_algorithm import IndividualStats


# Non-dominating sorting:
# A(x1|y1) dominates B(x2|y2) when:
# (x1 <= x2 AND y1 <= y2)  AND (x1 < x2 OR y1 < y2)
#  Determine which front the individuals belong to.


# Assumes minimization!!
def is_dominating(solution_a: np.array, solution_b: np.array) -> bool:
    if np.less_equal(solution_a, solution_b).all():
        if np.less(solution_a, solution_b).any():
            return True
    return False


def collect_domination_statistics(individuals: List[IndividualStats]):
    for i, solution_a in enumerate(individuals):
        for j, solution_b in enumerate(individuals):
            if i == j:
                continue
            if is_dominating(solution_a.fitness_values, solution_b.fitness_values):
                solution_a.dominates(solution_b)
                solution_b.dominated_by_solution()


def get_pareto_front(individuals: List[IndividualStats]) -> List[IndividualStats]:
    output = [ind for ind in individuals if ind.dominated_by_count == 0]
    return output


def advance_pareto_front(individuals: List[IndividualStats]):
    for ind in individuals:
        ind.reduce_dominated_by_count()
        for dom in ind.dominates_over:
            dom.reduce_dominated_by_count()


def collect_fronts(individuals: List[IndividualStats]) -> Dict[int, List]:
    more_to_come = True
    index = 0
    pareto_fronts = dict()
    while more_to_come:
        front = get_pareto_front(individuals)
        if len(front) == 0:
            break
        advance_pareto_front(front)
        pareto_fronts[index] = front
        index += 1
    return pareto_fronts


def sort_front(individuals: List[IndividualStats], objective_index: int) -> List[IndividualStats]:
    return sorted(individuals, key=lambda x: x.fitness_values[objective_index])


def crowd_sort(front: List[IndividualStats]) -> List[IndividualStats]:
    """
    For each objective, sort the individuals then calculate the crowding distance for each individual
    """
    eps = np.finfo(float).eps
    objective_count = len(front[0].fitness_values)
    for oc in range(0, objective_count):
        sorted_front = sort_front(front, oc)
        denom = sorted_front[-1].fitness_values[oc] - sorted_front[0].fitness_values[oc] + eps
        sorted_front[0].crowding_distance = np.inf
        sorted_front[-1].crowding_distance = np.inf
        for i in range(1, len(sorted_front)-1):
            fv0 = sorted_front[i-1].fitness_values[oc]
            fv1 = sorted_front[i+1].fitness_values[oc]
            sorted_front[i].crowding_distance += -(fv1-fv0) / denom
            # The minus makes the largest absolute values the largest negative number.  Easier for sorting
            # and selecting.

    return sorted(front, key=lambda x: x.crowding_distance)


