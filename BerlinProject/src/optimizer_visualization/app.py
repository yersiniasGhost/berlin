import os
import sys
import json
import logging
from pathlib import Path
from flask import Flask, render_template, request, jsonify
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


#TODO: REFACTOR THIS CODE OUT
# PAUSE AND CANCEL BUTTONS
# BAR GRAPH UNDERNEATH

def run_genetic_algorithm(ga_config_path: str, data_config_path: str):
    """Run the genetic algorithm optimization and return best individual"""
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

        out_str = f"{test_name}, {stats[0].iteration}/{genetic_algorithm.number_of_generations}, {metric_out}"
        logger.info(out_str)

    logger.info("⏱️  Optimization completed")

    return best_individual, optimization_stats, io, test_name


def load_raw_candle_data(data_config_path: str):
    """Load pure 1-minute candle data directly from MongoDB"""
    # Load data config
    with open(data_config_path, 'r') as f:
        data_config = json.load(f)

    # Get pure 1-minute candle data directly from YahooFinanceHistorical
    yahoo_data = YahooFinanceHistorical()

    # Load the raw tick data directly (pure 1-minute data from MongoDB)
    raw_ticks = yahoo_data._load_raw_ticks(
        data_config['ticker'],
        data_config['start_date'],
        data_config['end_date']
    )

    if not raw_ticks:
        raise Exception('Failed to load raw 1-minute tick data from MongoDB')

    logger.info(f"📈 Loaded {len(raw_ticks)} raw ticks from MongoDB")

    # Deduplicate ticks by timestamp - keep the first occurrence of each minute
    seen_timestamps = set()
    deduplicated_ticks = []
    duplicates_removed = 0

    for tick in raw_ticks:
        timestamp_key = tick.timestamp
        if timestamp_key not in seen_timestamps:
            seen_timestamps.add(timestamp_key)
            deduplicated_ticks.append(tick)
        else:
            duplicates_removed += 1

    logger.info(f"📊 Removed {duplicates_removed} duplicate timestamps")
    logger.info(f"📈 Using {len(deduplicated_ticks)} unique 1-minute candles")

    # Format candlestick data for Highcharts
    candlestick_data = []
    for tick in deduplicated_ticks:
        timestamp = int(tick.timestamp.timestamp() * 1000)
        candlestick_data.append([
            timestamp,
            tick.open,
            tick.high,
            tick.low,
            tick.close
        ])

    logger.info(f"📊 Prepared {len(candlestick_data)} unique 1-minute candles for chart")

    return candlestick_data, data_config


def extract_threshold_configuration(best_individual):
    """Extract threshold configuration for each bar from the best individual"""
    threshold_config = {}

    try:
        # Get enter_long thresholds (entry conditions)
        enter_conditions = getattr(best_individual.monitor_configuration, 'enter_long', [])
        for condition in enter_conditions:
            bar_name = condition.get('name')
            threshold = condition.get('threshold', 0.5)
            threshold_config[bar_name] = {
                'threshold': threshold,
                'type': 'entry',
                'color': '#28a745'  # Green for entry
            }

        # Get exit_long thresholds (exit conditions)
        exit_conditions = getattr(best_individual.monitor_configuration, 'exit_long', [])
        for condition in exit_conditions:
            bar_name = condition.get('name')
            threshold = condition.get('threshold', 0.6)
            threshold_config[bar_name] = {
                'threshold': threshold,
                'type': 'exit',
                'color': '#dc3545'  # Red for exit
            }

        logger.info(f"📏 Extracted thresholds for {len(threshold_config)} bars")
        for bar_name, config in threshold_config.items():
            logger.info(f"   {bar_name}: {config['threshold']:.3f} ({config['type']})")

    except Exception as e:
        logger.error(f"❌ Error extracting threshold configuration: {e}")

    return threshold_config

def extract_trade_history_and_pnl(best_individual, io):
    """Extract trade history and calculate P&L from the best individual"""
    trade_history = []
    triggers = []
    pnl_history = []

    try:
        logger.info("🔄 Running backtest with best individual to generate trade history...")

        # Get the backtest streamer and replace monitor config
        backtest_streamer = io.fitness_calculator.backtest_streamer
        backtest_streamer.replace_monitor_config(best_individual.monitor_configuration)

        # Run the backtest to populate portfolio with trades
        portfolio = backtest_streamer.run()

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

                trade_entry = {
                    'timestamp': trade.time,
                    'type': trade_type,
                    'price': trade.price,
                    'quantity': trade.size,
                    'reason': trade.reason.value if hasattr(trade.reason, 'value') else str(trade.reason)
                }
                trade_history.append(trade_entry)

                # Add to triggers for chart display
                triggers.append({
                    'timestamp': trade.time,
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
                                'timestamp': trade.time,
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

    return trade_history, triggers, pnl_history


def build_response(data_config, candlestick_data, triggers, trade_history, pnl_history, test_name, bar_scores_history, threshold_config):
    """Build the final response object"""
    response = {
        'success': True,
        'ticker': data_config['ticker'],
        'candlestick_data': candlestick_data,
        'triggers': triggers,
        'trade_history': trade_history,
        'pnl_history': pnl_history,
        'total_candles': len(candlestick_data),
        'total_trades': len(trade_history),
        'date_range': {
            'start': data_config['start_date'],
            'end': data_config['end_date']
        },
        'optimization_summary': {
            'test_name': test_name,
            'generation': 1
        },
        'bar_scores_history': bar_scores_history,
        'threshold_config': threshold_config  # Add threshold config
    }

    logger.info(f"✅ Response prepared: {len(candlestick_data)} candles, {len(triggers)} signals, {len(bar_scores_history)} bar scores")
    return response


def extract_bar_scores_history_from_backtest(best_individual, io, candlestick_data):
    """Extract bar scores history during backtest for charting"""
    bar_scores_history = []

    try:
        logger.info("🔄 Extracting bar scores history from backtest...")

        # Get the backtest streamer and replace monitor config
        backtest_streamer = io.fitness_calculator.backtest_streamer
        backtest_streamer.replace_monitor_config(best_individual.monitor_configuration)

        # Get indicator processor to calculate bar scores
        from optimization.calculators.indicator_processor_historical_new import IndicatorProcessorHistoricalNew
        indicator_processor = IndicatorProcessorHistoricalNew(best_individual.monitor_configuration)
        indicator_history, raw_indicator_history, bar_score_history = (
            indicator_processor.calculate_indicators(backtest_streamer.aggregators)
        )

        # Convert bar_score_history to timeline format
        if bar_score_history and candlestick_data:
            for i, candle_data in enumerate(candlestick_data):
                timestamp = candle_data[0]  # First element is timestamp

                # Get bar scores for this time point
                bar_scores = {}
                for bar_name, values in bar_score_history.items():
                    bar_scores[bar_name] = values[i] if i < len(values) else 0.0

                bar_scores_history.append({
                    'timestamp': timestamp,
                    'scores': bar_scores
                })

        logger.info(f"📊 Extracted {len(bar_scores_history)} bar score data points")

    except Exception as e:
        logger.error(f"❌ Error extracting bar scores history: {e}")
        import traceback
        traceback.print_exc()

    return bar_scores_history


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
        file_type = request.form.get('file_type')

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})

        # Create uploads directory
        uploads_dir = Path('uploads')
        uploads_dir.mkdir(exist_ok=True)

        # Save file with original name
        file_path = uploads_dir / file.filename
        file.save(str(file_path))

        return jsonify({
            'success': True,
            'file_path': str(file_path),
            'file_type': file_type,
            'filename': file.filename
        })

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/load_configs', methods=['POST'])
def load_configs():
    """Load and parse configuration files"""
    try:
        data = request.get_json()
        ga_config_path = data.get('ga_config_path')
        data_config_path = data.get('data_config_path')

        if not ga_config_path or not data_config_path:
            return jsonify({'success': False, 'error': 'Both config file paths required'})

        # Check files exist
        if not Path(ga_config_path).exists():
            return jsonify({'success': False, 'error': f'GA config file not found: {ga_config_path}'})
        if not Path(data_config_path).exists():
            return jsonify({'success': False, 'error': f'Data config file not found: {data_config_path}'})

        # Load and parse configs
        with open(ga_config_path, 'r') as f:
            ga_config = json.load(f)

        with open(data_config_path, 'r') as f:
            data_config = json.load(f)

        # Build summary
        summary = {
            'ga_config': {
                'test_name': ga_config.get('test_name', 'Unknown'),
                'population_size': ga_config.get('population_size', 'Unknown'),
                'generations': ga_config.get('generations', 'Unknown'),
                'mutation_rate': ga_config.get('mutation_rate', 'Unknown')
            },
            'data_config': {
                'ticker': data_config.get('ticker', 'Unknown'),
                'start_date': data_config.get('start_date', 'Unknown'),
                'end_date': data_config.get('end_date', 'Unknown'),
                'time_increment': data_config.get('time_increment', 1)
            }
        }

        return jsonify({
            'success': True,
            'summary': summary,
            'ga_config_path': ga_config_path,
            'data_config_path': data_config_path
        })

    except Exception as e:
        logger.error(f"Error loading configs: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/run_optimization', methods=['POST'])
def run_optimization():
    """Main optimization endpoint - simplified and delegated to helper functions"""
    try:
        data = request.get_json()
        ga_config_path = data.get('ga_config_path')
        data_config_path = data.get('data_config_path')

        if not ga_config_path or not data_config_path:
            return jsonify({'success': False, 'error': 'Config paths not provided'})

        # Step 1: Run genetic algorithm optimization
        best_individual, optimization_stats, io, test_name = run_genetic_algorithm(ga_config_path, data_config_path)

        if not best_individual:
            return jsonify({'success': False, 'error': 'No optimization results generated'})

        # Step 2: Load pure 1-minute candle data
        candlestick_data, data_config = load_raw_candle_data(data_config_path)

        # Step 3: Extract trade history and calculate P&L
        trade_history, triggers, pnl_history = extract_trade_history_and_pnl(best_individual, io)
        # Step 4: Extract bar scores history and thresholds
        bar_scores_history = extract_bar_scores_history_from_backtest(best_individual, io, candlestick_data)
        threshold_config = extract_threshold_configuration(best_individual)

        # Step 5: Build and return response
        response = build_response(data_config, candlestick_data, triggers, trade_history, pnl_history, test_name,
                                  bar_scores_history, threshold_config)
        return jsonify(response)

    except Exception as e:
        logger.error(f"❌ Error running optimization: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    # Create uploads directory if it doesn't exist
    uploads_dir = Path('uploads')
    uploads_dir.mkdir(exist_ok=True)
    logger.info(f"Created uploads directory: {uploads_dir.absolute()}")

    app.run(debug=True, port=5001)