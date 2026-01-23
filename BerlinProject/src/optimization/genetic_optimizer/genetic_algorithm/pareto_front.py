from typing import Tuple, List, Dict, Optional
import numpy as np

from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("ParetoFront")


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


def get_pareto_front(individuals: List[IndividualStats], index: int, max_index: int) -> Tuple[List[IndividualStats], int]:
    output = []
    while len(output) == 0 and index <= max_index:
        output = [ind for ind in individuals if ind.dominated_by_count == index]
        index += 1

    return output, index



def collect_fronts(individuals: List[IndividualStats]) -> Dict[int, List]:
    index = 0
    max_domination = max([i.dominated_by_count for i in individuals])
    pareto_fronts = dict()
    cnt = 0
    while True:
        front, index = get_pareto_front(individuals, index, max_domination)
        if len(front) == 0:
            break
        pareto_fronts[cnt] = balance_fronts(front)
        cnt += 1
        # index += 1
    return pareto_fronts


def balance_fronts(front: List[IndividualStats]) -> List[IndividualStats]:
    ideal_point = np.min([ind.fitness_values for ind in front], axis=0)
    balanced_front = sorted(front, key=lambda ind: np.linalg.norm(ind.fitness_values - ideal_point))
    return balanced_front


def sort_front(individuals: List[IndividualStats], objective_index: int) -> List[IndividualStats]:
    return sorted(individuals, key=lambda x: x.fitness_values[objective_index])


def crowd_sort(front: List[IndividualStats]) -> List[IndividualStats]:
    """
    NSGA-II crowding distance calculation and sorting.

    For each objective, sort individuals and calculate crowding distance.
    Crowding distance measures how isolated a solution is - higher values mean
    the solution is in a less crowded region and should be preserved for diversity.

    Boundary solutions (best/worst in any objective) get infinite distance to
    ensure they're always preserved, maintaining the full extent of the Pareto front.

    Returns solutions sorted by crowding distance DESCENDING (most isolated first).
    """
    # Edge case: small fronts don't need crowding calculation
    if len(front) <= 2:
        for ind in front:
            ind.crowding_distance = np.inf
        return front

    eps = np.finfo(float).eps
    objective_count = len(front[0].fitness_values)

    # Reset crowding distances before calculation
    for ind in front:
        ind.crowding_distance = 0.0

    # Calculate crowding distance contribution from each objective
    for oc in range(objective_count):
        sorted_front = sort_front(front, oc)
        obj_min = sorted_front[0].fitness_values[oc]
        obj_max = sorted_front[-1].fitness_values[oc]
        denom = obj_max - obj_min + eps

        # Boundary points get infinite distance (always preserve extremes)
        sorted_front[0].crowding_distance = np.inf
        sorted_front[-1].crowding_distance = np.inf

        # Interior points: distance = normalized gap between neighbors
        for i in range(1, len(sorted_front) - 1):
            fv_prev = sorted_front[i - 1].fitness_values[oc]
            fv_next = sorted_front[i + 1].fitness_values[oc]
            sorted_front[i].crowding_distance += (fv_next - fv_prev) / denom

    # Sort DESCENDING: higher crowding distance = more isolated = preferred for diversity
    return sorted(front, key=lambda x: x.crowding_distance, reverse=True)


# ================================================================================
# ELITE DIVERSITY DETECTION
# ================================================================================

def extract_all_parameters(individual) -> List[float]:
    """
    Extract all optimizable parameters from an individual for diversity comparison.

    Extracts:
    - Indicator weights from bars
    - Trend indicator weights from bars
    - Trend thresholds from bars
    - Indicator parameters (period, multiplier, etc.)
    - Enter/exit condition thresholds

    Returns:
        List of float parameter values for comparison
    """
    params = []

    try:
        config = individual.monitor_configuration

        # 1. Extract bar indicator weights and trend settings
        if hasattr(config, 'bars') and config.bars:
            for bar_name, bar_config in config.bars.items():
                # Signal indicator weights
                if 'indicators' in bar_config:
                    for indicator_name, weight in bar_config['indicators'].items():
                        if isinstance(weight, (int, float)):
                            params.append(float(weight))

                # Trend indicator weights
                if 'trend_indicators' in bar_config:
                    for trend_name, trend_config in bar_config['trend_indicators'].items():
                        if isinstance(trend_config, dict):
                            weight = trend_config.get('weight', 0.0)
                            params.append(float(weight))
                        elif isinstance(trend_config, (int, float)):
                            params.append(float(trend_config))

                # Trend threshold (gate threshold)
                if 'trend_threshold' in bar_config:
                    params.append(float(bar_config['trend_threshold']))

        # 2. Extract indicator parameters (period, multiplier, etc.)
        if hasattr(config, 'indicators') and config.indicators:
            for indicator in config.indicators:
                if hasattr(indicator, 'parameters') and indicator.parameters:
                    for param_name, param_value in indicator.parameters.items():
                        if isinstance(param_value, (int, float)):
                            params.append(float(param_value))

        # 3. Extract enter/exit thresholds
        if hasattr(config, 'enter_long') and config.enter_long:
            for condition in config.enter_long:
                if 'threshold' in condition and isinstance(condition['threshold'], (int, float)):
                    params.append(float(condition['threshold']))

        if hasattr(config, 'exit_long') and config.exit_long:
            for condition in config.exit_long:
                if 'threshold' in condition and isinstance(condition['threshold'], (int, float)):
                    params.append(float(condition['threshold']))

    except Exception as e:
        logger.warning(f"Error extracting parameters: {e}")

    return params


def calculate_elite_diversity(elites: List[IndividualStats], threshold: float = 0.05) -> Dict:
    """
    Analyze diversity of elite population by comparing parameter values.

    Uses normalized Euclidean distance in parameter space to measure how
    "spread out" the elite population is. High similarity indicates premature
    convergence and loss of genetic diversity.

    Args:
        elites: List of elite IndividualStats
        threshold: Distance below which two elites are considered "similar" (default 0.05 = 5%)

    Returns:
        Dict with:
        - similarity_score: 0.0 (all different) to 1.0 (all identical)
        - distinct_count: Number of meaningfully different elites
        - similar_pairs: List of (index_i, index_j, distance) tuples
        - needs_reinjection: Boolean flag if diversity is critically low
        - mean_distance: Average pairwise distance
    """
    if len(elites) < 2:
        return {
            'similarity_score': 0.0,
            'distinct_count': len(elites),
            'similar_pairs': [],
            'needs_reinjection': False,
            'mean_distance': 1.0
        }

    # Extract parameter vectors from each elite
    param_vectors = []
    for elite in elites:
        if hasattr(elite, 'individual') and elite.individual is not None:
            params = extract_all_parameters(elite.individual)
            if params:
                param_vectors.append(np.array(params))

    if len(param_vectors) < 2:
        return {
            'similarity_score': 0.0,
            'distinct_count': len(param_vectors),
            'similar_pairs': [],
            'needs_reinjection': False,
            'mean_distance': 1.0
        }

    # Ensure all vectors have the same length
    min_len = min(len(v) for v in param_vectors)
    param_vectors = [v[:min_len] for v in param_vectors]

    # Stack into matrix and normalize to [0,1] range
    param_matrix = np.array(param_vectors)
    mins = param_matrix.min(axis=0)
    maxs = param_matrix.max(axis=0)
    ranges = maxs - mins
    ranges[ranges == 0] = 1  # Avoid division by zero for constant parameters
    normalized = (param_matrix - mins) / ranges

    # Calculate pairwise distances
    similar_pairs = []
    all_distances = []
    n = len(elites)

    for i in range(min(len(param_vectors), n)):
        for j in range(i + 1, min(len(param_vectors), n)):
            dist = np.linalg.norm(normalized[i] - normalized[j])
            all_distances.append(dist)
            if dist < threshold:
                similar_pairs.append((i, j, float(dist)))

    # Calculate overall similarity score
    max_pairs = n * (n - 1) / 2
    similarity_score = len(similar_pairs) / max_pairs if max_pairs > 0 else 0.0

    # Count distinct elites using union-find clustering
    distinct_count = count_distinct_clusters(n, similar_pairs)

    # Calculate mean distance for reporting
    mean_distance = np.mean(all_distances) if all_distances else 1.0

    # Determine if reinjection is needed
    needs_reinjection = similarity_score > 0.7 or distinct_count < 3

    result = {
        'similarity_score': float(similarity_score),
        'distinct_count': distinct_count,
        'similar_pairs': similar_pairs[:10],  # Limit to first 10 for display
        'needs_reinjection': needs_reinjection,
        'mean_distance': float(mean_distance)
    }

    if needs_reinjection:
        logger.warning(f"⚠️ Low elite diversity: similarity={similarity_score:.2f}, distinct={distinct_count}")

    return result


def count_distinct_clusters(n: int, similar_pairs: List[Tuple]) -> int:
    """
    Count the number of distinct clusters using Union-Find algorithm.

    Elites connected by similar_pairs are grouped together.
    Returns the number of separate groups (distinct elite archetypes).

    Args:
        n: Total number of elites
        similar_pairs: List of (i, j, distance) tuples marking similar elites

    Returns:
        Number of distinct clusters
    """
    # Initialize each element as its own parent
    parent = list(range(n))

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])  # Path compression
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Union similar elites
    for i, j, _ in similar_pairs:
        if i < n and j < n:
            union(i, j)

    # Count distinct roots
    roots = set(find(i) for i in range(n))
    return len(roots)


def select_distinct_elites(elites: List[IndividualStats], diversity_info: Dict,
                           max_keep: int = 5) -> List[IndividualStats]:
    """
    Select only distinct elites from each cluster.

    Keeps the best elite (by index) from each cluster of similar elites.
    This preserves diversity by avoiding redundant solutions.

    Args:
        elites: List of elite IndividualStats
        diversity_info: Result from calculate_elite_diversity()
        max_keep: Maximum distinct elites to keep

    Returns:
        List of distinct elites (one per cluster)
    """
    if not elites:
        return []

    n = len(elites)
    similar_pairs = diversity_info.get('similar_pairs', [])

    # Build union-find structure
    parent = list(range(n))

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Union similar elites
    for i, j, _ in similar_pairs:
        if i < n and j < n:
            union(i, j)

    # Group elites by cluster
    clusters = {}
    for i in range(n):
        root = find(i)
        if root not in clusters:
            clusters[root] = []
        clusters[root].append(i)

    # Select best from each cluster (lowest index = best rank)
    distinct_indices = []
    for cluster_indices in clusters.values():
        best_idx = min(cluster_indices)  # Best ranked in this cluster
        distinct_indices.append(best_idx)

    # Sort by original ranking and limit
    distinct_indices = sorted(distinct_indices)[:max_keep]

    return [elites[i] for i in distinct_indices]


