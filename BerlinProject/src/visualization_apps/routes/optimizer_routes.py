"""
Optimizer Visualization Routes
Handles genetic algorithm optimization with real-time WebSocket updates
"""

from flask import Blueprint, render_template, request, jsonify
import os
import json
import time
import threading
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from .optimization_state import OptimizationState

from optimization.genetic_optimizer.apps.utils.mlf_optimizer_config import MlfOptimizerConfig
from portfolios.portfolio_tool import TradeReason
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
from optimization.mlf_optimizer.mlf_individual_stats import MlfIndividualStats
from optimization.genetic_optimizer.support.parameter_collector import ParameterCollector

# Import mlf_utils
from mlf_utils import sanitize_nan_values, FileUploadHandler, ConfigLoader
from mlf_utils.log_manager import LogManager

# Import optimizer module functions (extracted for modularity)
from .optimizer import (
    # Constants
    PERFORMANCE_TABLE_COLUMNS,
    get_table_columns_from_data,
    # Elite selection
    balance_fronts,
    select_winning_population,
    # Chart generation
    generate_optimizer_chart_data,
    load_raw_candle_data,
    extract_trade_history_and_pnl_from_portfolio,
    generate_chart_data_for_individual_with_new_indicators,
    # Genetic algorithm
    heartbeat_thread,
    run_genetic_algorithm_threaded_with_new_indicators,
    # Results management
    save_optimization_results_with_new_indicators
)

logger = LogManager().get_logger("OptimizerVisualization")

# Create Blueprint
optimizer_bp = Blueprint('optimizer', __name__, url_prefix='/optimizer')

# Create upload handler for optimizer routes
upload_handler = FileUploadHandler(upload_dir='uploads')
config_loader = ConfigLoader(config_dir='inputs')


# =============================================================================
# Flask Route Handlers
# All utility functions have been extracted to the optimizer module
# =============================================================================


@optimizer_bp.route('/')
def optimizer_main():
    """Main optimizer visualization page"""
    return render_template('optimizer/main.html')


@optimizer_bp.route('/api/upload_file', methods=['POST'])
def upload_file():
    """Handle file uploads and save them temporarily"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Empty filename'})

        # Determine file type
        file_type = request.form.get('type', 'unknown')

        # Generate safe filename with type prefix
        filename = f"{file_type}_{file.filename}"
        filepath = Path('uploads') / filename

        # Ensure uploads directory exists
        filepath.parent.mkdir(exist_ok=True)

        # Save file
        file.save(filepath)

        return jsonify({
            'success': True,
            'filename': filename,
            'filepath': str(filepath.absolute()),
            'type': file_type
        })

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/load_examples')
def load_examples():
    """Load example configurations for form initialization"""
    try:
        examples = {}

        # Load example GA config
        example_ga_path = Path('inputs/dan_fuck_around1.json')
        if example_ga_path.exists():
            with open(example_ga_path) as f:
                examples['ga_config'] = json.load(f)
        else:
            # Provide default GA config structure with NEW indicators
            examples['ga_config'] = {
                "test_name": "New_Test",
                "monitor": {
                    "name": "New Strategy",
                    "description": "Description for new strategy",
                    "trade_executor": {
                        "default_position_size": 100.0,
                        "stop_loss_pct": 0.02,
                        "take_profit_pct": 0.04,
                        "ignore_bear_signals": False,
                        "trailing_stop_loss": True,
                        "trailing_stop_distance_pct": 0.01,
                        "trailing_stop_activation_pct": 0.005
                    },
                    "enter_long": [],
                    "exit_long": [],
                    "bars": {}
                },
                "indicators": [
                    {
                        "name": "sma_crossover",
                        "display_name": "SMA Crossover",
                        "parameters": {
                            "period": {"min": 10, "max": 50, "default": 20},
                            "crossover_value": {"min": 0.01, "max": 0.05, "default": 0.015},
                            "trend": {"choices": ["bullish", "bearish"], "default": "bullish"}
                        },
                        "enabled": True
                    }
                ],
                "objectives": [
                    {
                        "objective": "MaximizeProfit",
                        "weight": 1.0
                    }
                ],
                "ga_hyperparameters": {
                    "number_of_iterations": 100,
                    "population_size": 50,
                    "propagation_fraction": 0.4,
                    "elite_size": 12,
                    "chance_of_mutation": 0.05,
                    "chance_of_crossover": 0.03
                }
            }

        # Provide default data config
        examples['data_config'] = {
            "ticker": "NVDA",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }

        return jsonify({
            'success': True,
            'examples': examples
        })

    except Exception as e:
        logger.error(f"Error loading example configs: {e}")
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/load_configs', methods=['POST'])
def load_configs():
    """Load and validate the uploaded configuration files"""
    try:
        data = request.get_json()
        logger.info(f"Received load_configs request with data: {data}")

        # The file upload component sends keys like 'ga_config' and 'data_config'
        ga_config_path = data.get('ga_config')
        data_config_path = data.get('data_config')

        if not ga_config_path or not data_config_path:
            available_keys = list(data.keys()) if data else []
            logger.error(f"Missing config files. Available keys: {available_keys}")
            return jsonify({'success': False, 'error': f'Both config files are required. Received keys: {available_keys}'})

        # Validate files exist
        if not Path(ga_config_path).exists():
            return jsonify({'success': False, 'error': f'GA config file not found: {ga_config_path}'})

        if not Path(data_config_path).exists():
            return jsonify({'success': False, 'error': f'Data config file not found: {data_config_path}'})

        # Load and validate GA config
        with open(ga_config_path) as f:
            ga_config = json.load(f)

        # Load and validate data config
        with open(data_config_path) as f:
            data_config = json.load(f)

        logger.info(f"Successfully loaded configs for optimizer visualization")
        return jsonify({
            'success': True,
            'ga_config': ga_config,  # Full config for editing
            'data_config': data_config  # Full config for editing
        })

    except Exception as e:
        logger.error(f"Error loading configs: {e}")
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/start_optimization', methods=['POST'])
def start_optimization():
    """HTTP endpoint to start optimization - creates temp files and triggers WebSocket"""
    try:
        # Check if optimization is already running
        if OptimizationState().is_running():
            return jsonify({
                'success': False,
                'error': 'An optimization is already running. Please stop or pause the current optimization before starting a new one.'
            })

        data = request.get_json()
        logger.info(f"Received start_optimization request with data keys: {list(data.keys()) if data else 'None'}")

        # The frontend sends actual config objects, not file paths
        ga_config = data.get('ga_config')
        data_config = data.get('data_config')
        test_data_config = data.get('test_data_config')  # Optional test data config

        if not ga_config or not data_config:
            return jsonify({'success': False, 'error': 'Both config objects are required'})

        # Create temporary files for the configs since our optimization function expects file paths
        import tempfile

        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='_ga_config.json', delete=False) as ga_file:
            json.dump(ga_config, ga_file, indent=2)
            ga_config_path = ga_file.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='_data_config.json', delete=False) as data_file:
            json.dump(data_config, data_file, indent=2)
            data_config_path = data_file.name

        # Create test data config file if provided
        test_data_config_path = None
        if test_data_config:
            with tempfile.NamedTemporaryFile(mode='w', suffix='_test_data_config.json', delete=False) as test_data_file:
                json.dump(test_data_config, test_data_file, indent=2)
                test_data_config_path = test_data_file.name

        # Store paths and config data globally so WebSocket handler can access them
        OptimizationState().update({
            'ga_config_path_temp': ga_config_path,
            'data_config_path_temp': data_config_path,
            'test_data_config_path_temp': test_data_config_path,
            'ga_config_data': ga_config,
            'data_config_data': data_config,
            'test_data_config_data': test_data_config
        })

        return jsonify({
            'success': True,
            'message': 'Configuration received. Use WebSocket to start optimization.',
            'ga_config_path': ga_config_path,
            'data_config_path': data_config_path
        })

    except Exception as e:
        logger.error(f"Error preparing optimization: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/stop_optimization', methods=['POST'])
def api_stop_optimization():
    """Stop the optimization via REST API"""
    try:
        from flask import current_app

        # Stop the optimization immediately
        OptimizationState().update({
            'running': False,
            'paused': False
        })

        logger.info("🛑 Stopping optimization threads...")

        # Emit stopping event immediately for real-time UI updates
        try:
            socketio = current_app.extensions.get('socketio')
            if socketio:
                socketio.emit('optimization_stopping', {
                    'generation': OptimizationState().get('current_generation', 0),
                    'total_generations': OptimizationState().get('total_generations', 0)
                })
        except Exception as ws_error:
            logger.warning(f"Could not emit optimization_stopping event: {ws_error}")

        # Try to gracefully stop the main optimization thread
        thread = OptimizationState().get('thread')
        if thread and thread.is_alive():
            logger.info("Waiting for main optimization thread to stop...")
            thread.join(timeout=5)
            if thread.is_alive():
                logger.warning("Optimization thread did not terminate gracefully within timeout")
            else:
                logger.info("✅ Main optimization thread stopped")

        # Try to gracefully stop the heartbeat thread
        heartbeat_thread_obj = OptimizationState().get('heartbeat_thread')
        if heartbeat_thread_obj and heartbeat_thread_obj.is_alive():
            logger.info("💓 Waiting for heartbeat thread to stop...")
            heartbeat_thread_obj.join(timeout=15)  # Wait up to 15 seconds (heartbeat checks every 10s)
            if heartbeat_thread_obj.is_alive():
                logger.warning("💓 Heartbeat thread did not stop gracefully within timeout")
            else:
                logger.info("💓 Heartbeat thread stopped")

        logger.info("✅ Optimization stopped via REST API")

        # Also emit WebSocket event for real-time UI updates
        try:
            socketio = current_app.extensions.get('socketio')
            if socketio:
                socketio.emit('optimization_stopped', {
                    'generation': OptimizationState().get('current_generation', 0),
                    'total_generations': OptimizationState().get('total_generations', 0)
                })
        except Exception as ws_error:
            logger.warning(f"Could not emit WebSocket event: {ws_error}")

        return jsonify({
            'success': True,
            'message': 'Optimization stopped',
            'generation': OptimizationState().get('current_generation', 0),
            'total_generations': OptimizationState().get('total_generations', 0)
        })
    except Exception as e:
        logger.error(f"Error stopping optimization: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@optimizer_bp.route('/api/pause_optimization', methods=['POST'])
def api_pause_optimization():
    """Pause the optimization via REST API"""
    try:
        from flask import current_app

        if OptimizationState().is_running():
            OptimizationState().set('paused', True)
            logger.info("Optimization paused via REST API - will finish current generation")

            # Also emit WebSocket event for real-time UI updates
            try:
                socketio = current_app.extensions.get('socketio')
                if socketio:
                    socketio.emit('optimization_paused', {
                        'generation': OptimizationState().get('current_generation', 0),
                        'total_generations': OptimizationState().get('total_generations', 0)
                    })
            except Exception as ws_error:
                logger.warning(f"Could not emit WebSocket event: {ws_error}")

            return jsonify({
                'success': True,
                'message': 'Optimization paused - will finish current generation',
                'generation': OptimizationState().get('current_generation', 0),
                'total_generations': OptimizationState().get('total_generations', 0)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No optimization is currently running'
            })
    except Exception as e:
        logger.error(f"Error pausing optimization: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@optimizer_bp.route('/api/resume_optimization', methods=['POST'])
def api_resume_optimization():
    """Resume the optimization via REST API"""
    try:
        from flask import current_app

        if OptimizationState().is_running() and OptimizationState().is_paused():
            OptimizationState().set('paused', False)
            logger.info("Optimization resumed via REST API")

            # Also emit WebSocket event for real-time UI updates
            try:
                socketio = current_app.extensions.get('socketio')
                if socketio:
                    socketio.emit('optimization_resumed', {
                        'generation': OptimizationState().get('current_generation', 0),
                        'total_generations': OptimizationState().get('total_generations', 0)
                    })
            except Exception as ws_error:
                logger.warning(f"Could not emit WebSocket event: {ws_error}")

            return jsonify({
                'success': True,
                'message': 'Optimization resumed',
                'generation': OptimizationState().get('current_generation', 0),
                'total_generations': OptimizationState().get('total_generations', 0)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No paused optimization found to resume'
            })
    except Exception as e:
        logger.error(f"Error resuming optimization: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@optimizer_bp.route('/api/save_config', methods=['POST'])
def save_config():
    """Save configuration changes back to files"""
    try:
        data = request.get_json()
        config_type = data.get('config_type')
        config_data = data.get('config_data')

        if not config_type or not config_data:
            return jsonify({'success': False, 'error': 'Missing config_type or config_data'})

        # Create saved_configs directory if it doesn't exist
        saved_configs_dir = Path('saved_configs')
        saved_configs_dir.mkdir(exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{config_type}.json"
        filepath = saved_configs_dir / filename

        # Save the config
        with open(filepath, 'w') as f:
            json.dump(config_data, f, indent=2)

        logger.info(f"Saved {config_type} configuration to {filepath}")

        return jsonify({
            'success': True,
            'message': f'Configuration saved successfully to {filename}',
            'filepath': str(filepath.absolute()),
            'filename': filename
        })

    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/export_optimized_configs')
def export_optimized_configs():
    """Export complete optimization results package like the old system"""
    try:
        print("EXPORT", OptimizationState().get('elites'))
        elites = OptimizationState().get('elites', [])
        best_individuals_log = OptimizationState().get('best_individuals_log', [])
        ga_config_data = OptimizationState().get('ga_config_data', {})
        test_name = OptimizationState().get('test_name', 'optimization')

        if not elites:
            return jsonify({'success': False, 'error': 'No elite configurations available'})

        # Generate timestamp for folder name
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

        # Get number of elites to save from GA hyperparameters (specifically "elites_to_save")
        elites_to_save = 5  # Default
        try:
            # First try from stored ga_config_data
            if ga_config_data and 'ga_hyperparameters' in ga_config_data:
                elites_to_save = ga_config_data.get('ga_hyperparameters', {}).get('elites_to_save', 5)
                logger.info(f"📊 Found elites_to_save in stored config: {elites_to_save}")
            else:
                # Try to read from the config paths used during optimization start
                ga_config_path = OptimizationState().get('ga_config_path')
                if ga_config_path and os.path.exists(ga_config_path):
                    with open(ga_config_path, 'r') as f:
                        ga_config = json.load(f)
                        elites_to_save = ga_config.get('ga_hyperparameters', {}).get('elites_to_save', 5)
                        logger.info(f"📊 Found elites_to_save in config file: {elites_to_save}")
                else:
                    logger.warning(f"📊 Could not find GA config, using default elites_to_save: {elites_to_save}")

        except Exception as e:
            logger.warning(f"Could not read elites_to_save from config, using default {elites_to_save}: {e}")
            pass

        # Limit to available elites
        elites_to_export = min(elites_to_save, len(elites))

        def serialize_object(obj):
            """Convert objects to JSON-serializable format"""
            if hasattr(obj, '__dict__'):
                result = {}
                for key, value in obj.__dict__.items():
                    if hasattr(value, '__dict__'):
                        result[key] = serialize_object(value)
                    elif isinstance(value, list):
                        result[key] = [serialize_object(item) if hasattr(item, '__dict__') else item for item in value]
                    elif isinstance(value, dict):
                        result[key] = {k: serialize_object(v) if hasattr(v, '__dict__') else v for k, v in value.items()}
                    else:
                        result[key] = value
                return result
            else:
                return obj

        # Prepare optimization results package
        optimization_package = {
            'folder_name': f"{timestamp}_{test_name}",
            'timestamp': timestamp,
            'test_name': test_name,
            'files': {}
        }

        # 1. Elite configurations (same format as old system)
        elite_files = {}
        for i in range(elites_to_export):
            elite = elites[i]

            if hasattr(elite, 'individual') and hasattr(elite.individual, 'monitor_configuration'):
                monitor_config = elite.individual.monitor_configuration

                # Extract trade executor config
                elite_trade_executor = {}
                if hasattr(monitor_config, 'trade_executor'):
                    te = monitor_config.trade_executor
                    elite_trade_executor = {
                        'default_position_size': getattr(te, 'default_position_size', 100.0),
                        'stop_loss_pct': getattr(te, 'stop_loss_pct', 0.01),
                        'take_profit_pct': getattr(te, 'take_profit_pct', 0.02),
                        'ignore_bear_signals': getattr(te, 'ignore_bear_signals', False),
                        'trailing_stop_loss': getattr(te, 'trailing_stop_loss', False),
                        'trailing_stop_distance_pct': getattr(te, 'trailing_stop_distance_pct', 0.01),
                        'trailing_stop_activation_pct': getattr(te, 'trailing_stop_activation_pct', 0.005)
                    }
                else:
                    elite_trade_executor = {
                        'default_position_size': 100.0,
                        'stop_loss_pct': 0.01,
                        'take_profit_pct': 0.02,
                        'ignore_bear_signals': False,
                        'trailing_stop_loss': False,
                        'trailing_stop_distance_pct': 0.01,
                        'trailing_stop_activation_pct': 0.005
                    }

                # Convert indicators to proper dict format
                elite_indicators_list = []
                if hasattr(monitor_config, 'indicators') and monitor_config.indicators:
                    for indicator in monitor_config.indicators:
                        indicator_dict = {
                            'name': indicator.name,
                            'type': indicator.type,
                            'indicator_class': indicator.indicator_class,
                            'agg_config': indicator.agg_config,
                            'calc_on_pip': getattr(indicator, 'calc_on_pip', False),
                            'parameters': dict(indicator.parameters) if hasattr(indicator, 'parameters') else {}
                        }
                        elite_indicators_list.append(indicator_dict)

                # Create elite config in the same format as old system
                elite_config = {
                    'monitor': {
                        'name': getattr(monitor_config, 'name', f"Elite {i+1}"),
                        'description': getattr(monitor_config, 'description', f"Elite monitor #{i+1}"),
                        'trade_executor': elite_trade_executor,
                        'enter_long': serialize_object(getattr(monitor_config, 'enter_long', [])),
                        'exit_long': serialize_object(getattr(monitor_config, 'exit_long', [])),
                        'bars': serialize_object(getattr(monitor_config, 'bars', {})),
                    },
                    'indicators': elite_indicators_list
                }

                elite_filename = f"{timestamp}_{test_name}_elite_{i+1}.json"
                elite_files[elite_filename] = elite_config

        # 2. Objectives evolution CSV
        objectives_csv = ""
        if best_individuals_log:
            # Get all unique objective names
            all_objectives = set()
            for entry in best_individuals_log:
                all_objectives.update(entry['metrics'].keys())

            # CSV header
            header = ['Generation'] + sorted(list(all_objectives))
            objectives_csv = ','.join(header) + '\n'

            # CSV data rows
            for entry in best_individuals_log:
                row = [str(entry['generation'])]
                for obj_name in sorted(list(all_objectives)):
                    row.append(str(entry['metrics'].get(obj_name, '')))
                objectives_csv += ','.join(row) + '\n'

        # 3. Original GA config with metadata
        ga_config_with_metadata = dict(ga_config_data)
        ga_config_with_metadata['optimization_metadata'] = {
            'timestamp': timestamp,
            'results_directory': f"{timestamp}_{test_name}",
            'elites_exported': elites_to_export,
            'total_generations': len(best_individuals_log) if best_individuals_log else 0
        }

        # 4. Summary report
        summary_text = f"""Genetic Algorithm Optimization Results
=====================================

Test Name: {test_name}
Timestamp: {timestamp}
Total Generations: {len(best_individuals_log) if best_individuals_log else 0}
Elites Saved: {elites_to_export}

"""

        if best_individuals_log:
            summary_text += "Final Best Metrics:\n"
            final_metrics = best_individuals_log[-1]['metrics']
            for metric_name, metric_value in final_metrics.items():
                summary_text += f"  {metric_name}: {metric_value}\n"
            summary_text += "\n"

        if elites:
            summary_text += "Elite Performance Summary:\n"
            for i in range(elites_to_export):
                elite = elites[i]
                if hasattr(elite, 'fitness_values'):
                    fitness_str = ", ".join([f"{val:.6f}" for val in elite.fitness_values])
                    summary_text += f"  Elite {i+1}: [{fitness_str}]\n"
            summary_text += "\n"

        summary_text += f"Files created:\n"
        for filename in elite_files.keys():
            summary_text += f"  - {filename}\n"
        summary_text += f"  - {timestamp}_{test_name}_objectives.csv\n"
        summary_text += f"  - {timestamp}_{test_name}_original_ga_config.json\n"
        summary_text += f"  - {timestamp}_{test_name}_summary.txt\n"

        # Package everything for frontend
        optimization_package['files'] = elite_files
        optimization_package['objectives_csv'] = objectives_csv
        optimization_package['objectives_filename'] = f"{timestamp}_{test_name}_objectives.csv"
        optimization_package['ga_config'] = ga_config_with_metadata
        optimization_package['ga_config_filename'] = f"{timestamp}_{test_name}_original_ga_config.json"
        optimization_package['summary'] = summary_text
        optimization_package['summary_filename'] = f"{timestamp}_{test_name}_summary.txt"
        optimization_package['elites_count'] = elites_to_export

        logger.info(f"✅ Prepared optimization package with {elites_to_export} elites")

        return jsonify({
            'success': True,
            'package': optimization_package,
            'message': f'Optimization package prepared with {elites_to_export} elite configurations'
        })

    except Exception as e:
        logger.error(f"Error exporting elites: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/get_elite/<int:index>')
def get_elite(index):
    """Get a specific elite by index"""
    try:
        elites = OptimizationState().get('elites', [])

        if not elites:
            return jsonify({'success': False, 'error': 'No elites available'})

        if index >= len(elites):
            return jsonify({'success': False, 'error': 'Elite index out of range'})

        elite = elites[index]

        # Convert to format suitable for replay visualization
        elite_data = {
            'index': index,
            'fitness': getattr(elite, 'fitness', 0),
            'config': elite.to_config() if hasattr(elite, 'to_config') else elite.genotype if hasattr(elite, 'genotype') else {}
        }

        return jsonify({
            'success': True,
            'elite': elite_data
        })

    except Exception as e:
        logger.error(f"Error getting elite {index}: {e}")
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/get_elites')
def get_elites():
    """Get list of elites with summary metrics for selection"""
    try:
        elites = OptimizationState().get('elites', [])

        if not elites:
            return jsonify({'success': False, 'error': 'No elites available'})

        # Build summary data for each elite
        elite_summaries = []
        for i, elite in enumerate(elites):
            # Extract key metrics
            total_pnl = None
            win_rate = None
            total_trades = None

            # IndividualStats stores metrics in additional_data dictionary
            if hasattr(elite, 'additional_data') and elite.additional_data:
                metrics = elite.additional_data

                # Try different metric key names that might be present
                total_pnl = metrics.get('total_pnl') or metrics.get('net_pnl') or metrics.get('pnl')
                winning_trades = metrics.get('winning_trades', 0)
                losing_trades = metrics.get('losing_trades', 0)
                total_trades = metrics.get('total_trades', 0)

                # Calculate win rate if we have trade counts
                if not total_trades and (winning_trades or losing_trades):
                    total_trades = winning_trades + losing_trades

                if total_trades > 0:
                    win_rate = (winning_trades / total_trades) * 100

            # Fallback: Check if metrics stored directly in elite attributes
            elif hasattr(elite, 'performance_metrics'):
                metrics = elite.performance_metrics
                total_pnl = metrics.get('total_pnl', None)
                winning_trades = metrics.get('winning_trades', 0)
                total_trades = metrics.get('total_trades', 0)

                if total_trades > 0:
                    win_rate = (winning_trades / total_trades) * 100

            elite_summaries.append({
                'index': i,
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'total_trades': total_trades
            })

        logger.info(f"✅ Retrieved {len(elite_summaries)} elites with metrics")
        return jsonify({
            'success': True,
            'elites': elite_summaries
        })

    except Exception as e:
        logger.error(f"❌ Error getting elites: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/get_elite_config/<int:index>')
def get_elite_config(index):
    """Get full configuration for a specific elite"""
    try:
        elites = OptimizationState().get('elites', [])

        if not elites:
            return jsonify({'success': False, 'error': 'No elites available'})

        if index >= len(elites):
            return jsonify({'success': False, 'error': 'Elite index out of range'})

        elite = elites[index]

        # Extract monitor configuration from elite
        # IndividualStats has an 'individual' attribute which is an MlfIndividual
        # MlfIndividual has a 'monitor_configuration' attribute
        monitor_config = None

        if hasattr(elite, 'individual') and hasattr(elite.individual, 'monitor_configuration'):
            # MlfIndividual stores MonitorConfiguration (Pydantic BaseModel)
            monitor_config_obj = elite.individual.monitor_configuration

            # Pydantic models have model_dump() or dict() methods
            if hasattr(monitor_config_obj, 'model_dump'):
                # Pydantic v2
                monitor_config = monitor_config_obj.model_dump()
            elif hasattr(monitor_config_obj, 'dict'):
                # Pydantic v1
                monitor_config = monitor_config_obj.dict()
            else:
                # Fallback: Manual conversion
                logger.warning("Using manual conversion for MonitorConfiguration")
                monitor_config = {
                    'name': getattr(monitor_config_obj, 'name', ''),
                    'description': getattr(monitor_config_obj, 'description', ''),
                    'trade_executor': getattr(monitor_config_obj, 'trade_executor', {}),
                    'bars': getattr(monitor_config_obj, 'bars', {}),
                    'enter_long': getattr(monitor_config_obj, 'enter_long', []),
                    'exit_long': getattr(monitor_config_obj, 'exit_long', []),
                    'indicators': []
                }

                # Convert indicators if present
                if hasattr(monitor_config_obj, 'indicators'):
                    for ind in monitor_config_obj.indicators:
                        if hasattr(ind, 'model_dump'):
                            monitor_config['indicators'].append(ind.model_dump())
                        elif hasattr(ind, 'dict'):
                            monitor_config['indicators'].append(ind.dict())
                        else:
                            monitor_config['indicators'].append({
                                'name': getattr(ind, 'name', ''),
                                'indicator_class': getattr(ind, 'indicator_class', ''),
                                'agg_config': getattr(ind, 'agg_config', ''),
                                'parameters': getattr(ind, 'parameters', {}),
                                'ranges': getattr(ind, 'ranges', {})
                            })
        elif hasattr(elite, 'genotype'):
            monitor_config = elite.genotype
        elif hasattr(elite, 'to_config'):
            config = elite.to_config()
            monitor_config = config.get('monitor', {})

        if not monitor_config:
            logger.error(f"❌ Could not extract monitor configuration from elite {index}")
            return jsonify({'success': False, 'error': 'Could not extract monitor configuration'})

        # Log indicator data for debugging
        if 'indicators' in monitor_config and monitor_config['indicators']:
            logger.info(f"📊 Elite {index} has {len(monitor_config['indicators'])} indicators")
            for i, ind in enumerate(monitor_config['indicators']):
                logger.info(f"📊 Indicator {i}: name={ind.get('name')}, class={ind.get('indicator_class')}, agg={ind.get('agg_config')}")

        logger.info(f"✅ Successfully extracted monitor config for elite {index}")
        return jsonify({
            'success': True,
            'monitor_config': monitor_config
        })

    except Exception as e:
        logger.error(f"❌ Error getting elite config {index}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/export_elite/<int:index>')
def export_elite(index):
    """Export a specific elite configuration"""
    try:

        elites = OptimizationState().get('elites', [])

        if not elites:
            return jsonify({'success': False, 'error': 'No elites available'})

        if index >= len(elites):
            return jsonify({'success': False, 'error': 'Elite index out of range'})

        elite = elites[index]

        # Convert to configuration format
        if hasattr(elite, 'to_config'):
            elite_config = elite.to_config()
        else:
            elite_config = {
                'test_name': f'Elite_{index + 1}_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                'monitor': elite.genotype if hasattr(elite, 'genotype') else {},
                'elite_fitness': getattr(elite, 'fitness', 0)
            }

        return jsonify({
            'success': True,
            'config': elite_config
        })

    except Exception as e:
        logger.error(f"Error exporting elite {index}: {e}")
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/get_parameter_histogram', methods=['POST'])
def get_parameter_histogram():
    """
    Get histogram data for a specific parameter

    Request JSON:
        - parameter_name: Name of the parameter to get histogram for
        - num_bins: Number of bins for continuous parameters (optional, default: 20)

    Returns:
        JSON with histogram bins, statistics, and metadata
    """
    try:
        data = request.get_json()
        param_name = data.get('parameter_name')
        num_bins = data.get('num_bins', 20)

        if not param_name:
            return jsonify({'success': False, 'error': 'parameter_name is required'})

        # Get parameter collector from optimization state
        parameter_collector = OptimizationState().get('parameter_collector')
        if not parameter_collector:
            return jsonify({'success': False, 'error': 'No parameter data available - optimization may not have started yet'})

        # Generate histogram data for requested parameter
        histogram_data = parameter_collector.get_parameter_histogram_data(param_name, num_bins)

        if not histogram_data:
            return jsonify({'success': False, 'error': f'Parameter "{param_name}" not found or has no data'})

        pop_count = histogram_data['population']['total_values']
        elite_count = histogram_data['elites']['total_values'] if histogram_data['elites'] else 0
        logger.info(f"📊 Generated histogram for parameter '{param_name}' with {pop_count} population + {elite_count} elite values")

        return jsonify({
            'success': True,
            'histogram': histogram_data
        })

    except Exception as e:
        logger.error(f"❌ Error generating parameter histogram: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/get_parameter_evolution', methods=['POST'])
def get_parameter_evolution():
    """
    Get parameter evolution data across all generations

    Request JSON:
        - parameter_name: Name of the parameter to get evolution data for

    Returns:
        JSON with time-series data for mean, std, min, max, median across generations,
        plus convergence detection and jump identification
    """
    try:
        data = request.get_json()
        param_name = data.get('parameter_name')

        if not param_name:
            return jsonify({'success': False, 'error': 'parameter_name is required'})

        # Get parameter collector from optimization state
        parameter_collector = OptimizationState().get('parameter_collector')
        if not parameter_collector:
            return jsonify({'success': False, 'error': 'No parameter data available - optimization may not have started yet'})

        # Get evolution data for requested parameter
        evolution_data = parameter_collector.get_parameter_evolution_data(param_name)

        if not evolution_data:
            return jsonify({'success': False, 'error': f'Parameter "{param_name}" not found or has no evolution data'})

        gen_count = len(evolution_data['generations'])
        convergence = "✅ Converged" if evolution_data['convergence_detected'] else "🔄 Evolving"
        jump_count = len(evolution_data['jumps'])
        logger.info(f"📈 Generated evolution data for parameter '{param_name}' across {gen_count} generations ({convergence}, {jump_count} jumps)")

        return jsonify({
            'success': True,
            'evolution': evolution_data
        })

    except Exception as e:
        logger.error(f"❌ Error generating parameter evolution data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


# =============================================================================
# WebSocket Event Handlers
# These need to be registered in the main app.py file with the socketio instance
# =============================================================================
