"""
Genetic Algorithm Core Execution
Main GA optimization logic with WebSocket updates and real-time monitoring

MEMORY OPTIMIZATION: Includes periodic garbage collection and memory-efficient
data handling to prevent memory bloat during long optimization runs.
"""

import os
import json
import time
import threading
import tempfile
import gc
from datetime import datetime
from pathlib import Path

from optimization.genetic_optimizer.apps.utils.mlf_optimizer_config import MlfOptimizerConfig
from optimization.genetic_optimizer.support.parameter_collector import ParameterCollector
from portfolios.portfolio_tool import TradeReason
from candle_aggregator.csa_container import CSAContainer
from optimization.calculators.bt_data_streamer import BacktestDataStreamer
from mlf_utils.log_manager import LogManager
from mlf_utils.timezone_utils import now_et, isoformat_et, format_et

from .elite_selection import select_winning_population
from .chart_generation import generate_optimizer_chart_data

logger = LogManager().get_logger("OptimizerVisualization")


def heartbeat_thread(socketio, opt_state):
    """Background thread to send heartbeats during optimization"""
    logger.info("💓 Heartbeat thread started")

    while opt_state.is_running():
        try:
            # Send heartbeat with current optimization state
            heartbeat_data = {
                'timestamp': isoformat_et(now_et()),
                'optimization_state': {
                    'running': opt_state.is_running(),
                    'paused': opt_state.is_paused(),
                    'current_generation': opt_state.get('current_generation', 0),
                    'total_generations': opt_state.get('total_generations', 0),
                    'test_name': opt_state.get('test_name', 'Unknown')
                }
            }

            socketio.emit('heartbeat', heartbeat_data)
            logger.debug(f"💓 Heartbeat sent: gen {heartbeat_data['optimization_state']['current_generation']}")

        except Exception as e:
            logger.error(f"❌ Error sending heartbeat: {e}")

        # Send heartbeat every 10 seconds
        time.sleep(10)

    logger.info("💓 Heartbeat thread stopped")


def run_genetic_algorithm_threaded_with_new_indicators(ga_config_path: str, data_config_path: str,
                                                       socketio, opt_state, test_data_config_path: str = None):
    """
    Run the genetic algorithm optimization with real-time WebSocket updates

    This is the main GA execution function that orchestrates:
    - Configuration loading and validation
    - Genetic algorithm initialization
    - Generation-by-generation optimization with WebSocket updates
    - Elite selection and test data evaluation
    - Progress tracking and state management

    Args:
        ga_config_path: Path to GA configuration JSON file
        data_config_path: Path to data configuration JSON file
        socketio: Flask-SocketIO instance for real-time updates
        opt_state: OptimizationState singleton for thread-safe state management
        test_data_config_path: Optional path to test data configuration
    """
    heartbeat_worker = None
    try:
        logger.info("🚀 Starting threaded optimization with NEW indicator system")

        # Load configuration
        with open(ga_config_path) as f:
            config_data = json.load(f)

        # Load data configuration to verify ticker
        with open(data_config_path) as f:
            data_config = json.load(f)

        current_ticker = data_config.get('ticker', 'UNKNOWN')
        logger.info(f"🎯 Loading optimization for ticker: {current_ticker}")
        logger.info(f"   Data config path: {data_config_path}")
        logger.info(f"   Date range: {data_config.get('start_date')} to {data_config.get('end_date')}")

        # Load test data configuration if provided
        test_data_config = None
        if test_data_config_path and os.path.exists(test_data_config_path):
            with open(test_data_config_path) as f:
                test_data_config = json.load(f)
            logger.info(f"🧪 Test data config loaded for ticker: {test_data_config.get('ticker', 'UNKNOWN')}")
            logger.info(f"   Test date range: {test_data_config.get('start_date')} to {test_data_config.get('end_date')}")

        test_name = config_data.get('test_name', config_data.get('monitor', {}).get('name', 'NoNAME'))
        opt_state.set('test_name', test_name)
        opt_state.set('ga_config_path', ga_config_path)

        # Process indicators using old system for now (new system disabled)
        processed_indicators = []
        logger.info("Using NEW indicator system for compatibility")

        # Create optimizer config with processed indicators
        io = MlfOptimizerConfig.from_json(config_data, data_config_path)
        genetic_algorithm = io.create_project()

        # Initialize parameter collector for histogram tracking
        parameter_collector = ParameterCollector()

        # Store instances for state management using thread-safe methods
        opt_state.update({
            'ga_instance': genetic_algorithm,
            'io_instance': io,
            'total_generations': genetic_algorithm.number_of_generations,
            'current_generation': 0,
            'best_individuals_log': [],
            'processed_indicators': processed_indicators,
            'parameter_collector': parameter_collector
        })

        logger.info(f"   Test: {test_name}")
        logger.info(f"   Generations: {genetic_algorithm.number_of_generations}")
        logger.info(f"   Population Size: {genetic_algorithm.population_size}")
        logger.info(f"   Elitist Size: {genetic_algorithm.elitist_size}")
        logger.info(f"   New Indicators: {len(processed_indicators)}")

        # Store timestamp for later use (ET for user-friendly file naming)
        optimization_timestamp = now_et().strftime("%Y-%m-%d_%H%M%S")
        opt_state.set('timestamp', optimization_timestamp)

        # Start heartbeat thread
        heartbeat_worker = threading.Thread(
            target=heartbeat_thread,
            args=(socketio, opt_state),
            daemon=True
        )
        heartbeat_worker.start()
        opt_state.set('heartbeat_thread', heartbeat_worker)
        logger.info("💓 Heartbeat thread started")

        # Emit initial status
        socketio.emit('optimization_started', {
            'test_name': test_name,
            'total_generations': genetic_algorithm.number_of_generations,
            'population_size': genetic_algorithm.population_size,
            'timestamp': optimization_timestamp,
            'new_indicators_count': len(processed_indicators)
        })

        # Run optimization with generation-by-generation updates
        for observer, statsobserver in genetic_algorithm.run_ga_iterations(1):
            if not observer.success:
                print("NOT SUCCESSFUL... trying again with next epoch")
                continue

            # Fix generation numbering first - stats returns 0-based, we want 1-based display
            current_gen = observer.iteration + 1  # Convert from 0-based to 1-based

            # Check if stopped using thread-safe methods
            if not opt_state.is_running():
                logger.info(f"🛑 Optimization stopped by user at generation {current_gen}")
                socketio.emit('optimization_stopped', {
                    'generation': current_gen,
                    'total_generations': genetic_algorithm.number_of_generations
                })
                break

            # Wait while paused using thread-safe methods - pause after finishing current generation
            if opt_state.is_paused() and opt_state.is_running():
                logger.info(f"⏸️ Optimization paused after completing generation {current_gen}")
                while opt_state.is_paused() and opt_state.is_running():
                    time.sleep(0.1)

                if opt_state.is_running():  # If still running after unpause
                    logger.info(f"▶️ Optimization resumed at generation {current_gen}")

            metrics = statsobserver.best_metric_iteration

            elites = select_winning_population(genetic_algorithm.elitist_size, observer.fronts)
            best_individual = elites[0].individual

            # Collect parameters from entire population (all fronts) for histogram visualization
            # Clear previous generation data to show only current epoch
            parameter_collector.clear_generation_data()
            # Extract all individuals from all Pareto fronts
            full_population = [individual for front in observer.fronts.values() for individual in front]
            # Pass both full population and elites for two-series histogram
            parameter_collector.collect_generation_parameters(current_gen, full_population, elites=elites)

            opt_state.update({
                'current_generation': current_gen,
                'last_best_individual': best_individual,
                'elites': elites
            })

            # MEMORY OPTIMIZATION: Trim elites to prevent unbounded growth
            # Keep only top 20 elites to reduce memory footprint
            opt_state.trim_elites(max_elites=20)

            # Save elites every epoch if flag is enabled
            if config_data.get('ga_hyperparameters', {}).get('save_elites_every_epoch', False):
                _save_elites_for_epoch(config_data, elites, test_name, optimization_timestamp, current_gen)

            # Log the best individual for this generation
            objectives = [o.name for o in io.fitness_calculator.objectives]
            fitness_log = {
                'generation': current_gen,
                'metrics': dict(zip(objectives, metrics))
            }
            current_log = opt_state.get('best_individuals_log', [])
            current_log.append(fitness_log)
            opt_state.set('best_individuals_log', current_log)

            # Log progress
            metric_out = [f"{obj}={metric:.4f}" for obj, metric in zip(objectives, metrics)]
            out_str = f"{test_name}, {current_gen}/{genetic_algorithm.number_of_generations}, {metric_out}"
            logger.info(out_str)

            # Get chart data for optimizer visualization
            try:
                # Get objective names dynamically
                objectives = [o.name for o in io.fitness_calculator.objectives]

                # Generate optimizer-specific chart data
                optimizer_charts = generate_optimizer_chart_data(
                    best_individual, elites, io, data_config_path,
                    opt_state.get('best_individuals_log', []), objectives
                )

                # Convert numpy arrays to regular Python lists for JSON serialization
                elite_objectives = [e.fitness_values.tolist() for e in elites]

                # Get parameter list for histogram dropdown
                parameter_list = parameter_collector.get_parameter_list()

                # Evaluate elites on test data if test config is provided
                test_evaluations = _evaluate_elites_on_test_data(
                    test_data_config, config_data, elites, io, current_gen, opt_state
                ) if test_data_config else []

                socketio.emit('generation_complete', {
                    'generation': current_gen,
                    'total_generations': genetic_algorithm.number_of_generations,
                    'fitness_metrics': dict(zip(objectives, metrics)),
                    'chart_data': optimizer_charts,
                    'best_individuals_log': opt_state.get('best_individuals_log', []),
                    'elite_objective_values': elite_objectives,
                    'objective_names': objectives,
                    'progress': {
                        'current_generation': current_gen,
                        'total_generations': genetic_algorithm.number_of_generations,
                        'completed': False
                    },
                    'optimizer_charts': optimizer_charts,  # Specifically for optimizer frontend
                    'parameter_list': parameter_list,  # For parameter histogram dropdown
                    'test_evaluations': test_evaluations  # Test data evaluation results
                })

            except Exception as e:
                logger.error(f"Error generating chart data: {e}")
                socketio.emit('optimization_error', {'error': str(e)})
                break

            # MEMORY OPTIMIZATION: Periodic garbage collection every 5 generations
            # to prevent memory accumulation during long optimization runs
            if current_gen % 5 == 0:
                gc.collect()

        # Optimization completed
        if opt_state.is_running():
            logger.info("⏱️  Optimization completed successfully with NEW indicator system")
            # Auto-saving disabled - user will manually save best elites via UI button
            logger.info("✅ Optimization completed - elites available for manual saving via UI")
            # Emit completion event without automatic saving
            socketio.emit('optimization_complete', {
                'total_generations': opt_state.get('current_generation'),
                'best_individuals_log': opt_state.get('best_individuals_log', []),
                'manual_save_available': True
            })

    except Exception as e:
        logger.error(f"❌ Error in threaded optimization: {e}")
        import traceback
        traceback.print_exc()
        socketio.emit('optimization_error', {'error': str(e)})

    finally:
        # Stop the heartbeat thread first
        logger.info("🛑 Stopping heartbeat thread...")
        opt_state.update({
            'running': False,
            'paused': False
        })

        # Wait for heartbeat thread to stop (it checks is_running() every 10 seconds)
        heartbeat_thread_ref = opt_state.get('heartbeat_thread')
        if heartbeat_thread_ref and heartbeat_thread_ref.is_alive():
            logger.info("💓 Waiting for heartbeat thread to stop...")
            heartbeat_thread_ref.join(timeout=15)  # Wait up to 15 seconds (heartbeat checks every 10s)
            if heartbeat_thread_ref.is_alive():
                logger.warning("💓 Heartbeat thread did not stop gracefully within timeout")
            else:
                logger.info("💓 Heartbeat thread stopped cleanly")

        # Clean up temporary files if they exist
        try:
            ga_config_path_temp = opt_state.get('ga_config_path_temp')
            data_config_path_temp = opt_state.get('data_config_path_temp')

            if ga_config_path_temp and Path(ga_config_path_temp).exists():
                Path(ga_config_path_temp).unlink()

            if data_config_path_temp and Path(data_config_path_temp).exists():
                Path(data_config_path_temp).unlink()

        except Exception:
            pass

        # Reset optimization state
        opt_state.update({
            'running': False,
            'paused': False,
            'thread': None,
            'heartbeat_thread': None,
            'ga_config_path_temp': None,
            'data_config_path_temp': None
        })


def _save_elites_for_epoch(config_data, elites, test_name, optimization_timestamp, current_gen):
    """Helper function to save elite configurations for a specific epoch"""
    try:
        # Create output directory: outputs/monitor_name_timestamp/
        output_dir = Path('outputs') / f"{test_name}_{optimization_timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get number of elites to save
        elites_to_save = config_data.get('ga_hyperparameters', {}).get('elites_to_save', 5)
        num_elites_to_save = min(elites_to_save, len(elites))

        # Helper function to serialize complex objects
        def serialize_object(obj):
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

        # Save each elite configuration
        for elite_idx in range(num_elites_to_save):
            elite = elites[elite_idx]
            if not hasattr(elite, 'individual') or not hasattr(elite.individual, 'monitor_configuration'):
                logger.warning(f"Elite #{elite_idx+1} missing individual.monitor_configuration, skipping")
                continue

            elite_config = elite.individual.monitor_configuration

            # Extract trade executor config
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

            # Convert indicators to proper dict format
            elite_indicators_list = []
            if hasattr(elite_config, 'indicators') and elite_config.indicators:
                for indicator in elite_config.indicators:
                    indicator_dict = {
                        'name': indicator.name,
                        'type': indicator.type,
                        'indicator_class': indicator.indicator_class,
                        'agg_config': indicator.agg_config,
                        'calc_on_pip': getattr(indicator, 'calc_on_pip', False),
                        'parameters': dict(indicator.parameters) if hasattr(indicator, 'parameters') else {}
                    }
                    elite_indicators_list.append(indicator_dict)

            # Create elite config with serialized enter_long, exit_long, and bars
            elite_dict = {
                'monitor': {
                    'name': getattr(elite_config, 'name', f"Elite {elite_idx+1}"),
                    'description': getattr(elite_config, 'description', f"Elite monitor #{elite_idx+1} - Epoch {current_gen}"),
                    'trade_executor': elite_trade_executor,
                    'enter_long': serialize_object(getattr(elite_config, 'enter_long', [])),
                    'exit_long': serialize_object(getattr(elite_config, 'exit_long', [])),
                    'bars': serialize_object(getattr(elite_config, 'bars', {})),
                },
                'indicators': elite_indicators_list,
                'epoch': current_gen,
                'fitness_values': elite.fitness_values.tolist() if hasattr(elite, 'fitness_values') else []
            }

            # Save to file: outputs/monitor_name_timestamp/epoch{gen}_elite{idx}.json
            elite_filename = f"epoch{current_gen}_elite{elite_idx+1}.json"
            elite_filepath = output_dir / elite_filename

            with open(elite_filepath, 'w') as f:
                json.dump(elite_dict, f, indent=2)

            logger.info(f"💾 Saved elite {elite_idx+1} for epoch {current_gen}: {elite_filepath}")

        logger.info(f"✅ Saved {num_elites_to_save} elites for epoch {current_gen} to {output_dir}")

    except Exception as save_error:
        logger.error(f"❌ Error saving elites for epoch {current_gen}: {save_error}")
        import traceback
        traceback.print_exc()


def _evaluate_elites_on_test_data(test_data_config, config_data, elites, io, current_gen, opt_state):
    """Helper function to evaluate elite individuals on test data"""
    test_evaluations = []
    try:
        # Get number of elites to save from GA hyperparameters
        elites_to_save = config_data.get('ga_hyperparameters', {}).get('elites_to_save', 5)
        num_elites_to_evaluate = min(elites_to_save, len(elites))

        logger.info(f"🧪 Evaluating top {num_elites_to_evaluate} elites (out of {len(elites)}) on test data for generation {current_gen}")

        # Create a temporary test data config file for evaluation
        with tempfile.NamedTemporaryFile(mode='w', suffix='_test_eval.json', delete=False) as test_file:
            json.dump(test_data_config, test_file, indent=2)
            temp_test_path = test_file.name

        try:
            # Get aggregator configurations from monitor config
            aggregator_list = list(io.monitor_config.get_aggregator_configs().keys())

            # Create CSA container for test data
            test_csa = CSAContainer(test_data_config, aggregator_list)

            # Create and initialize BacktestDataStreamer with test data
            test_streamer = BacktestDataStreamer()
            test_streamer.initialize(test_csa.get_aggregators(), test_data_config, io.monitor_config)

            # Only evaluate the top elites that will be saved
            elites_to_test = elites[:num_elites_to_evaluate]

            for elite_idx, elite_stats in enumerate(elites_to_test):
                try:
                    # Evaluate elite on training data (already calculated)
                    train_pnl = getattr(elite_stats, 'total_pnl', None)
                    train_trades = getattr(elite_stats, 'number_of_trades', 0)
                    train_winning = getattr(elite_stats, 'number_of_winning_trades', 0)
                    train_win_rate = (train_winning / train_trades * 100) if train_trades > 0 else 0

                    # Evaluate elite on test data using the backtest streamer
                    test_streamer.replace_monitor_config(elite_stats.individual.monitor_configuration)
                    test_portfolio = test_streamer.run()

                    # Extract test metrics from portfolio trade history
                    # Calculate P&L from entry/exit pairs
                    cumulative_pnl = 0.0
                    trade_pairs = []

                    for trade in test_portfolio.trade_history:
                        is_entry = trade.reason.is_entry()
                        is_exit = trade.reason.is_exit()

                        if is_entry:
                            trade_pairs.append({'entry': trade, 'exit': None})
                        elif is_exit and trade_pairs:
                            for pair in reversed(trade_pairs):
                                if pair['exit'] is None:
                                    pair['exit'] = trade
                                    entry_price = pair['entry'].price
                                    exit_price = trade.price
                                    trade_pnl = ((exit_price - entry_price) / entry_price) * 100.0
                                    cumulative_pnl += trade_pnl
                                    break

                    # Count completed trades
                    completed_pairs = [p for p in trade_pairs if p['exit'] is not None]
                    test_pnl = cumulative_pnl
                    test_trades = len(completed_pairs)

                    # Count winning trades
                    test_winning = 0
                    for pair in completed_pairs:
                        entry_price = pair['entry'].price
                        exit_price = pair['exit'].price
                        if exit_price > entry_price:
                            test_winning += 1

                    test_win_rate = (test_winning / test_trades * 100) if test_trades > 0 else 0

                    # Calculate overfitting score (difference between train and test performance)
                    overfitting_score = train_pnl - test_pnl if (train_pnl is not None and test_pnl is not None) else None

                    test_evaluations.append({
                        'generation': current_gen,
                        'elite_index': elite_idx,
                        'train_pnl': train_pnl,
                        'test_pnl': test_pnl,
                        'train_trades': train_trades,
                        'test_trades': test_trades,
                        'train_win_rate': train_win_rate,
                        'test_win_rate': test_win_rate,
                        'overfitting_score': overfitting_score
                    })

                    logger.info(f"   Elite {elite_idx}: Train P&L={train_pnl:.2f}%, Test P&L={test_pnl:.2f}%, Overfitting={overfitting_score:.2f}%")

                except Exception as elite_eval_error:
                    logger.warning(f"Error evaluating elite {elite_idx} on test data: {elite_eval_error}")
                    import traceback
                    traceback.print_exc()

            # Store test evaluations in state
            current_test_evals = opt_state.get('test_evaluations', [])
            current_test_evals.extend(test_evaluations)
            opt_state.set('test_evaluations', current_test_evals)

            logger.info(f"✅ Evaluated {len(test_evaluations)} elites on test data")

        finally:
            # Clean up temporary test config file
            if os.path.exists(temp_test_path):
                os.unlink(temp_test_path)

    except Exception as test_eval_error:
        logger.error(f"Error during test data evaluation: {test_eval_error}")
        import traceback
        traceback.print_exc()

    return test_evaluations
