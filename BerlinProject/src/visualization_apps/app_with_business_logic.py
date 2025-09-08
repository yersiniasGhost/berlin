from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import os
import sys
import json
import logging
import threading
import time
import csv
import math
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
from werkzeug.utils import secure_filename

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..'))

# Import all necessary modules from your existing apps
from optimization.genetic_optimizer.apps.utils.mlf_optimizer_config import MlfOptimizerConfig
from optimization.calculators.yahoo_finance_historical import YahooFinanceHistorical
from portfolios.portfolio_tool import TradeReason
from optimization.genetic_optimizer.abstractions import IndividualBase
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
from optimization.genetic_optimizer.genetic_algorithm import crowd_sort
from models.monitor_configuration import MonitorConfiguration, TradeExecutorConfig
from models.indicator_definition import IndicatorDefinition
from data_streamer.indicator_processor import IndicatorProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('VisualizationApp')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'visualization-apps-secret-key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
socketio = SocketIO(app, cors_allowed_origins="*")

# Create upload folders
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global optimization state for optimizer
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

# Utility functions from your existing apps
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'json'

def sanitize_nan_values(obj):
    """
    Recursively sanitize NaN values in a data structure for JSON compatibility.
    Converts NaN to None (null in JSON), and handles nested lists/dicts.
    """
    if isinstance(obj, dict):
        return {key: sanitize_nan_values(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_nan_values(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj):
            return None
        elif math.isinf(obj):
            return None  # Convert infinity to null as well
        else:
            return obj
    else:
        return obj

# Optimizer utility functions
def balance_fronts(front: List[IndividualStats]) -> List[IndividualStats]:
    ideal_point = np.min([ind.fitness_values for ind in front], axis=0)
    balanced_front = sorted(front, key=lambda ind: np.linalg.norm(ind.fitness_values - ideal_point))
    return balanced_front

def select_winning_population(number_of_elites: int, fronts: Dict[int, List]) -> [List[IndividualStats]]:
    elitists: List[IndividualStats] = []
    for front in fronts.values():
        sorted_front = balance_fronts(front)
        for stat in sorted_front:
            if len(elitists) < number_of_elites:
                elitists.append(stat)
    return elitists

# ===== REPLAY VISUALIZATION FUNCTIONS =====

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

def run_monitor_backtest(monitor_config_path: str, data_config_path: str):
    """Run backtest with the provided monitor configuration and return chart data"""
    logger.info("🔍 Running monitor backtest for visualization")

    try:
        # Load monitor config
        with open(monitor_config_path) as f:
            monitor_data = json.load(f)

        # Load data config
        with open(data_config_path) as f:
            data_config = json.load(f)

        # Extract the monitor configuration from the JSON structure
        if 'monitor' in monitor_data:
            # New format: {"test_name": "...", "monitor": {...}, "indicators": [...]}
            monitor_config = monitor_data['monitor']
            indicators = monitor_data.get('indicators', [])
            test_name = monitor_data.get('test_name', 'Monitor Visualization')
        else:
            # Legacy format - assume the whole file is the monitor config
            monitor_config = monitor_data
            indicators = monitor_data.get('indicators', [])
            test_name = monitor_data.get('name', 'Monitor Visualization')

        logger.info(f"📋 Running backtest for: {test_name}")
        logger.info(f"📊 Data: {data_config['ticker']} from {data_config['start_date']} to {data_config['end_date']}")
        logger.info(f"   Data config path: {data_config_path}")

        # Create monitor configuration object directly
        # Prepare trade executor config first
        if 'trade_executor' in monitor_config:
            te_config = TradeExecutorConfig(**monitor_config['trade_executor'])
        else:
            # Fallback to defaults if somehow incomplete
            te_config = TradeExecutorConfig()

        # Create monitor configuration with all data at once
        monitor_obj = MonitorConfiguration(
            name=monitor_config.get('name', test_name),
            indicators=indicators,
            bars=monitor_config.get('bars', {}),
            enter_long=monitor_config.get('enter_long', []),
            exit_long=monitor_config.get('exit_long', []),
            trade_executor=te_config
        )

        # Load historical data using Yahoo Finance Historical
        yahoo_source = YahooFinanceHistorical()
        yahoo_source.process_historical_data(
            data_config['ticker'],
            data_config['start_date'],
            data_config['end_date'],
            monitor_obj
        )

        # Create backtest streamer manually
        from optimization.calculators.bt_data_streamer import BacktestDataStreamer

        backtest_streamer = BacktestDataStreamer(monitor_obj, data_config_path)

        # Calculate indicators and bar scores using the monitor configuration
        from optimization.calculators.indicator_processor_historical_new import IndicatorProcessorHistoricalNew

        indicator_processor = IndicatorProcessorHistoricalNew(monitor_obj)
        indicator_history, raw_indicator_history, bar_score_history_dict, component_history = (
            indicator_processor.calculate_indicators(backtest_streamer.aggregators)
        )

        # Store the bar score history for later access
        backtest_streamer.bar_score_history_dict = bar_score_history_dict

        # Run the backtest to get trades
        portfolio = backtest_streamer.run()

        # Load raw candle data for visualization
        candlestick_data = []
        tick_history = backtest_streamer.tick_history
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

        # Extract trade history and P&L from the fresh portfolio
        trade_history, triggers, pnl_history, bar_scores_history = extract_trade_history_and_pnl_from_portfolio(
            portfolio, backtest_streamer)

        # Get threshold config for bar charts
        threshold_config = {
            'enter_long': monitor_config.get('enter_long', []),
            'exit_long': monitor_config.get('exit_long', [])
        }

        # Format component data for charts (MACD, SMA components)
        component_data_formatted = {}
        if component_history:
            for comp_name, comp_values in component_history.items():
                # Convert to Highcharts format with timestamps
                comp_series = []
                for i, value in enumerate(comp_values):
                    if i < len(tick_history) and value is not None:
                        timestamp = int(tick_history[i].timestamp.timestamp() * 1000)
                        comp_series.append([timestamp, float(value)])
                
                component_data_formatted[comp_name] = {
                    'data': comp_series,
                    'name': comp_name
                }

        # Format component data for the MACD chart (keep this for MACD/signal/histogram)
        # indicator_data should NOT have the decayed values - leave it empty or minimal
        indicator_data_formatted = {}

        # Add indicator_history for the trigger signals chart (using time-decayed values)
        indicator_history_formatted = []
        if indicator_history and tick_history:
            for i, tick in enumerate(tick_history):
                timestamp = int(tick.timestamp.timestamp() * 1000)
                indicator_values = {}
                for ind_name, ind_values in indicator_history.items():
                    if i < len(ind_values):
                        value = ind_values[i] if ind_values[i] is not None else 0.0
                        indicator_values[ind_name] = value
                    else:
                        indicator_values[ind_name] = 0.0
                
                indicator_history_formatted.append({
                    'timestamp': timestamp,
                    **indicator_values
                })

        chart_data = {
            'ticker': data_config['ticker'],
            'candlestick_data': candlestick_data,
            'triggers': triggers,
            'trade_history': trade_history,
            'pnl_history': pnl_history,
            'bar_scores_history': bar_scores_history,
            'threshold_config': threshold_config,
            'component_data': component_data_formatted,  # MACD/SMA component data (unchanged)
            'indicator_data': indicator_data_formatted,  # Time-decayed indicator data (unchanged)
            'indicator_history': indicator_history_formatted,  # For trigger signals chart ONLY
            'total_candles': len(candlestick_data),
            'total_trades': len(trade_history),
            'date_range': {
                'start': data_config['start_date'],
                'end': data_config['end_date']
            }
        }

        logger.info("✅ Successfully generated chart data")
        
        # Sanitize NaN values for JSON compatibility
        sanitized_chart_data = sanitize_nan_values(chart_data)
        logger.info("🧹 Sanitized NaN values for JSON compatibility")
        
        return sanitized_chart_data

    except Exception as e:
        logger.error(f"❌ Error running monitor backtest: {e}")
        import traceback
        traceback.print_exc()
        raise

# ===== INDICATOR VISUALIZATION CLASS =====

class SimpleIndicatorVisualizer:
    def __init__(self):
        self.yahoo_finance = YahooFinanceHistorical()

    def load_and_process_data(self, ticker: str, start_date: str, end_date: str, indicator_configs: list):
        """Load data and process ENTIRELY using IndicatorProcessor"""
        logger.info(f"Loading data for {ticker} from {start_date} to {end_date}")

        # Create indicator definitions from configs
        indicators = []
        for config in indicator_configs:
            indicator = IndicatorDefinition(
                name=config['name'],
                type=config['type'],
                function=config['function'],
                parameters=config['parameters'],
                agg_config=config.get('agg_config', '1m-normal'),
                calc_on_pip=config.get('calc_on_pip', False)
            )
            indicators.append(indicator)

        # Create monitor config
        monitor_config = MonitorConfiguration(
            name="indicator_viz_monitor",
            description="Temporary monitor for indicator visualization",
            indicators=indicators,
            trade_executor={
                "default_position_size": 100.0,
                "stop_loss_pct": 0.01,
                "take_profit_pct": 0.02,
                "ignore_bear_signals": False,
                "trailing_stop_loss": False,
                "trailing_stop_distance_pct": 0.01,
                "trailing_stop_activation_pct": 0.005
            }
        )

        # Process data using YahooFinanceHistorical (same as optimizer)
        success = self.yahoo_finance.process_historical_data(ticker, start_date, end_date, monitor_config)

        if not success:
            return None, None, None, None

        # Get aggregators (same as optimizer)
        aggregators = self.yahoo_finance.aggregators

        # Get the main aggregator key for timestamps
        main_key = None
        for key in aggregators.keys():
            if "1m" in key:
                main_key = key
                break
        if not main_key:
            main_key = list(aggregators.keys())[0]

        # Get candles from aggregator history for timestamps
        candles = aggregators[main_key].history

        # Calculate ALL indicator data using IndicatorProcessor 
        indicator_data = self.process_indicators_through_time(aggregators, monitor_config, candles)

        logger.info(f"Loaded {len(candles)} candles from {main_key}")
        logger.info(f"Processed indicators through time: {list(indicator_data.keys())}")

        return candles, indicator_data, monitor_config

    def process_indicators_through_time(self, aggregators, monitor_config, candles):
        """Process indicators using BOTH raw calculations AND IndicatorProcessor"""
        logger.info("Processing indicators through IndicatorProcessor...")
        
        # Step 1: Get raw trigger history using direct calculation (fast and complete)
        raw_data = self.calculate_raw_indicator_values(candles, [
            {
                'name': ind.name,
                'type': ind.type,
                'function': ind.function, 
                'parameters': ind.parameters
            } for ind in monitor_config.indicators
        ])
        
        # Step 2: Get current time-decayed values from IndicatorProcessor
        indicator_processor = IndicatorProcessor(monitor_config)
        
        for agg in aggregators.values():
            agg.completed_candle = True
        
        indicators, raw_indicators, bar_scores = indicator_processor.calculate_indicators_new(aggregators)
        
        # Step 3: Calculate time-decayed history using the raw trigger data
        time_decayed_histories = {}
        
        for indicator_def in monitor_config.indicators:
            indicator_name = indicator_def.name
            triggers_key = f"{indicator_name}_triggers"
            
            if triggers_key in raw_data:
                triggers = raw_data[triggers_key]
                lookback = indicator_def.parameters.get('lookback', 10)
                
                # Calculate decayed values for the entire trigger history
                decayed_values = []
                for i in range(len(triggers)):
                    # Get trigger history up to this point
                    window = triggers[:i+1]
                    if len(window) > 0:
                        import numpy as np
                        decay_value = indicator_processor.calculate_time_based_metric(np.array(window), lookback)
                        decayed_values.append(decay_value)
                    else:
                        decayed_values.append(0.0)
                
                time_decayed_histories[f"{indicator_name}_decayed"] = decayed_values
        
        # Step 4: Return component values (MACD, SMA lines) + decayed values, but NO raw triggers
        component_data = {}
        for key, value in raw_data.items():
            # Include component values (MACD, SMA, signal, histogram) but exclude triggers
            if not key.endswith('_triggers'):
                component_data[key] = value
        
        result = {
            **component_data,  # MACD, SMA component values (lines/histograms)
            **time_decayed_histories,  # Time-decayed trigger values
            'current_raw_indicators': raw_indicators,
            'current_time_decayed_indicators': indicators,
            'current_bar_scores': bar_scores
        }
        
        logger.info(f"Generated data for: {list(result.keys())}")
        
        return result

    def calculate_raw_indicator_values(self, candles, indicator_configs):
        """Calculate the actual raw indicator values AND trigger signals - ORIGINAL WORKING VERSION"""
        raw_values = {}

        # Convert candles to TickData list for indicator functions
        tick_data_list = []
        for candle in candles:
            from models.tick_data import TickData
            tick = TickData(
                symbol=candle.symbol,
                timestamp=candle.timestamp,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume
            )
            tick_data_list.append(tick)

        for config in indicator_configs:
            function = config.get('function')
            parameters = config.get('parameters', {})
            name = config.get('name')

            logger.info(f"Calculating raw values for {name} using {function}")

            if function == 'macd_histogram_crossover':
                # Get the actual MACD calculation values
                fast = parameters.get('fast', 12)
                slow = parameters.get('slow', 26)
                signal = parameters.get('signal', 9)

                from features.indicators import macd_calculation, macd_histogram_crossover
                macd, signal_line, histogram = macd_calculation(tick_data_list, fast, slow, signal)

                # Get trigger signals (0s and 1s)
                trigger_signals = macd_histogram_crossover(tick_data_list, parameters)

                # Store each component separately
                raw_values[f"{name}_macd"] = macd.tolist()
                raw_values[f"{name}_signal"] = signal_line.tolist()
                raw_values[f"{name}_histogram"] = histogram.tolist()
                raw_values[f"{name}_triggers"] = trigger_signals.tolist()

                logger.info(f"MACD raw values calculated: MACD len={len(macd)}, Signal len={len(signal_line)}, Histogram len={len(histogram)}")
                logger.info(f"Trigger count: {sum(trigger_signals)} out of {len(trigger_signals)} total points")

            elif function == 'sma_crossover':
                period = parameters.get('period', 20)
                from features.indicators import sma_indicator, sma_crossover
                sma_values = sma_indicator(tick_data_list, period)

                # Get trigger signals (0s and 1s)
                trigger_signals = sma_crossover(tick_data_list, parameters)

                raw_values[f"{name}_sma"] = sma_values.tolist()
                raw_values[f"{name}_triggers"] = trigger_signals.tolist()

                logger.info(f"SMA raw values calculated: len={len(sma_values)}")
                logger.info(f"SMA trigger count: {sum(trigger_signals)} out of {len(trigger_signals)} total points")

        return raw_values

# Global visualizer instance
visualizer = SimpleIndicatorVisualizer()

# ===== MAIN ROUTES =====

@app.route('/')
def index():
    return render_template('base.html')

# ===== REPLAY VISUALIZATION ROUTES =====

@app.route('/replay')
def replay():
    return render_template('replay/main.html')

@app.route('/replay/api/upload_file', methods=['POST'])
def replay_upload_file():
    """Handle file uploads and save them temporarily"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})

        file = request.files['file']
        file_type = request.form.get('config_type', 'unknown')

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

@app.route('/replay/api/load_examples')
def replay_load_examples():
    """Load example configurations for form initialization"""
    try:
        examples = {}
        
        # Load example monitor config
        example_monitor_path = Path('inputs/random_monitor_example.json')
        if example_monitor_path.exists():
            with open(example_monitor_path) as f:
                examples['monitor_config'] = json.load(f)
        else:
            # Provide default monitor config structure
            examples['monitor_config'] = {
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
                "bars": {},
                "indicators": []
            }

        # Load example data config from replay_visualization/inputs
        example_data_path = Path('inputs/data_config_nvda.json')
        if example_data_path.exists():
            with open(example_data_path) as f:
                examples['data_config'] = json.load(f)
        else:
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

@app.route('/replay/api/run_visualization', methods=['POST'])
def replay_run_visualization():
    """Load configs and run the monitor visualization"""
    try:
        data = request.get_json()
        monitor_config_path = data.get('monitor_config_path')
        data_config_path = data.get('data_config_path')

        if not monitor_config_path or not data_config_path:
            return jsonify({'success': False, 'error': 'Both config files are required'})

        # Validate files exist
        if not Path(monitor_config_path).exists():
            return jsonify({'success': False, 'error': f'Monitor config file not found: {monitor_config_path}'})

        if not Path(data_config_path).exists():
            return jsonify({'success': False, 'error': f'Data config file not found: {data_config_path}'})

        # Run the backtest and generate chart data
        chart_data = run_monitor_backtest(monitor_config_path, data_config_path)

        # Load config summaries for display
        with open(monitor_config_path) as f:
            monitor_config = json.load(f)

        with open(data_config_path) as f:
            data_config = json.load(f)

        # Debug: Log what ticker is being returned
        actual_ticker = data_config.get('ticker', 'UNKNOWN')
        logger.info(f"🎯 Replay visualization returning ticker: {actual_ticker}")
        logger.info(f"   Data config path: {data_config_path}")

        # OPTIMIZATION: Don't include full chart data in configuration loading response
        # The frontend should request chart data separately via websocket or streaming
        chart_summary = {
            'ticker': chart_data.get('ticker'),
            'total_candles': chart_data.get('total_candles'),
            'total_trades': chart_data.get('total_trades'),
            'date_range': chart_data.get('date_range'),
            'available_components': list(chart_data.get('component_data', {}).keys()),
            'available_indicators': list(chart_data.get('indicator_data', {}).keys())
        }

        return jsonify({
            'success': True,
            'chart_summary': chart_summary,  # Send summary instead of full data
            'monitor_config': monitor_config,
            'data_config': data_config
        })

    except Exception as e:
        logger.error(f"Error running visualization: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/replay/api/get_chart_data', methods=['POST'])
def replay_get_chart_data():
    """Get the full chart data for visualization"""
    try:
        data = request.get_json()
        monitor_config_path = data.get('monitor_config_path')
        data_config_path = data.get('data_config_path')

        if not monitor_config_path or not data_config_path:
            return jsonify({'success': False, 'error': 'Both config files are required'})

        # Validate files exist
        if not Path(monitor_config_path).exists():
            return jsonify({'success': False, 'error': f'Monitor config file not found: {monitor_config_path}'})

        if not Path(data_config_path).exists():
            return jsonify({'success': False, 'error': f'Data config file not found: {data_config_path}'})

        # Run the backtest and get full chart data
        chart_data = run_monitor_backtest(monitor_config_path, data_config_path)

        logger.info(f"🎯 Returning full chart data with {chart_data.get('total_candles', 0)} candles")

        return jsonify({
            'success': True,
            'chart_data': chart_data
        })

    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ===== INDICATOR VISUALIZATION ROUTES =====

@app.route('/indicator')
def indicator():
    return render_template('indicator/main.html')

@app.route('/indicator/api/visualize', methods=['POST'])
def indicator_visualize():
    try:
        data = request.json
        ticker = data.get('ticker', '').upper()
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        indicator_configs = data.get('indicators', [])

        if not all([ticker, start_date, end_date]):
            return jsonify({"error": "Missing required parameters"}), 400

        if not indicator_configs:
            return jsonify({"error": "No indicators specified"}), 400

        # Load data using IndicatorProcessor
        candles, indicator_data, monitor_config = visualizer.load_and_process_data(
            ticker, start_date, end_date, indicator_configs
        )

        if not candles:
            return jsonify({"error": f"No data found for {ticker}"}), 404

        # Format candlestick data for Highcharts
        candlestick_data = []
        for candle in candles:
            timestamp = int(candle.timestamp.timestamp() * 1000)
            candlestick_data.append([
                timestamp,
                candle.open,
                candle.high,
                candle.low,
                candle.close
            ])

        # Format all indicator data for Highcharts
        indicators_data = {}
        
        # Process all data from IndicatorProcessor (raw, decayed, etc.)
        for indicator_name, values in indicator_data.items():
            # Skip current single-value indicators (handle separately)
            if indicator_name.startswith('current_'):
                continue
                
            # Ensure values is a list
            if not isinstance(values, list):
                continue
            
            # Create timestamp-value pairs for each indicator
            indicator_series = []
            for i, value in enumerate(values):
                if i < len(candles) and value is not None:
                    timestamp = int(candles[i].timestamp.timestamp() * 1000)
                    # Convert NaN to None for JSON serialization
                    if isinstance(value, float) and (np.isnan(value) or str(value) == 'nan'):
                        clean_value = None
                    else:
                        clean_value = float(value)

                    if clean_value is not None:
                        indicator_series.append([timestamp, clean_value])

            indicators_data[indicator_name] = {
                "data": indicator_series,
                "name": indicator_name
            }

        # Format current single-value indicators  
        current_indicators = {}
        if 'current_time_decayed_indicators' in indicator_data:
            for indicator_name, value in indicator_data['current_time_decayed_indicators'].items():
                if value is not None and not np.isnan(value):
                    current_indicators[f"{indicator_name}_current"] = {
                        "data": [[int(candles[-1].timestamp.timestamp() * 1000), float(value)]],
                        "name": f"{indicator_name} (Current Time Decayed)"
                    }

        # Format current bar scores
        bar_scores_formatted = {}
        if 'current_bar_scores' in indicator_data:
            for bar_name, value in indicator_data['current_bar_scores'].items():
                if value is not None and not np.isnan(value):
                    bar_scores_formatted[bar_name] = {
                        "data": [[int(candles[-1].timestamp.timestamp() * 1000), float(value)]],
                        "name": f"{bar_name} (Bar Score)"
                    }

        response = {
            "success": True,
            "ticker": ticker,
            "data": {
                "candlestick": candlestick_data,
                "indicators": indicators_data,  # All historical indicator data
                "current_indicators": current_indicators,  # Current time-decayed values
                "bar_scores": bar_scores_formatted  # Current bar scores
            },
            "candle_count": len(candles),
            "date_range": f"{start_date} to {end_date}"
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Create uploads directory if it doesn't exist
    uploads_dir = Path('uploads')
    uploads_dir.mkdir(exist_ok=True)
    logger.info(f"Created uploads directory: {uploads_dir.absolute()}")

    socketio.run(app, debug=True, host='0.0.0.0', port=5000)