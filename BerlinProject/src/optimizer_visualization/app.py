import os
import sys
import json
import logging
import threading
import time
import csv
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..'))

from optimization.genetic_optimizer.apps.utils.mlf_optimizer_config import MlfOptimizerConfig
from optimization.calculators.yahoo_finance_historical import YahooFinanceHistorical
from portfolios.portfolio_tool import TradeReason

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('GAVisualizationApp')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ga-viz-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global optimization state
optimization_state = {
    'running': False,
    'paused': False,
    'thread': None,
    'ga_instance': None,
    'io_instance': None,
    'current_generation': 0,
    'total_generations': 0,
    'best_individuals_log': [],
    'last_best_individual': None,
    'test_name': None
}


def run_genetic_algorithm_threaded(ga_config_path: str, data_config_path: str):
    """Run the genetic algorithm optimization in a separate thread with websocket updates"""
    global optimization_state

    try:
        logger.info("🚀 Starting threaded optimization")

        # Load configuration
        with open(ga_config_path) as f:
            config_data = json.load(f)

        test_name = config_data.get('test_name', config_data.get('monitor', {}).get('name', 'NoNAME'))
        optimization_state['test_name'] = test_name

        # Create optimizer config
        io = MlfOptimizerConfig.from_json(config_data, data_config_path)
        genetic_algorithm = io.create_project()

        # Store instances for state management
        optimization_state['ga_instance'] = genetic_algorithm
        optimization_state['io_instance'] = io
        optimization_state['total_generations'] = genetic_algorithm.number_of_generations
        optimization_state['current_generation'] = 0
        optimization_state['best_individuals_log'] = []

        logger.info(f"   Test: {test_name}")
        logger.info(f"   Generations: {genetic_algorithm.number_of_generations}")
        logger.info(f"   Population Size: {genetic_algorithm.population_size}")
        logger.info(f"   Elitist Size: {genetic_algorithm.elitist_size}")

        # Store timestamp for later use
        optimization_timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        optimization_state['timestamp'] = optimization_timestamp

        # Emit initial status
        socketio.emit('optimization_started', {
            'test_name': test_name,
            'total_generations': genetic_algorithm.number_of_generations,
            'population_size': genetic_algorithm.population_size,
            'timestamp': optimization_timestamp  # Send same timestamp to frontend
        })

        # Run optimization with generation-by-generation updates
        for stats in genetic_algorithm.run_ga_iterations(1):
            # Check if stopped
            if not optimization_state['running']:
                logger.info("Optimization stopped by user")
                break

            # Wait while paused
            while optimization_state['paused'] and optimization_state['running']:
                time.sleep(0.1)

            # Check if stopped during pause
            if not optimization_state['running']:
                logger.info("Optimization stopped during pause")
                break

            # Fix generation numbering - stats returns 0-based, we want 1-based display
            current_gen = stats[0].iteration + 1  # Convert from 0-based to 1-based
            best_individual = stats[1].best_front[0].individual
            metrics = stats[1].best_metric_iteration

            # Update state
            optimization_state['current_generation'] = current_gen
            optimization_state['last_best_individual'] = best_individual

            # Log best individual for this generation
            objectives = [o.name for o in io.fitness_calculator.objectives]
            fitness_log = {
                'generation': current_gen,
                'metrics': dict(zip(objectives, metrics))
            }
            optimization_state['best_individuals_log'].append(fitness_log)

            # Log progress
            metric_out = [f"{obj}={metric:.4f}" for obj, metric in zip(objectives, metrics)]
            out_str = f"{test_name}, {current_gen}/{genetic_algorithm.number_of_generations}, {metric_out}"
            logger.info(out_str)

            # Get chart data for this best individual (still needed for metrics calculation)
            try:
                chart_data = generate_chart_data_for_individual(best_individual, io, data_config_path)

                # Emit update to frontend
                socketio.emit('generation_complete', {
                    'generation': current_gen,
                    'total_generations': genetic_algorithm.number_of_generations,
                    'fitness_metrics': dict(zip(objectives, metrics)),
                    'chart_data': chart_data,
                    'best_individuals_log': optimization_state['best_individuals_log']
                })

            except Exception as e:
                logger.error(f"Error generating chart data: {e}")
                socketio.emit('optimization_error', {'error': str(e)})
                break

        # Optimization completed
        if optimization_state['running']:
            logger.info("⏱️  Optimization completed successfully")

            # Save results to files
            try:
                # Use the same timestamp that was sent to frontend
                optimization_timestamp = None
                # Try to extract timestamp from the initial emit (we'll need to store it)
                # For now, create it fresh but we'll sync this properly

                results_info = save_optimization_results(
                    optimization_state['best_individuals_log'],
                    optimization_state['last_best_individual'],
                    ga_config_path,
                    test_name,
                    optimization_state.get('timestamp')  # Pass stored timestamp
                )

                socketio.emit('optimization_complete', {
                    'total_generations': optimization_state['current_generation'],
                    'best_individuals_log': optimization_state['best_individuals_log'],
                    'results_saved': results_info
                })

                logger.info(f"📁 Results saved to: {results_info['results_dir']}")

            except Exception as save_error:
                logger.error(f"❌ Error saving results: {save_error}")
                socketio.emit('optimization_complete', {
                    'total_generations': optimization_state['current_generation'],
                    'best_individuals_log': optimization_state['best_individuals_log'],
                    'results_saved': None,
                    'save_error': str(save_error)
                })

    except Exception as e:
        logger.error(f"❌ Error in threaded optimization: {e}")
        import traceback
        traceback.print_exc()
        socketio.emit('optimization_error', {'error': str(e)})

    finally:
        # Reset state
        optimization_state['running'] = False
        optimization_state['paused'] = False
        optimization_state['thread'] = None


def generate_chart_data_for_individual(best_individual, io, data_config_path):
    """Generate chart data for the given best individual"""
    # Load candle data
    candlestick_data, data_config = load_raw_candle_data(data_config_path, io)

    # IMPORTANT: Run backtest for this specific individual to get trades and bar scores
    backtest_streamer = io.fitness_calculator.backtest_streamer
    backtest_streamer.replace_monitor_config(best_individual.monitor_configuration)

    # Calculate indicators and bar scores for this individual's configuration
    from optimization.calculators.indicator_processor_historical_new import IndicatorProcessorHistoricalNew

    indicator_processor = IndicatorProcessorHistoricalNew(best_individual.monitor_configuration)
    indicator_history, raw_indicator_history, bar_score_history_dict = (
        indicator_processor.calculate_indicators(backtest_streamer.aggregators)
    )

    # Store the bar score history for later access
    backtest_streamer.bar_score_history_dict = bar_score_history_dict

    # Run the backtest to get trades
    portfolio = backtest_streamer.run()

    # Extract trade history and P&L from the fresh portfolio
    trade_history, triggers, pnl_history, bar_scores_history = extract_trade_history_and_pnl_from_portfolio(portfolio,
                                                                                                            backtest_streamer)

    # Get threshold config
    threshold_config = {}
    if hasattr(best_individual, 'monitor_configuration'):
        monitor_config = best_individual.monitor_configuration
        threshold_config = {
            'enter_long': getattr(monitor_config, 'enter_long', []),
            'exit_long': getattr(monitor_config, 'exit_long', [])
        }

    return {
        'ticker': data_config['ticker'],
        'candlestick_data': candlestick_data,
        'triggers': triggers,
        'trade_history': trade_history,
        'pnl_history': pnl_history,
        'bar_scores_history': bar_scores_history,
        'threshold_config': threshold_config,
        'total_candles': len(candlestick_data),
        'total_trades': len(trade_history),
        'date_range': {
            'start': data_config['start_date'],
            'end': data_config['end_date']
        }
    }


def extract_trade_history_and_pnl_from_portfolio(portfolio, backtest_streamer):
    """Extract trade history, triggers, P&L history, and bar scores from portfolio"""
    logger.info("💼 Extracting trade history and P&L from portfolio")

    trade_history = []
    triggers = []
    pnl_history = []
    bar_scores_history = []

    try:
        # Generate bar scores history from the stored calculation
        try:
            # Access the bar score history we calculated before running the backtest
            if (hasattr(backtest_streamer, 'bar_score_history_dict') and
                    backtest_streamer.bar_score_history_dict and
                    backtest_streamer.tick_history):

                bar_score_history_dict = backtest_streamer.bar_score_history_dict
                tick_history = backtest_streamer.tick_history

                logger.info(f"📊 Found bar scores history with {len(bar_score_history_dict)} bars")

                # Create timeline of bar scores
                timeline_length = len(tick_history)
                for i in range(timeline_length):
                    if i < len(tick_history):
                        tick = tick_history[i]
                        timestamp = int(tick.timestamp.timestamp() * 1000)

                        scores = {}
                        for bar_name, bar_values in bar_score_history_dict.items():
                            if i < len(bar_values):
                                scores[bar_name] = bar_values[i]
                            else:
                                scores[bar_name] = 0.0

                        bar_scores_history.append({
                            'timestamp': timestamp,
                            'scores': scores
                        })

                logger.info(f"📈 Generated {len(bar_scores_history)} bar score history entries")
            else:
                logger.warning("⚠️  No bar score history data available from backtest streamer")

        except Exception as bar_error:
            logger.warning(f"⚠️  Could not generate bar scores history: {bar_error}")
            import traceback
            traceback.print_exc()

        if portfolio and hasattr(portfolio, 'trade_history') and portfolio.trade_history:
            logger.info(f"📊 Found {len(portfolio.trade_history)} trades in portfolio")

            # Calculate cumulative P&L over time
            cumulative_pnl = 0.0
            trade_pairs = []  # Store entry/exit pairs for P&L calculation

            # Process trades to build P&L history
            for i, trade in enumerate(portfolio.trade_history):
                # Determine trade type based on TradeReason
                trade_type = 'buy'
                if trade.reason in [TradeReason.EXIT_LONG, TradeReason.STOP_LOSS, TradeReason.TAKE_PROFIT]:
                    trade_type = 'sell'

                # Convert timestamp to milliseconds for JavaScript
                timestamp_ms = int(trade.time.timestamp() * 1000) if hasattr(trade.time, 'timestamp') else trade.time

                trade_entry = {
                    'timestamp': timestamp_ms,
                    'type': trade_type,
                    'price': trade.price,
                    'quantity': trade.size,
                    'reason': trade.reason.value if hasattr(trade.reason, 'value') else str(trade.reason)
                }
                trade_history.append(trade_entry)

                # Add to triggers for chart display
                triggers.append({
                    'timestamp': timestamp_ms,
                    'type': trade_type,
                    'price': trade.price,
                    'reason': trade_entry['reason']
                })

                # Calculate P&L for completed trades (entry -> exit pairs)
                if trade_type == 'buy':
                    # Store entry for P&L calculation
                    trade_pairs.append({'entry': trade, 'exit': None})
                elif trade_type == 'sell' and trade_pairs:
                    # Find the matching entry and calculate P&L
                    for pair in reversed(trade_pairs):
                        if pair['exit'] is None:
                            pair['exit'] = trade
                            entry_price = pair['entry'].price
                            exit_price = trade.price
                            trade_pnl = ((exit_price - entry_price) / entry_price) * 100.0
                            cumulative_pnl += trade_pnl

                            # Add P&L point after each completed trade
                            pnl_history.append({
                                'timestamp': timestamp_ms,
                                'cumulative_pnl': cumulative_pnl,
                                'trade_pnl': trade_pnl
                            })
                            break

            logger.info(
                f"📈 Processed {len(trade_history)} trades, {len(triggers)} signals, {len(pnl_history)} P&L points")
        else:
            logger.warning("⚠️  No trade history found in portfolio")

    except Exception as e:
        logger.error(f"❌ Error extracting trade history: {e}")
        import traceback
        traceback.print_exc()

    return trade_history, triggers, pnl_history, bar_scores_history


def load_raw_candle_data(data_config_path: str, io):
    """Load raw candlestick data from Yahoo Finance using the same data as trade execution"""
    logger.info("📊 Loading raw candle data for visualization")

    try:
        # Load data config
        with open(data_config_path) as f:
            data_config = json.load(f)

        ticker = data_config['ticker']
        start_date = data_config['start_date']
        end_date = data_config['end_date']

        logger.info(f"   Ticker: {ticker}")
        logger.info(f"   Date Range: {start_date} to {end_date}")

        # Use the SAME data source as trade execution to ensure consistency
        # Access the tick_history directly from the backtest_streamer
        backtest_streamer = io.fitness_calculator.backtest_streamer
        tick_history = backtest_streamer.tick_history

        # Format candlestick data for Highcharts in the original format [timestamp, open, high, low, close]
        candlestick_data = []
        for tick in tick_history:
            timestamp = int(tick.timestamp.timestamp() * 1000)
            candlestick_data.append([
                timestamp,
                tick.open,
                tick.high,
                tick.low,
                tick.close
            ])

        logger.info(f"📈 Loaded {len(candlestick_data)} candles")
        return candlestick_data, data_config

    except Exception as e:
        logger.error(f"❌ Error loading candle data: {e}")
        raise

        raise


def save_optimization_results(best_individuals_log, best_individual, ga_config_path, test_name, timestamp=None):
    """Save optimization results to CSV and JSON files"""
    logger.info("💾 Saving optimization results...")

    # Use provided timestamp or create new one
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
        # 1. Save best monitor configuration as JSON
        if best_individual and hasattr(best_individual, 'monitor_configuration'):
            best_monitor_file = results_dir / f"{timestamp}_{test_name}_best_monitor.json"

            # Convert monitor configuration to the exact format you want
            monitor_config = best_individual.monitor_configuration

            # Extract COMPLETE trade executor config with ALL fields
            trade_executor = {}
            if hasattr(monitor_config, 'trade_executor'):
                te = monitor_config.trade_executor
                trade_executor = {
                    'default_position_size': getattr(te, 'default_position_size', 100.0),
                    'stop_loss_pct': getattr(te, 'stop_loss_pct', 0.01),
                    'take_profit_pct': getattr(te, 'take_profit_pct', 0.02),
                    'ignore_bear_signals': getattr(te, 'ignore_bear_signals', False),
                    'trailing_stop_loss': getattr(te, 'trailing_stop_loss', False),
                    'trailing_stop_distance_pct': getattr(te, 'trailing_stop_distance_pct', 0.01),
                    'trailing_stop_activation_pct': getattr(te, 'trailing_stop_activation_pct', 0.005)
                }
            else:
                # Use complete defaults if no trade executor in monitor
                trade_executor = {
                    'default_position_size': 100.0,
                    'stop_loss_pct': 0.01,
                    'take_profit_pct': 0.02,
                    'ignore_bear_signals': False,
                    'trailing_stop_loss': False,
                    'trailing_stop_distance_pct': 0.01,
                    'trailing_stop_activation_pct': 0.005
                }

            # Convert indicators to proper dict format (no ranges)
            indicators_list = []
            raw_indicators = getattr(monitor_config, 'indicators', [])

            for indicator in raw_indicators:
                if hasattr(indicator, '__dict__'):
                    # Convert indicator object to dict
                    indicator_dict = {
                        'name': getattr(indicator, 'name', ''),
                        'type': getattr(indicator, 'type', 'Indicator'),
                        'function': getattr(indicator, 'function', ''),
                        'agg_config': getattr(indicator, 'agg_config', '1m-normal'),
                        'calc_on_pip': getattr(indicator, 'calc_on_pip', False),
                        'parameters': getattr(indicator, 'parameters', {})
                    }
                elif isinstance(indicator, dict):
                    # Already a dict, just clean it up (remove ranges if present)
                    indicator_dict = {
                        'name': indicator.get('name', ''),
                        'type': indicator.get('type', 'Indicator'),
                        'function': indicator.get('function', ''),
                        'agg_config': indicator.get('agg_config', '1m-normal'),
                        'calc_on_pip': indicator.get('calc_on_pip', False),
                        'parameters': indicator.get('parameters', {})
                    }
                else:
                    # Skip malformed indicators
                    continue

                indicators_list.append(indicator_dict)

            # Build the complete monitor dict in your format with FULL trade executor
            monitor_dict = {
                'test_name': test_name,
                'monitor': {
                    '_id': '65f2d5555555555555555555',  # Placeholder ID
                    'user_id': '65f2d6666666666666666666',  # Placeholder user ID
                    'name': getattr(monitor_config, 'name', test_name),
                    'description': f'Optimized configuration from GA run {timestamp}',
                    'trade_executor': trade_executor,  # Now includes ALL fields
                    'enter_long': getattr(monitor_config, 'enter_long', []),
                    'exit_long': getattr(monitor_config, 'exit_long', []),
                    'bars': getattr(monitor_config, 'bars', {}),
                },
                'indicators': indicators_list
            }

            # Save without default=str to avoid string conversion
            with open(best_monitor_file, 'w') as f:
                json.dump(monitor_dict, f, indent=2)

            results_info['files_created'].append(str(best_monitor_file))
            logger.info(f"✅ Saved best monitor config: {best_monitor_file}")

        # 2. Save objectives evolution CSV
        if best_individuals_log:
            objectives_file = results_dir / f"{timestamp}_{test_name}_objectives.csv"

            with open(objectives_file, 'w', newline='') as f:
                writer = csv.writer(f)

                # Get all unique objective names
                all_objectives = set()
                for entry in best_individuals_log:
                    all_objectives.update(entry['metrics'].keys())

                # Write header
                header = ['Generation'] + sorted(list(all_objectives))
                writer.writerow(header)

                # Write data rows
                for entry in best_individuals_log:
                    row = [entry['generation']]
                    for obj_name in sorted(list(all_objectives)):
                        row.append(entry['metrics'].get(obj_name, ''))
                    writer.writerow(row)

            results_info['files_created'].append(str(objectives_file))
            logger.info(f"✅ Saved objectives evolution: {objectives_file}")

        # 3. Save original GA config for reference
        if ga_config_path and Path(ga_config_path).exists():
            original_config_file = results_dir / f"{timestamp}_{test_name}_original_ga_config.json"

            with open(ga_config_path, 'r') as src, open(original_config_file, 'w') as dst:
                config_data = json.load(src)
                config_data['optimization_metadata'] = {
                    'timestamp': timestamp,
                    'results_directory': str(results_dir)
                }
                json.dump(config_data, dst, indent=2)

            results_info['files_created'].append(str(original_config_file))
            logger.info(f"✅ Saved original GA config: {original_config_file}")

        # 4. Create summary report
        summary_file = results_dir / f"{timestamp}_{test_name}_summary.txt"

        with open(summary_file, 'w') as f:
            f.write(f"Genetic Algorithm Optimization Results\n")
            f.write(f"=====================================\n\n")
            f.write(f"Test Name: {test_name}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Total Generations: {len(best_individuals_log) if best_individuals_log else 0}\n\n")

            if best_individuals_log:
                f.write(f"Final Best Metrics:\n")
                final_metrics = best_individuals_log[-1]['metrics']
                for metric, value in final_metrics.items():
                    f.write(f"  {metric}: {value:.4f}\n")

            f.write(f"\nFiles Created:\n")
            for file_path in results_info['files_created']:
                f.write(f"  - {Path(file_path).name}\n")

        results_info['files_created'].append(str(summary_file))
        logger.info(f"✅ Created summary report: {summary_file}")

        logger.info(f"💾 Successfully saved {len(results_info['files_created'])} files to {results_dir}")

    except Exception as e:
        logger.error(f"❌ Error saving results: {e}")
        raise

    return results_info


# WebSocket event handlers
@socketio.on('start_optimization')
def handle_start_optimization(data):
    """Start the genetic algorithm optimization"""
    global optimization_state

    if optimization_state['running']:
        emit('optimization_error', {'error': 'Optimization already running'})
        return

    ga_config_path = data.get('ga_config_path')
    data_config_path = data.get('data_config_path')

    if not ga_config_path or not data_config_path:
        emit('optimization_error', {'error': 'Config paths not provided'})
        return

    # Reset state
    optimization_state['running'] = True
    optimization_state['paused'] = False
    optimization_state['current_generation'] = 0
    optimization_state['best_individuals_log'] = []

    # Start optimization thread
    optimization_state['thread'] = threading.Thread(
        target=run_genetic_algorithm_threaded,
        args=(ga_config_path, data_config_path)
    )
    optimization_state['thread'].start()


@socketio.on('pause_optimization')
def handle_pause_optimization():
    """Pause the optimization"""
    global optimization_state

    if optimization_state['running']:
        optimization_state['paused'] = True
        emit('optimization_paused', {
            'generation': optimization_state['current_generation'],
            'total_generations': optimization_state['total_generations']
        })
        logger.info("Optimization paused by user")


@socketio.on('resume_optimization')
def handle_resume_optimization():
    """Resume the optimization"""
    global optimization_state

    if optimization_state['running'] and optimization_state['paused']:
        optimization_state['paused'] = False
        emit('optimization_resumed', {
            'generation': optimization_state['current_generation'],
            'total_generations': optimization_state['total_generations']
        })
        logger.info("Optimization resumed by user")


@socketio.on('stop_optimization')
def handle_stop_optimization():
    """Stop the optimization"""
    global optimization_state

    optimization_state['running'] = False
    optimization_state['paused'] = False

    if optimization_state['thread'] and optimization_state['thread'].is_alive():
        optimization_state['thread'].join(timeout=2)

    emit('optimization_stopped', {
        'generation': optimization_state['current_generation'],
        'total_generations': optimization_state['total_generations']
    })
    logger.info("Optimization stopped by user")


# Keep your existing REST endpoints for file uploads and config loading
@app.route('/')
def index():
    """Main page for the genetic algorithm visualization app"""
    return render_template('main.html')


@app.route('/api/upload_file', methods=['POST'])
def upload_file():
    """Handle file uploads and save them temporarily"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})

        file = request.files['file']
        file_type = request.form.get('type', 'unknown')

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})

        if not file.filename.endswith('.json'):
            return jsonify({'success': False, 'error': 'Only JSON files are allowed'})

        # Create uploads directory
        uploads_dir = Path('uploads')
        uploads_dir.mkdir(exist_ok=True)

        # Save file with type prefix
        filename = f"{file_type}_{file.filename}"
        filepath = uploads_dir / filename

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


@app.route('/api/load_configs', methods=['POST'])
def load_configs():
    """Load and validate the uploaded configuration files"""
    try:
        data = request.get_json()
        ga_config_path = data.get('ga_config_path')
        data_config_path = data.get('data_config_path')

        if not ga_config_path or not data_config_path:
            return jsonify({'success': False, 'error': 'Both config files are required'})

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

        return jsonify({
            'success': True,
            'ga_config': {
                'test_name': ga_config.get('test_name', 'Unknown'),
                'monitor': ga_config.get('monitor', {}),
                'genetic_algorithm': ga_config.get('genetic_algorithm', {})
            },
            'data_config': data_config
        })

    except Exception as e:
        logger.error(f"Error loading configs: {e}")
        return jsonify({'success': False, 'error': str(e)})

        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/save_generation_metrics', methods=['POST'])
def save_generation_metrics():
    """Save generation metrics data to CSV file"""
    try:
        data = request.get_json()
        test_name = data.get('test_name', 'unknown')
        generation_metrics = data.get('generation_metrics', [])
        timestamp = data.get('timestamp')

        if not generation_metrics:
            return jsonify({'success': False, 'error': 'No metrics data provided'})

        # Create results directory
        results_dir = Path('results') / f"{timestamp}_{test_name}"
        results_dir.mkdir(parents=True, exist_ok=True)

        # Save generation metrics CSV
        metrics_file = results_dir / f"{timestamp}_{test_name}_generation_metrics.csv"

        with open(metrics_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Generation', 'Total_Trades', 'Winning_Trades', 'Losing_Trades',
                             'Total_PnL_Percent', 'Avg_Win_Percent', 'Avg_Loss_Percent'])

            for metrics in generation_metrics:
                writer.writerow([
                    metrics['generation'],
                    metrics['totalTrades'],
                    metrics['winningTrades'],
                    metrics['losingTrades'],
                    round(metrics['totalPnL'], 4),
                    round(metrics['avgWin'], 4),
                    round(metrics['avgLoss'], 4)
                ])

        logger.info(f"✅ Updated generation metrics: {metrics_file}")

        return jsonify({
            'success': True,
            'file_path': str(metrics_file),
            'metrics_count': len(generation_metrics)
        })

    except Exception as e:
        logger.error(f"Error saving generation metrics: {e}")
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    # Create uploads directory if it doesn't exist
    uploads_dir = Path('uploads')
    uploads_dir.mkdir(exist_ok=True)
    logger.info(f"Created uploads directory: {uploads_dir.absolute()}")

    socketio.run(app, debug=True, host='0.0.0.0', port=5001)