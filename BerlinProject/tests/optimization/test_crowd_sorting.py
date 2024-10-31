import unittest
import numpy as np
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class Solution:
    """Represents a solution in the multi-objective space."""
    objectives: np.ndarray
    crowding_distance: float = 0.0


def calculate_crowding_distances(solutions: List[Solution]) -> None:
    """
    Calculate crowding distances for a set of solutions.

    The crowding distance is a measure of how close a solution is to its neighbors.
    Solutions with larger crowding distances are preferred to maintain diversity.

    Args:
        solutions: List of solutions in the same non-dominated front
    """
    if len(solutions) <= 2:
        # Set infinite crowding distance for edge cases
        for solution in solutions:
            solution.crowding_distance = np.inf
        return

    num_objectives = len(solutions[0].objectives)
    num_solutions = len(solutions)

    # Reset crowding distances
    for solution in solutions:
        solution.crowding_distance = 0

    # Calculate crowding distance for each objective
    for obj_index in range(num_objectives):
        # Sort solutions based on current objective
        solutions.sort(key=lambda x: x.objectives[obj_index])

        # Get objective bounds
        obj_min = solutions[0].objectives[obj_index]
        obj_max = solutions[-1].objectives[obj_index]
        scale = obj_max - obj_min

        # Set infinite distance to boundary points
        solutions[0].crowding_distance = np.inf
        solutions[-1].crowding_distance = np.inf

        # Calculate crowding distances for intermediate points
        if scale > 0:  # Only if objectives are not all equal
            for i in range(1, num_solutions - 1):
                distance = (solutions[i + 1].objectives[obj_index] -
                            solutions[i - 1].objectives[obj_index]) / scale
                solutions[i].crowding_distance += distance


def crowding_sort(solutions: List[Solution]) -> List[Solution]:
    """
    Sort solutions based on their crowding distances in descending order.

    Args:
        solutions: List of solutions with calculated crowding distances

    Returns:
        Sorted list of solutions
    """
    return sorted(solutions, key=lambda x: x.crowding_distance, reverse=True)

class TestCrowdSorting(unittest.TestCase):

    def test_crowding_sort(self):
        """Test the crowding sort implementation with various scenarios."""
        # Create test solutions
        solutions = [
            Solution(np.array([1.0, 1.0])),  # Solution A
            Solution(np.array([2.0, 2.0])),  # Solution B
            Solution(np.array([3.0, 1.5])),  # Solution C
            Solution(np.array([1.5, 2.5])),  # Solution D
        ]

        # Calculate crowding distances
        calculate_crowding_distances(solutions)

        # Sort solutions
        sorted_solutions = crowding_sort(solutions)

        # Print results
        print("\nCrowding sort results:")
        for i, sol in enumerate(sorted_solutions):
            print(f"Solution {i}: objectives={sol.objectives}, "
                  f"crowding_distance={sol.crowding_distance}")

        # Verify that boundary points have infinite distance
        assert np.isinf(sorted_solutions[0].crowding_distance)
        assert np.isinf(sorted_solutions[1].crowding_distance)

        # Verify that intermediate points have finite distances
        assert np.isfinite(sorted_solutions[2].crowding_distance)
        assert np.isfinite(sorted_solutions[3].crowding_distance)
