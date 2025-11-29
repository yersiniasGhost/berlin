"""
Elite Selection Logic
Functions for selecting and balancing elite individuals from Pareto fronts
"""

import numpy as np
from typing import List, Dict
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats


def balance_fronts(front: List[IndividualStats]) -> List[IndividualStats]:
    """
    Balance Pareto front by distance from ideal point

    Args:
        front: List of individuals in a Pareto front

    Returns:
        Sorted list of individuals by distance from ideal point
    """
    ideal_point = np.min([ind.fitness_values for ind in front], axis=0)
    balanced_front = sorted(front, key=lambda ind: np.linalg.norm(ind.fitness_values - ideal_point))
    return balanced_front


def select_winning_population(number_of_elites: int, fronts: Dict[int, List]) -> List[IndividualStats]:
    """
    Select elite individuals from Pareto fronts

    Args:
        number_of_elites: Number of elite individuals to select
        fronts: Dictionary mapping front number to list of individuals

    Returns:
        List of elite individuals
    """
    elitists: List[IndividualStats] = []
    for front in fronts.values():
        sorted_front = balance_fronts(front)
        for stat in sorted_front:
            if len(elitists) < number_of_elites:
                elitists.append(stat)
    return elitists
