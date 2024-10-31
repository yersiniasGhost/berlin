import unittest
import numpy as np
from optimization.genetic_optimizer.genetic_algorithm.pareto_front import is_dominating, collect_domination_statistics, crowd_sort
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats


class TestIndividualStats(unittest.TestCase):

    def setUp(self):
        # Sample individuals with fitness values for tests
        self.ind1 = IndividualStats(index=1, fitness_values=np.array([1, 2]), individual=None)
        self.ind2 = IndividualStats(index=2, fitness_values=np.array([2, 3]), individual=None)
        self.ind3 = IndividualStats(index=3, fitness_values=np.array([3, 1]), individual=None)
        self.ind4 = IndividualStats(index=4, fitness_values=np.array([1, 1]), individual=None)
        self.individuals = [self.ind1, self.ind2, self.ind3, self.ind4]



    def test_initialization(self):
        """Test that IndividualStats instances initialize correctly."""
        self.assertEqual(self.ind1.index, 1)
        self.assertEqual(self.ind1.dominated_by_count, 0)
        self.assertEqual(self.ind1.crowding_distance, 0)
        self.assertEqual(self.ind1.dominates_over, [])



    def test_is_dominating(self):
        """Test the dominance function is_dominating."""
        # ind4 dominates ind1 and ind2 based on fitness values
        self.assertTrue(is_dominating(self.ind4.fitness_values, self.ind1.fitness_values))
        self.assertTrue(is_dominating(self.ind4.fitness_values, self.ind2.fitness_values))
        self.assertFalse(is_dominating(self.ind2.fitness_values, self.ind3.fitness_values))



    def test_collect_domination_statistics(self):
        """Test collect_domination_statistics to ensure correct domination tracking."""
        collect_domination_statistics(self.individuals)

        # After domination statistics, ind4 should dominate ind1 and ind2
        self.assertIn(self.ind1, self.ind4.dominates_over)
        self.assertIn(self.ind2, self.ind4.dominates_over)
        self.assertEqual(self.ind1.dominated_by_count, 1)
        self.assertEqual(self.ind2.dominated_by_count, 2)
        self.assertEqual(self.ind4.dominated_by_count, 0)  # ind4 is not dominated by any



    def test_reduce_dominated_by_count(self):
        """Test reducing dominated_by_count with a floor of 0."""
        self.ind1.dominated_by_count = 1
        self.ind1.reduce_dominated_by_count()
        self.assertEqual(self.ind1.dominated_by_count, 0)
        # Ensure it doesn’t go below zero
        self.ind1.reduce_dominated_by_count()
        self.assertEqual(self.ind1.dominated_by_count, 0)



    def test_calculate_weighted_sum(self):
        """Test calculate_sum method for weighted fitness values."""
        weights = [0.5, 0.5]
        expected_sum = np.sum(self.ind1.fitness_values * weights)
        self.assertAlmostEqual(self.ind1.calculate_sum(weights), expected_sum)



    def test_crowd_sort2(self):
        """Test crowding distance calculation and sorting."""
        # Create a specific test case for crowding
        ind_a = IndividualStats(index=1, fitness_values=np.array([1, 1]), individual=None)
        ind_b = IndividualStats(index=2, fitness_values=np.array([2, 2]), individual=None)
        ind_c = IndividualStats(index=3, fitness_values=np.array([3, 1]), individual=None)
        test_front = [ind_a, ind_b, ind_c]

        sorted_front = crowd_sort(test_front)

        # Test boundary points have infinite crowding distance
        self.assertTrue(np.isinf(sorted_front[0].crowding_distance))
        self.assertTrue(np.isinf(sorted_front[-1].crowding_distance))

        # Test middle point has finite crowding distance
        self.assertTrue(np.isfinite(ind_b.crowding_distance))

    def test_crowd_sort(self):
        """Test crowding distance sorting within a front."""
        front = [self.ind1, self.ind2, self.ind3, self.ind4]
        # Call the crowd_sort function to calculate crowding distances
        sorted_front = crowd_sort(front)

        # Check that boundary individuals have infinite crowding distance
        self.assertEqual(sorted_front[0].crowding_distance, np.inf)
        self.assertEqual(sorted_front[-1].crowding_distance, np.inf)

        # Check that crowding distances are calculated
        for i in range(1, len(sorted_front) - 1):
            self.assertNotEqual(sorted_front[i].crowding_distance, 0)
            self.assertNotEqual(sorted_front[i].crowding_distance, np.inf)

