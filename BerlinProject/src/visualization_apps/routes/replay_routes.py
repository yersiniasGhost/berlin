"""
Replay Visualization Routes
Handles monitor configuration visualization with backtest execution
"""

from flask import Blueprint, render_template, request, jsonify
import os
import sys
import json
import logging
import math
from datetime import datetime
from pathlib import Path

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..', '..'))

# Import necessary modules for replay visualization
from optimization.genetic_optimizer.apps.utils.mlf_optimizer_config import MlfOptimizerConfig
from mongo_tools.mongo_db_connect import MongoDBConnect
from portfolios.portfolio_tool import TradeReason
from models.monitor_configuration import MonitorConfiguration, TradeExecutorConfig

# Remove new indicator system imports that are causing backend conflicts  
# from indicator_triggers.indicator_base import IndicatorRegistry
# from indicator_triggers.refactored_indicators import *  # Import to register indicators

logger = logging.getLogger('ReplayVisualization')

# Create Blueprint
replay_bp = Blueprint('replay', __name__, url_prefix='/replay')

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
    """Run backtest with the provided monitor configuration using the old working method"""
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

        # Create monitor configuration object directly using the old working method
        from models.monitor_configuration import MonitorConfiguration
        from models.monitor_configuration import TradeExecutorConfig

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

        # Load historical data using MongoDB
        mongo_source = MongoDBConnect()
        mongo_source.process_historical_data(
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


        # Merge P&L information into trade objects for frontend
        trades_with_pnl = []
        pnl_lookup = {pnl['timestamp']: pnl for pnl in pnl_history}
        cumulative_pnl = 0
        
        for i, trade in enumerate(trade_history):
            trade_with_pnl = trade.copy()
            
            # Find matching P&L entry for this trade
            if trade['timestamp'] in pnl_lookup:
                pnl_entry = pnl_lookup[trade['timestamp']]
                trade_with_pnl['pnl'] = pnl_entry['trade_pnl']
                cumulative_pnl = pnl_entry['cumulative_pnl']
            else:
                # For buy orders or trades without P&L, set to 0
                trade_with_pnl['pnl'] = 0.0
            
            trades_with_pnl.append(trade_with_pnl)
        
        # Format P&L data for charting (timestamp, cumulative_pnl pairs)
        pnl_data = [[pnl['timestamp'], pnl['cumulative_pnl']] for pnl in pnl_history]
        
        chart_data = {
            'ticker': data_config['ticker'],
            'candlestick_data': candlestick_data,
            'triggers': triggers,
            'trades': trades_with_pnl,  # Frontend expects 'trades' with pnl property
            'trade_history': trade_history,  # Keep for backwards compatibility  
            'pnl_history': pnl_history,
            'pnl_data': pnl_data,  # Frontend expects 'pnl_data' for charting
            'bar_scores_history': bar_scores_history,
            'threshold_config': threshold_config,
            'component_data': component_data_formatted,  # Now includes NEW indicators
            'indicator_data': indicator_data_formatted,  # Time-decayed indicator data
            'indicator_history': indicator_history_formatted,  # For trigger signals chart ONLY
            'total_candles': len(candlestick_data),
            'total_trades': len(trades_with_pnl),
            'date_range': {
                'start': data_config['start_date'],
                'end': data_config['end_date']
            },
            'data_config': data_config,  # Include data config for reference
            'monitor_config': monitor_config  # Include monitor config for frontend display
        }

        logger.info("✅ Successfully generated chart data")
        logger.info(f"🔍 DEBUG: trades count = {len(chart_data.get('trades', []))}")  
        logger.info(f"🔍 DEBUG: pnl_history count = {len(chart_data.get('pnl_history', []))}")
        logger.info(f"🔍 DEBUG: triggers count = {len(chart_data.get('triggers', []))}")
        
        # Log some sample data for debugging
        if chart_data.get('trades'):
            logger.info(f"🔍 DEBUG: First trade = {chart_data['trades'][0]}")
        if chart_data.get('pnl_history'):
            logger.info(f"🔍 DEBUG: First PnL = {chart_data['pnl_history'][0]}")
        
        # Sanitize NaN values for JSON compatibility
        sanitized_chart_data = sanitize_nan_values(chart_data)
        logger.info("🧹 Sanitized NaN values for JSON compatibility")
        
        return sanitized_chart_data

    except Exception as e:
        logger.error(f"❌ Error running monitor backtest: {e}")
        import traceback
        traceback.print_exc()
        raise

# ===== ROUTES =====

@replay_bp.route('/')
def replay_main():
    """Main replay visualization page"""
    return render_template('replay/main.html')

@replay_bp.route('/api/upload_file', methods=['POST'])
def upload_file():
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

@replay_bp.route('/api/load_examples')
def load_examples():
    """Load example configurations for form initialization"""
    try:
        examples = {}
        
        # Load example monitor config
        example_monitor_path = Path('inputs/random_monitor_example.json')
        if example_monitor_path.exists():
            with open(example_monitor_path) as f:
                examples['monitor_config'] = json.load(f)
        else:
            # Provide default monitor config structure with NEW indicator format
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
                "indicators": [
                    {
                        "name": "sma_crossover",
                        "display_name": "SMA Crossover",
                        "parameters": {
                            "period": 20,
                            "crossover_value": 0.015,
                            "trend": "bullish"
                        },
                        "enabled": True
                    }
                ]
            }

        # Load example data config
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

@replay_bp.route('/api/run_visualization', methods=['POST'])
def run_visualization():
    """Load configs and run the monitor visualization with NEW indicator system"""
    try:
        data = request.get_json()
        logger.info(f"Received run_visualization request with data keys: {list(data.keys()) if data else 'None'}")
        
        # The frontend sends actual config objects, not file paths
        monitor_config = data.get('monitor_config')
        data_config = data.get('data_config')

        if not monitor_config or not data_config:
            return jsonify({'success': False, 'error': 'Both config objects are required'})

        # Create temporary files for the configs since our backtest function expects file paths
        import tempfile
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='_monitor_config.json', delete=False) as monitor_file:
            json.dump(monitor_config, monitor_file, indent=2)
            monitor_config_path = monitor_file.name
            
        with tempfile.NamedTemporaryFile(mode='w', suffix='_data_config.json', delete=False) as data_file:
            json.dump(data_config, data_file, indent=2)
            data_config_path = data_file.name

        try:
            # Run the backtest with original working method
            chart_data = run_monitor_backtest(monitor_config_path, data_config_path)

            return jsonify({
                'success': True,
                'data': chart_data
            })
        finally:
            # Clean up temporary files
            try:
                os.unlink(monitor_config_path)
                os.unlink(data_config_path)
            except:
                pass  # Ignore cleanup errors

    except Exception as e:
        logger.error(f"Error running visualization: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@replay_bp.route('/api/get_chart_data', methods=['POST'])
def get_chart_data():
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

        # Run the backtest and get full chart data with original working method
        chart_data = run_monitor_backtest(monitor_config_path, data_config_path)

        logger.info(f"🎯 Returning full chart data with {chart_data.get('total_candles', 0)} candles")

        return jsonify({
            'success': True,
            'chart_data': chart_data
        })

    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        return jsonify({'success': False, 'error': str(e)})

@replay_bp.route('/api/load_configs', methods=['POST'])
def load_configs():
    """Load and validate the uploaded configuration files"""
    try:
        data = request.get_json()
        logger.info(f"Received load_configs request with data: {data}")
        
        # The file upload component sends keys like 'monitor_config' and 'data_config'
        monitor_config_path = data.get('monitor_config')
        data_config_path = data.get('data_config')

        if not monitor_config_path or not data_config_path:
            available_keys = list(data.keys()) if data else []
            logger.error(f"Missing config files. Available keys: {available_keys}")
            return jsonify({'success': False, 'error': f'Both config files are required. Received keys: {available_keys}'})

        # Validate files exist
        if not Path(monitor_config_path).exists():
            return jsonify({'success': False, 'error': f'Monitor config file not found: {monitor_config_path}'})

        if not Path(data_config_path).exists():
            return jsonify({'success': False, 'error': f'Data config file not found: {data_config_path}'})

        # Load and validate monitor config
        with open(monitor_config_path) as f:
            monitor_config = json.load(f)

        # Load and validate data config
        with open(data_config_path) as f:
            data_config = json.load(f)

        logger.info(f"Successfully loaded configs for replay visualization")
        return jsonify({
            'success': True,
            'monitor_config': monitor_config,  # Full config for editing
            'data_config': data_config  # Full config for editing
        })

    except Exception as e:
        logger.error(f"Error loading configs: {e}")
        return jsonify({'success': False, 'error': str(e)})

@replay_bp.route('/api/save_config', methods=['POST'])
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

# Additional routes can be added here (download_config, etc.)
# Following the same pattern as the original replay_visualization/app.py