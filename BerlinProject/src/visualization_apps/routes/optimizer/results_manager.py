"""
Optimization Results Management
Saving and exporting optimization results with elite configurations
"""

import json
from pathlib import Path
from datetime import datetime
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("OptimizerVisualization")


def save_optimization_results_with_new_indicators(best_individuals_log, best_individual, elites, ga_config_path, test_name, timestamp=None, processed_indicators=None):
    """
    Save optimization results including NEW indicator information

    Creates a results directory with:
    - Elite monitor configurations (JSON files)
    - New indicators information (if applicable)
    - Optimization metadata

    Args:
        best_individuals_log: Log of best individuals per generation
        best_individual: The best individual from optimization
        elites: List of elite individuals to save
        ga_config_path: Path to GA configuration file
        test_name: Name of the optimization test
        timestamp: Optional timestamp (generated if not provided)
        processed_indicators: Optional list of processed indicators

    Returns:
        Dictionary with results directory path and files created
    """
    logger.info("💾 Saving optimization results with NEW indicator system...")

    if not timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    results_dir = Path('results') / f"{timestamp}_{test_name}"
    results_dir.mkdir(parents=True, exist_ok=True)

    results_info = {
        'results_dir': str(results_dir),
        'timestamp': timestamp,
        'files_created': []
    }

    try:
        # Save information about new indicators used
        if processed_indicators:
            indicators_info_file = results_dir / f"{timestamp}_{test_name}_new_indicators_used.json"

            indicators_info = {
                'count': len(processed_indicators),
                'indicators': []
            }

            for indicator in processed_indicators:
                indicators_info['indicators'].append({
                    'name': indicator.name,
                    'display_name': getattr(indicator, 'display_name', indicator.name),
                    'parameters': indicator.config.parameters,
                    'enabled': indicator.config.enabled
                })

            with open(indicators_info_file, 'w') as f:
                json.dump(indicators_info, f, indent=2)

            results_info['files_created'].append(str(indicators_info_file))
            logger.info(f"✅ Saved new indicators info: {indicators_info_file}")

        # Save other results following the same pattern as original
        # (elite monitors, objectives CSV, etc.)

        # Load GA config to get elites_to_save parameter
        elites_to_save = 5  # Default value
        try:
            with open(ga_config_path) as f:
                ga_config = json.load(f)
                elites_to_save = ga_config.get('ga_hyperparameters', {}).get('elites_to_save', 5)
        except Exception as e:
            logger.warning(f"Could not read elites_to_save from GA config: {e}")

        if elites and len(elites) >= 1 and elites_to_save >= 1:
            # Save elite monitors with NEW indicator information
            elites_to_process = elites[:elites_to_save]
            logger.info(f"💫 Saving top {len(elites_to_process)} elite monitors with NEW indicators...")

            for i, elite in enumerate(elites_to_process):
                if not hasattr(elite, 'individual') or not hasattr(elite.individual, 'monitor_configuration'):
                    logger.warning(f"Elite #{i+1} missing individual.monitor_configuration, skipping")
                    continue

                elite_file = results_dir / f"{timestamp}_{test_name}_elite_{i+1}.json"
                elite_config = elite.individual.monitor_configuration

                # Extract and save elite configuration with NEW indicator format
                elite_trade_executor = {}
                if hasattr(elite_config, 'trade_executor'):
                    te = elite_config.trade_executor
                    elite_trade_executor = {
                        'default_position_size': getattr(te, 'default_position_size', 100.0),
                        'stop_loss_pct': getattr(te, 'stop_loss_pct', 0.01),
                        'take_profit_pct': getattr(te, 'take_profit_pct', 0.02),
                        'ignore_bear_signals': getattr(te, 'ignore_bear_signals', False),
                        'trailing_stop_loss': getattr(te, 'trailing_stop_loss', False),
                        'trailing_stop_distance_pct': getattr(te, 'trailing_stop_distance_pct', 0.01),
                        'trailing_stop_activation_pct': getattr(te, 'trailing_stop_activation_pct', 0.005)
                    }

                # Convert elite indicators to new format
                elite_indicators_list = []
                if hasattr(elite_config, 'indicators') and elite_config.indicators:
                    for indicator in elite_config.indicators:
                        indicator_dict = {
                            'name': getattr(indicator, 'name', 'unknown'),
                            'display_name': getattr(indicator, 'display_name', getattr(indicator, 'name', 'unknown')),
                            'type': getattr(indicator, 'type', 'unknown'),
                            'indicator_class': getattr(indicator, 'indicator_class', 'unknown'),
                            'agg_config': getattr(indicator, 'agg_config', '1m-normal'),
                            'calc_on_pip': getattr(indicator, 'calc_on_pip', False),
                            'parameters': dict(getattr(indicator, 'parameters', {})),
                            'enabled': getattr(indicator, 'enabled', True),
                            'new_system': True  # Mark as using new system
                        }
                        elite_indicators_list.append(indicator_dict)

                elite_dict = {
                    'monitor': {
                        'name': getattr(elite_config, 'name', f"Elite {i+1}"),
                        'description': getattr(elite_config, 'description', f"Elite monitor #{i+1} with NEW indicators"),
                        'trade_executor': elite_trade_executor,
                        'enter_long': getattr(elite_config, 'enter_long', []),
                        'exit_long': getattr(elite_config, 'exit_long', []),
                        'bars': getattr(elite_config, 'bars', {}),
                    },
                    'indicators': elite_indicators_list,
                    'system_version': 'new_indicator_system_v1.0',
                    'fitness_values': elite.fitness_values.tolist() if hasattr(elite, 'fitness_values') else []
                }

                try:
                    with open(elite_file, 'w') as f:
                        json.dump(elite_dict, f, indent=2)

                    results_info['files_created'].append(str(elite_file))
                    logger.info(f"✅ Saved NEW elite #{i+1} config: {elite_file}")
                except Exception as save_error:
                    logger.error(f"❌ Failed to save elite #{i+1}: {save_error}")
                    continue

        logger.info(f"💾 Successfully saved optimization results with NEW indicator system")

    except Exception as e:
        logger.error(f"❌ Error saving results: {e}")
        raise

    return results_info
