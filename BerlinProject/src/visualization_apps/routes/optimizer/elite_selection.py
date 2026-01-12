"""
Elite Selection Logic
Functions for selecting and balancing elite individuals from Pareto fronts
"""

from typing import List, Dict
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
from optimization.genetic_optimizer.genetic_algorithm.pareto_front import crowd_sort


def select_winning_population(number_of_elites: int, fronts: Dict[int, List]) -> List[IndividualStats]:
    """
    Select elite individuals from Pareto fronts using NSGA-II crowding distance.

    Uses crowd_sort to maintain diversity along the Pareto front rather than
    converging all elites toward a single ideal point.

    Args:
        number_of_elites: Number of elite individuals to select
        fronts: Dictionary mapping front number to list of individuals

    Returns:
        List of elite individuals with diversity preserved
    """
    elitists: List[IndividualStats] = []
    for front in fronts.values():
        # Use crowd_sort for diversity-preserving selection
        sorted_front = crowd_sort(front)
        for stat in sorted_front:
            if len(elitists) < number_of_elites:
                elitists.append(stat)
    return elitists
