"""
Optimizer Module
Genetic algorithm optimization with real-time visualization

This module provides a modular structure for the optimizer functionality,
splitting the original monolithic optimizer_routes.py into focused components:

- constants.py: Shared constants and configuration
- elite_selection.py: Pareto front balancing and elite selection
- chart_generation.py: Chart data generation for visualization
- genetic_algorithm.py: Core GA execution with WebSocket updates
- results_manager.py: Results saving and export functionality

All route handlers remain in the parent optimizer_routes.py file for
backward compatibility and easier Flask Blueprint management.
"""

# Import all modules for easy access
from .constants import PERFORMANCE_TABLE_COLUMNS, get_table_columns_from_data
from .elite_selection import balance_fronts, select_winning_population
from .chart_generation import (
    generate_optimizer_chart_data,
    load_raw_candle_data,
    extract_trade_history_and_pnl_from_portfolio,
    generate_chart_data_for_individual_with_new_indicators
)
from .genetic_algorithm import (
    heartbeat_thread,
    run_genetic_algorithm_threaded_with_new_indicators
)
from .results_manager import save_optimization_results_with_new_indicators

__all__ = [
    # Constants
    'PERFORMANCE_TABLE_COLUMNS',
    'get_table_columns_from_data',

    # Elite selection
    'balance_fronts',
    'select_winning_population',

    # Chart generation
    'generate_optimizer_chart_data',
    'load_raw_candle_data',
    'extract_trade_history_and_pnl_from_portfolio',
    'generate_chart_data_for_individual_with_new_indicators',

    # Genetic algorithm
    'heartbeat_thread',
    'run_genetic_algorithm_threaded_with_new_indicators',

    # Results management
    'save_optimization_results_with_new_indicators',
]
