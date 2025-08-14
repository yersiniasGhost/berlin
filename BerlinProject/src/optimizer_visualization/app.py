import os
import sys
import json
import logging
import threading
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from datetime import datetime

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

        # Emit initial status
        socketio.emit('optimization_started', {
            'test_name': test_name,
            'total_generations': genetic_algorithm.number_of_generations,
            'population_size': genetic_algorithm.population_size
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

            # Get chart data for this best individual
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
            socketio.emit('optimization_complete', {
                'total_generations': optimization_state['current_generation'],
                'best_individuals_log': optimization_state['best_individuals_log']
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


# Keep all your existing helper functions unchanged
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


def extract_trade_history_and_pnl(best_individual, io):
    """Extract trade history, triggers, P&L history, and bar scores from the best individual"""
    logger.info("💼 Extracting trade history and P&L from best individual")

    trade_history = []
    triggers = []
    pnl_history = []
    bar_scores_history = []

    try:
        # Get portfolio from the individual
        portfolio = getattr(best_individual, 'portfolio', None)

        if portfolio and hasattr(portfolio, 'trade_history') and portfolio.trade_history:
            logger.info(f"📋 Found {len(portfolio.trade_history)} trades in portfolio")

            cumulative_pnl = 0.0

            # Process each trade for trade history and P&L calculation
            for trade in portfolio.trade_history:
                # Add trigger points for entry/exit signals
                triggers.append({
                    'timestamp': int(trade.time.timestamp() * 1000) if hasattr(trade.time, 'timestamp') else trade.time,
                    'price': trade.price,
                    'type': 'buy' if trade.reason == TradeReason.ENTER_LONG else 'sell',
                    'reason': trade.reason.name if hasattr(trade.reason, 'name') else str(trade.reason)
                })

                # For completed trades (entries with matching exits), calculate P&L
                if trade.reason == TradeReason.ENTER_LONG:
                    entry_trade = trade
                    entry_price = trade.price
                    entry_time = trade.time

                    # Find corresponding exit
                    for exit_trade in portfolio.trade_history:
                        if (exit_trade.reason == TradeReason.EXIT_LONG and
                                exit_trade.time > entry_time):
                            exit_price = exit_trade.price

                            # Calculate trade P&L percentage
                            trade_pnl = ((exit_price - entry_price) / entry_price) * 100.0
                            cumulative_pnl += trade_pnl

                            # Add completed trade to history
                            trade_history.append({
                                'entry_time': int(entry_time.timestamp() * 1000) if hasattr(entry_time,
                                                                                            'timestamp') else entry_time,
                                'exit_time': int(exit_trade.time.timestamp() * 1000) if hasattr(exit_trade.time,
                                                                                                'timestamp') else exit_trade.time,
                                'entry_price': entry_price,
                                'exit_price': exit_price,
                                'pnl_percent': trade_pnl,
                                'cumulative_pnl': cumulative_pnl
                            })

                            # Add P&L point after each completed trade
                            pnl_history.append({
                                'timestamp': int(exit_trade.time.timestamp() * 1000) if hasattr(exit_trade.time,
                                                                                                'timestamp') else exit_trade.time,
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


if __name__ == '__main__':
    # Create uploads directory if it doesn't exist
    uploads_dir = Path('uploads')
    uploads_dir.mkdir(exist_ok=True)
    logger.info(f"Created uploads directory: {uploads_dir.absolute()}")

    socketio.run(app, debug=True, port=5001)