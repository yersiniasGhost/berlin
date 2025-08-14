"""
Genetic Algorithm Optimizer Service

Extracted from app.py to provide reusable optimization functionality.
Maintains exact same behavior as original implementation.
"""

import json
import logging
import os
import sys
from typing import Tuple, Optional, Any, Dict
from pathlib import Path

# Set up logging first
logger = logging.getLogger('GAOptimizerService')

# Add project path to find optimization modules
current_dir = os.path.dirname(os.path.abspath(__file__))
# Go up two levels: services -> optimizer_visualization -> src
sys.path.insert(0, os.path.join(current_dir, '..', '..'))

from optimization.genetic_optimizer.apps.utils.mlf_optimizer_config import MlfOptimizerConfig


class GAOptimizerService:
    """
    Service class for running genetic algorithm optimizations.

    Extracted from app.py with identical behavior to maintain compatibility.
    """

    def __init__(self):
        """Initialize the GA Optimizer Service"""
        logger.info("🔧 GAOptimizerService initialized")

    def run_optimization(
        self,
        ga_config_path: str,
        data_config_path: str
    ) -> Tuple[Optional[Any], Optional[Any], Optional[Any], Optional[str]]:
        """
        Run genetic algorithm optimization and return results.

        This is the exact same logic as the original run_genetic_algorithm function
        from app.py, extracted into a reusable service.

        Args:
            ga_config_path: Path to GA configuration JSON file
            data_config_path: Path to data configuration JSON file

        Returns:
            Tuple of (best_individual, optimization_stats, io, test_name)
            Returns (None, None, None, None) if optimization fails
        """
        try:
            logger.info("🚀 Starting optimization following the_optimizer_new.py pattern")

            # Load configuration exactly like the_optimizer_new.py
            with open(ga_config_path) as f:
                config_data = json.load(f)

            # Get test name
            test_name = config_data.get('test_name', config_data.get('monitor', {}).get('name', 'NoNAME'))
            logger.info(f"   Test: {test_name}")

            # Create optimizer config exactly like the_optimizer_new.py
            io = MlfOptimizerConfig.from_json(config_data, data_config_path)
            genetic_algorithm = io.create_project()

            # Override to single generation for visualization
            genetic_algorithm.number_of_generations = 1

            logger.info(f"   Generations: {genetic_algorithm.number_of_generations}")
            logger.info(f"   Population Size: {genetic_algorithm.population_size}")
            logger.info(f"   Data Config: {data_config_path}")

            # Run optimization exactly like the_optimizer_new.py
            best_individual = None
            optimization_stats = None

            for stats in genetic_algorithm.run_ga_iterations(1):
                best_individual = stats[1].best_front[0].individual
                optimization_stats = stats

                # Log progress like the_optimizer_new.py
                objectives = [o.name for o in io.fitness_calculator.objectives]
                metrics = zip(objectives, stats[1].best_metric_iteration)
                metric_out = [f"{a}={b:.4f}" for a, b in metrics]

                out_str = f"{test_name}, {stats[0].iteration}/{genetic_algorithm.number_of_generations}, " \
                         f"0.0s, eta: 0.0m, {metric_out}"

                logger.info(out_str)

            if best_individual:
                logger.info("✅ Optimization completed successfully")
                return best_individual, optimization_stats, io, test_name
            else:
                logger.warning("⚠️ No best individual found")
                return None, None, None, None

        except Exception as e:
            logger.error(f"❌ Error running optimization: {e}")
            import traceback
            traceback.print_exc()
            return None, None, None, None

    def validate_config_files(self, ga_config_path: str, data_config_path: str) -> Dict[str, Any]:
        """
        Validate configuration files and return validation results.

        This maintains the same validation logic as the original app.py

        Args:
            ga_config_path: Path to GA configuration file
            data_config_path: Path to data configuration file

        Returns:
            Dictionary with validation results
        """
        try:
            # Check if files exist
            if not os.path.exists(ga_config_path):
                return {
                    'success': False,
                    'error': f'GA config file not found: {ga_config_path}'
                }

            if not os.path.exists(data_config_path):
                return {
                    'success': False,
                    'error': f'Data config file not found: {data_config_path}'
                }

            # Load and validate GA config
            with open(ga_config_path) as f:
                ga_config = json.load(f)

            # Load and validate data config
            with open(data_config_path) as f:
                data_config = json.load(f)

            # Extract summary information (same as original)
            objectives_list = ga_config.get('objectives', [])
            objective_names = []

            # Handle objectives as either list or dict
            if isinstance(objectives_list, list):
                objective_names = [obj.get('objective', 'Unknown') for obj in objectives_list]
            elif isinstance(objectives_list, dict):
                objective_names = list(objectives_list.keys())

            summary = {
                'ga_config': {
                    'test_name': ga_config.get('test_name', 'Unknown'),
                    'population_size': ga_config.get('population_size', 'Unknown'),
                    'generations': ga_config.get('number_of_generations', 'Unknown'),
                    'objectives': objective_names
                },
                'data_config': {
                    'symbol': data_config.get('symbol') or data_config.get('ticker', 'Unknown'),
                    'start_date': data_config.get('start_date', 'Unknown'),
                    'end_date': data_config.get('end_date', 'Unknown'),
                    'time_increment': data_config.get('time_increment', 1)
                }
            }

            return {
                'success': True,
                'summary': summary,
                'ga_config_path': ga_config_path,
                'data_config_path': data_config_path
            }

        except Exception as e:
            logger.error(f"Error validating configs: {e}")
            return {
                'success': False,
                'error': str(e)
            }