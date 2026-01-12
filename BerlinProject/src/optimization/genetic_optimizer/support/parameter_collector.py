"""
Parameter Collector for Genetic Algorithm Optimization

Collects and organizes parameter values from entire populations across generations
to enable parameter distribution histogram visualization.

The collector captures parameters from all individuals in all Pareto fronts,
providing a comprehensive view of the parameter space exploration.
"""

from typing import Dict, List, Any
from collections import defaultdict
import numpy as np
from mlf_utils.log_manager import LogManager


class ParameterCollector:
    """
    Collects and organizes parameter values across optimization generations

    Captures parameters from all individuals in the population (all Pareto fronts)
    to provide a comprehensive view of parameter space exploration during optimization.

    MEMORY OPTIMIZATION: Evolution history is limited to max_evolution_generations to
    prevent unbounded memory growth during long optimization runs.
    """

    # Maximum generations to retain in evolution history
    # Set high to accumulate parameter evolution across all epochs (stores only summary stats, not raw values)
    MAX_EVOLUTION_GENERATIONS = 10000

    def __init__(self):
        self.parameter_history = defaultdict(list)  # {param_name: [values per generation]}
        self.elite_parameter_history = defaultdict(list)  # {param_name: [elite values per generation]}
        self.parameter_metadata = {}  # {param_name: {type, source, range}}

        # Track parameter evolution metrics across generations (bounded)
        self.parameter_evolution_history = defaultdict(lambda: {
            'generations': [],  # List of generation numbers
            'mean': [],         # Mean value per generation
            'std': [],          # Standard deviation per generation
            'min': [],          # Min value per generation
            'max': [],          # Max value per generation
            'median': [],       # Median value per generation
            'elite_mean': [],   # Elite mean per generation
            'elite_std': [],    # Elite std per generation
        })

        self.logger = LogManager().get_logger('ParameterCollector')

    def collect_generation_parameters(self, generation: int, population: List, elites: List = None):
        """
        Extract all parameters from population for a generation

        Args:
            generation: Current generation number
            population: List of IndividualStats objects from entire population (all fronts)
            elites: Optional list of IndividualStats objects from elite population
        """
        self.logger.info(f"📊 Collecting parameters from generation {generation} ({len(population)} individuals)")

        # Collect from full population
        for individual_stats in population:
            self._extract_indicator_parameters(individual_stats.individual, is_elite=False)
            self._extract_bar_weights(individual_stats.individual, is_elite=False)
            self._extract_threshold_parameters(individual_stats.individual, is_elite=False)

        # Collect from elites if provided
        if elites:
            self.logger.info(f"📊 Collecting elite parameters ({len(elites)} elites)")
            for individual_stats in elites:
                self._extract_indicator_parameters(individual_stats.individual, is_elite=True)
                self._extract_bar_weights(individual_stats.individual, is_elite=True)
                self._extract_threshold_parameters(individual_stats.individual, is_elite=True)

        self.logger.info(f"✅ Collected {len(self.parameter_metadata)} unique parameters from {len(population)} individuals")

        # NEW: Calculate and store evolution metrics for this generation
        self._calculate_evolution_metrics(generation)

    def _extract_indicator_parameters(self, individual, is_elite: bool = False):
        """Extract all indicator parameters with full naming"""
        config = individual.monitor_configuration

        for indicator in config.indicators:
            indicator_name = indicator.name

            # Try to get aggregation config (e.g., '5m', '1m') if available
            agg_config = getattr(indicator, 'agg_config', None)
            if agg_config:
                display_name = f"{indicator_name}_{agg_config}"
            else:
                display_name = indicator_name

            for param_name, param_value in indicator.parameters.items():
                # Skip parameters that shouldn't be optimized (like 'trend')
                if param_name in indicator.ranges and indicator.ranges[param_name].get('t') == 'skip':
                    continue

                # Create full parameter name like "macd5m: Fast EMA Period"
                full_name = f"{display_name}: {param_name}"

                # Get parameter type for proper conversion
                param_type = indicator.ranges.get(param_name, {}).get('t', 'unknown')

                # Convert value to numeric type
                try:
                    if param_type == 'int':
                        numeric_value = int(param_value)
                    elif param_type == 'float':
                        numeric_value = float(param_value)
                    else:
                        # Default to float for unknown types
                        numeric_value = float(param_value)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"⚠️ Could not convert parameter '{full_name}' value '{param_value}' to numeric: {e}")
                    continue

                # Store value in appropriate history
                if is_elite:
                    self.elite_parameter_history[full_name].append(numeric_value)
                else:
                    self.parameter_history[full_name].append(numeric_value)

                # Store metadata (first time only)
                if full_name not in self.parameter_metadata:
                    param_range = indicator.ranges.get(param_name, {}).get('r', [])

                    self.parameter_metadata[full_name] = {
                        'type': param_type,
                        'source': f'indicator.{indicator_name}',
                        'range': param_range
                    }

    def _extract_bar_weights(self, individual, is_elite: bool = False):
        """Extract bar indicator weights"""
        config = individual.monitor_configuration

        if not hasattr(config, 'bars') or not config.bars:
            return

        for bar_name, bar_config in config.bars.items():
            if 'indicators' not in bar_config:
                continue

            for indicator_name, weight in bar_config['indicators'].items():
                # Create full parameter name AND bar weights are always floats
                full_name = f"bar_{bar_name}: {indicator_name}_weight"

                # Convert weight to integer (bar weights are always floats)
                try:
                    numeric_weight = float(weight)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"⚠️ Could not convert bar weight '{full_name}' value '{weight}' to int: {e}")
                    continue

                # Store value in appropriate history
                if is_elite:
                    self.elite_parameter_history[full_name].append(numeric_weight)
                else:
                    self.parameter_history[full_name].append(numeric_weight)

                # Store metadata (first time only)
                if full_name not in self.parameter_metadata:
                    weight_ranges = bar_config.get('weight_ranges', {})
                    weight_range = weight_ranges.get(indicator_name, {}).get('r', [])

                    self.parameter_metadata[full_name] = {
                        'type': 'float',
                        'source': f'bar.{bar_name}',
                        'range': weight_range
                    }

    def _extract_threshold_parameters(self, individual, is_elite: bool = False):
        """Extract threshold parameters from enter/exit conditions"""
        config = individual.monitor_configuration

        # Extract enter_long thresholds
        if hasattr(config, 'enter_long') and config.enter_long:
            for idx, condition in enumerate(config.enter_long):
                threshold = condition.get('threshold')
                if threshold is not None:
                    # Use bar name if available, otherwise use index
                    bar_name = condition.get('bar', f'condition_{idx}')
                    full_name = f"enter_long[{bar_name}]: threshold"

                    # Convert threshold to float
                    try:
                        numeric_threshold = float(threshold)
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"⚠️ Could not convert threshold '{full_name}' value '{threshold}' to float: {e}")
                        continue

                    # Store value in appropriate history
                    if is_elite:
                        self.elite_parameter_history[full_name].append(numeric_threshold)
                    else:
                        self.parameter_history[full_name].append(numeric_threshold)

                    if full_name not in self.parameter_metadata:
                        threshold_range = condition.get('threshold_range', [])
                        self.parameter_metadata[full_name] = {
                            'type': 'float',
                            'source': 'threshold.enter_long',
                            'range': threshold_range
                        }

        # Extract exit_long thresholds
        if hasattr(config, 'exit_long') and config.exit_long:
            for idx, condition in enumerate(config.exit_long):
                threshold = condition.get('threshold')
                if threshold is not None:
                    bar_name = condition.get('bar', f'condition_{idx}')
                    full_name = f"exit_long[{bar_name}]: threshold"

                    # Convert threshold to float
                    try:
                        numeric_threshold = float(threshold)
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"⚠️ Could not convert threshold '{full_name}' value '{threshold}' to float: {e}")
                        continue

                    # Store value in appropriate history
                    if is_elite:
                        self.elite_parameter_history[full_name].append(numeric_threshold)
                    else:
                        self.parameter_history[full_name].append(numeric_threshold)

                    if full_name not in self.parameter_metadata:
                        threshold_range = condition.get('threshold_range', [])
                        self.parameter_metadata[full_name] = {
                            'type': 'float',
                            'source': 'threshold.exit_long',
                            'range': threshold_range
                        }

    def get_parameter_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all parameters for dropdown selection

        Returns:
            List of parameter metadata dicts with name, type, source, range, value_count
        """
        return [
            {
                'name': param_name,
                'type': meta['type'],
                'source': meta['source'],
                'range': meta['range'],
                'value_count': len(self.parameter_history[param_name])
            }
            for param_name, meta in sorted(self.parameter_metadata.items())
        ]

    def get_parameter_histogram_data(self, param_name: str, num_bins: int = 20) -> Dict:
        """
        Generate histogram data for a specific parameter with both population and elite series

        Args:
            param_name: Name of parameter to generate histogram for
            num_bins: Number of bins for continuous parameters (default: 20)

        Returns:
            Dict containing histogram bins for both population and elites, metadata, and statistics
        """
        if param_name not in self.parameter_history:
            self.logger.warning(f"⚠️ Parameter '{param_name}' not found in history")
            return {}

        values = self.parameter_history[param_name]
        elite_values = self.elite_parameter_history.get(param_name, [])
        metadata = self.parameter_metadata[param_name]

        if not values:
            return {}

        # Helper function to calculate bins for a set of values
        def calculate_bins(data_values, param_type):
            if param_type == 'int':
                # For integers, use discrete bins
                unique_vals = sorted(set(data_values))
                return {str(val): data_values.count(val) for val in unique_vals}
            else:
                # For floats, check if discrete or continuous distribution
                unique_vals = sorted(set(data_values))

                # If few unique values (≤20), treat as discrete float values
                if len(unique_vals) <= 20:
                    # Discrete bins preserving exact float values
                    return {f"{val:.4f}": data_values.count(val) for val in unique_vals}
                else:
                    # Continuous binning for many unique values
                    hist, bin_edges = np.histogram(data_values, bins=num_bins)
                    return {
                        f"{bin_edges[i]:.4f}-{bin_edges[i+1]:.4f}": int(hist[i])
                        for i in range(len(hist))
                    }

        # Calculate bins for population
        population_bins = calculate_bins(values, metadata['type'])

        # Calculate bins for elites (if available)
        elite_bins = {}
        if elite_values:
            elite_bins = calculate_bins(elite_values, metadata['type'])

        # Calculate statistics for population
        values_array = np.array(values)
        population_statistics = {
            'min': float(np.min(values_array)),
            'max': float(np.max(values_array)),
            'mean': float(np.mean(values_array)),
            'median': float(np.median(values_array)),
            'std': float(np.std(values_array))
        }

        # Calculate statistics for elites (if available)
        elite_statistics = {}
        if elite_values:
            elite_array = np.array(elite_values)
            elite_statistics = {
                'min': float(np.min(elite_array)),
                'max': float(np.max(elite_array)),
                'mean': float(np.mean(elite_array)),
                'median': float(np.median(elite_array)),
                'std': float(np.std(elite_array))
            }

        return {
            'parameter_name': param_name,
            'type': metadata['type'],
            'range': metadata['range'],
            'population': {
                'bins': population_bins,
                'total_values': len(values),
                'statistics': population_statistics
            },
            'elites': {
                'bins': elite_bins,
                'total_values': len(elite_values),
                'statistics': elite_statistics
            } if elite_values else None
        }

    def get_all_parameter_data(self) -> Dict[str, Any]:
        """
        Get complete parameter collection data for serialization

        Returns:
            Dict containing all parameter history and metadata
        """
        return {
            'parameter_list': self.get_parameter_list(),
            'parameter_count': len(self.parameter_metadata),
            'total_values': sum(len(vals) for vals in self.parameter_history.values())
        }

    def _calculate_evolution_metrics(self, generation: int):
        """
        Calculate and store evolution metrics for all parameters in current generation

        Computes mean, std, min, max, median for both population and elite parameters
        and stores them in parameter_evolution_history for tracking over time.

        MEMORY OPTIMIZATION: Automatically trims history to MAX_EVOLUTION_GENERATIONS
        to prevent unbounded memory growth during long optimization runs.

        Args:
            generation: Current generation number
        """
        for param_name in self.parameter_history.keys():
            values = self.parameter_history[param_name]
            elite_values = self.elite_parameter_history.get(param_name, [])

            if not values:
                continue

            # Calculate population statistics with explicit float conversion
            try:
                # Explicitly ensure numeric dtype to prevent string array issues
                values_array = np.array(values, dtype=float)
            except (ValueError, TypeError) as e:
                self.logger.error(f"❌ Failed to convert parameter '{param_name}' values to numeric array: {e}")
                self.logger.error(f"   Values causing issue: {values[:5]}... (showing first 5)")
                continue

            evolution = self.parameter_evolution_history[param_name]

            evolution['generations'].append(generation)
            evolution['mean'].append(float(np.mean(values_array)))
            evolution['std'].append(float(np.std(values_array)))
            evolution['min'].append(float(np.min(values_array)))
            evolution['max'].append(float(np.max(values_array)))
            evolution['median'].append(float(np.median(values_array)))

            # Calculate elite statistics if available
            if elite_values:
                try:
                    elite_array = np.array(elite_values, dtype=float)
                    evolution['elite_mean'].append(float(np.mean(elite_array)))
                    evolution['elite_std'].append(float(np.std(elite_array)))
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"⚠️ Failed to convert elite values for '{param_name}' to numeric: {e}")
                    evolution['elite_mean'].append(None)
                    evolution['elite_std'].append(None)
            else:
                evolution['elite_mean'].append(None)
                evolution['elite_std'].append(None)

            # MEMORY OPTIMIZATION: Trim evolution history to bounded size
            self._trim_evolution_history(param_name)

    def _trim_evolution_history(self, param_name: str):
        """
        Trim evolution history to MAX_EVOLUTION_GENERATIONS entries.
        Removes oldest entries when limit is exceeded.
        """
        evolution = self.parameter_evolution_history[param_name]
        max_gen = self.MAX_EVOLUTION_GENERATIONS

        if len(evolution['generations']) > max_gen:
            # Trim all lists to keep only the most recent entries
            for key in evolution:
                if isinstance(evolution[key], list) and len(evolution[key]) > max_gen:
                    evolution[key] = evolution[key][-max_gen:]

    def get_parameter_evolution_data(self, param_name: str) -> Dict:
        """
        Get evolution metrics for a specific parameter across all generations

        Args:
            param_name: Name of parameter to get evolution data for

        Returns:
            Dict containing time-series data for mean, std, min, max, median across generations
        """
        if param_name not in self.parameter_evolution_history:
            self.logger.warning(f"⚠️ Parameter '{param_name}' not found in evolution history")
            return {}

        evolution = self.parameter_evolution_history[param_name]
        metadata = self.parameter_metadata.get(param_name, {})

        # Detect convergence: Check if std has been consistently low in recent generations
        convergence_detected = False
        convergence_threshold = 0.05  # 5% of range
        if len(evolution['std']) >= 5:
            param_range = metadata.get('range', [])
            if param_range and len(param_range) >= 2:
                range_width = param_range[1] - param_range[0]
                threshold_value = range_width * convergence_threshold
                # Check last 5 generations
                recent_stds = evolution['std'][-5:]
                convergence_detected = all(std < threshold_value for std in recent_stds)

        # Detect jumps: Find generations where mean changed significantly
        jumps = []
        jump_threshold = 0.15  # 15% of range
        if len(evolution['mean']) >= 2:
            param_range = metadata.get('range', [])
            if param_range and len(param_range) >= 2:
                range_width = param_range[1] - param_range[0]
                threshold_value = range_width * jump_threshold
                for i in range(1, len(evolution['mean'])):
                    mean_change = abs(evolution['mean'][i] - evolution['mean'][i-1])
                    if mean_change > threshold_value:
                        jumps.append({
                            'generation': evolution['generations'][i],
                            'from_value': evolution['mean'][i-1],
                            'to_value': evolution['mean'][i],
                            'change': mean_change
                        })

        return {
            'parameter_name': param_name,
            'type': metadata.get('type', 'unknown'),
            'range': metadata.get('range', []),
            'generations': evolution['generations'],
            'mean': evolution['mean'],
            'std': evolution['std'],
            'min': evolution['min'],
            'max': evolution['max'],
            'median': evolution['median'],
            'elite_mean': evolution['elite_mean'],
            'elite_std': evolution['elite_std'],
            'convergence_detected': convergence_detected,
            'jumps': jumps
        }

    def clear_generation_data(self):
        """
        Clear parameter history to show only current generation

        Preserves parameter metadata (names, types, ranges) for dropdown continuity,
        but clears all accumulated values so histogram shows only the next generation's data.
        """
        self.parameter_history.clear()
        self.elite_parameter_history.clear()
        self.logger.info("🧹 Cleared generation parameter values (metadata preserved)")

    def clear(self):
        """Clear all collected parameter data including metadata"""
        self.parameter_history.clear()
        self.elite_parameter_history.clear()
        self.parameter_metadata.clear()
        self.logger.info("🧹 Cleared all parameter data")
