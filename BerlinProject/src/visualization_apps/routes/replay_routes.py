"""
Replay Visualization Routes
Handles monitor configuration visualization with backtest execution
"""

from flask import Blueprint, render_template, request, jsonify
import os
import sys
import json
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

# Import mlf_utils
from mlf_utils import sanitize_nan_values, FileUploadHandler, ConfigLoader
from mlf_utils.log_manager import LogManager

# Remove new indicator system imports that are causing backend conflicts
# from indicator_triggers.indicator_base import IndicatorRegistry
# from indicator_triggers.refactored_indicators import *  # Import to register indicators

logger = LogManager().get_logger("ReplayVisualization")

# Create Blueprint
replay_bp = Blueprint('replay', __name__, url_prefix='/replay')

# Create upload handler for replay routes
upload_handler = FileUploadHandler(upload_dir='uploads')

def load_raw_candle_data(data_config_path: str, io):
    """Load raw candlestick data from MongoDB using the same data as trade execution"""
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
    """Extract trade history, triggers, P&L history, bar scores, and trade details from portfolio"""
    logger.info("💼 Extracting trade history and P&L from portfolio")

    trade_history = []
    triggers = []
    pnl_history = []
    bar_scores_history = []
    trade_details = {}  # Detailed trade info for UI popup

    # Get trade details from the executor if available
    if hasattr(backtest_streamer, 'trade_executor') and backtest_streamer.trade_executor:
        trade_details = backtest_streamer.trade_executor.trade_details_history or {}

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

    return trade_history, triggers, pnl_history, bar_scores_history, trade_details

def run_monitor_backtest(monitor_config_path: str, data_config_path: str):
    """Run backtest with the provided monitor configuration using the old working method"""
    logger.info("🔍 Running monitor backtest for visualization")

    validation_errors = []  # Track validation errors from indicators

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

        backtest_streamer = BacktestDataStreamer()
        backtest_streamer.initialize(mongo_source.get_all_aggregators(), data_config, monitor_obj)

        # Calculate indicators and bar scores using the monitor configuration
        from optimization.calculators.indicator_processor_historical_new import IndicatorProcessorHistoricalNew

        try:
            indicator_processor = IndicatorProcessorHistoricalNew(monitor_obj)
            indicator_history, raw_indicator_history, bar_score_history_dict, component_history, indicator_agg_mapping = (
                indicator_processor.calculate_indicators(backtest_streamer.aggregators)
            )
        except ValueError as val_err:
            # Capture parameter validation errors
            error_msg = str(val_err)
            logger.error(f"❌ Parameter validation error: {error_msg}")

            # Extract indicator name and error details from the validation error message
            # Error format: "Parameter validation failed for SMACrossoverIndicator:\n  • Missing required parameter: 'trend'\n  • ..."
            if "Parameter validation failed for" in error_msg:
                validation_errors.append(error_msg)
            else:
                validation_errors.append(f"Indicator validation error: {error_msg}")

            # If there are validation errors, raise them so they get returned to the UI
            raise ValueError(f"Configuration validation failed: {validation_errors}")

        # Store the bar score history for later access
        backtest_streamer.bar_score_history_dict = bar_score_history_dict

        # Run the backtest to get trades
        portfolio = backtest_streamer.run()

        # Load raw candle data for visualization (primary 1m timeframe for trade overlay)
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

        logger.info(f"📈 Loaded {len(candlestick_data)} candles (primary timeframe)")

        # Get per-aggregator candlestick data for indicator charts
        # Each indicator chart needs candles from its own timeframe/type (e.g., 5m-heiken)
        per_aggregator_candles = backtest_streamer.get_all_candlestick_data()
        logger.info(f"📊 Prepared candles for {len(per_aggregator_candles)} aggregators: {list(per_aggregator_candles.keys())}")

        # Extract trade history and P&L from the fresh portfolio
        trade_history, triggers, pnl_history, bar_scores_history, trade_details = extract_trade_history_and_pnl_from_portfolio(
            portfolio, backtest_streamer)

        # Get threshold config for bar charts
        threshold_config = {
            'enter_long': monitor_config.get('enter_long', []),
            'exit_long': monitor_config.get('exit_long', [])
        }

        # Format raw_indicator_history (trigger values: 0, 1) for frontend
        # Uses native aggregator timestamps for each indicator
        raw_indicator_history_formatted = {}
        if raw_indicator_history:
            for ind_name, ind_values in raw_indicator_history.items():
                # Get the aggregator key for this indicator
                agg_key = indicator_agg_mapping.get(ind_name)
                if agg_key:
                    timestamps = backtest_streamer.get_aggregator_timestamps(agg_key)
                else:
                    # Fallback to primary timeframe
                    timestamps = [int(tick.timestamp.timestamp() * 1000) for tick in tick_history]

                series = []
                for i, value in enumerate(ind_values):
                    if i < len(timestamps) and value is not None:
                        series.append([timestamps[i], float(value)])
                raw_indicator_history_formatted[ind_name] = series
                logger.debug(f"📈 Raw indicator '{ind_name}' formatted with {len(series)} points from {agg_key or 'primary'}")

        # Format indicator_history (time-decayed values: 1, 0.9, 0.8, etc.) for frontend
        # Uses native aggregator timestamps for each indicator
        indicator_history_formatted = {}
        if indicator_history:
            for ind_name, ind_values in indicator_history.items():
                # Get the aggregator key for this indicator
                agg_key = indicator_agg_mapping.get(ind_name)
                if agg_key:
                    timestamps = backtest_streamer.get_aggregator_timestamps(agg_key)
                else:
                    # Fallback to primary timeframe
                    timestamps = [int(tick.timestamp.timestamp() * 1000) for tick in tick_history]

                series = []
                for i, value in enumerate(ind_values):
                    if i < len(timestamps) and value is not None:
                        series.append([timestamps[i], float(value)])
                indicator_history_formatted[ind_name] = series
                logger.debug(f"📈 Indicator '{ind_name}' formatted with {len(series)} points from {agg_key or 'primary'}")

        # Format component_history (MACD line, signal, histogram, SMA values) for frontend
        # Use the indicator's native aggregator timestamps (not primary 1m timeframe)
        component_history_formatted = {}
        if component_history:
            for comp_name, comp_values in component_history.items():
                # Extract indicator name from component name (e.g., "macd5m_macd" -> "macd5m")
                indicator_name = comp_name.rsplit('_', 1)[0] if '_' in comp_name else comp_name

                # Get the aggregator key for this indicator
                agg_key = indicator_agg_mapping.get(indicator_name)
                if not agg_key:
                    # Fallback: try to find matching indicator name
                    for ind_name, key in indicator_agg_mapping.items():
                        if ind_name in comp_name or comp_name.startswith(ind_name):
                            agg_key = key
                            break

                # Get timestamps from the correct aggregator
                if agg_key:
                    timestamps = backtest_streamer.get_aggregator_timestamps(agg_key)
                else:
                    # Fallback to primary timeframe if no mapping found
                    timestamps = [int(tick.timestamp.timestamp() * 1000) for tick in tick_history]
                    logger.warning(f"⚠️ No aggregator mapping for component '{comp_name}', using primary timeframe")

                series = []
                for i, value in enumerate(comp_values):
                    if i < len(timestamps) and value is not None:
                        series.append([timestamps[i], float(value)])
                component_history_formatted[comp_name] = series
                logger.debug(f"📈 Component '{comp_name}' formatted with {len(series)} points from {agg_key}")


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
        
        # Build class name to layout type mapping
        # Maps from CLASS NAME (e.g., "MACDHistogramCrossoverIndicator") to LAYOUT TYPE
        class_to_layout = {}
        try:
            # Ensure indicators are registered
            import indicator_triggers.refactored_indicators  # This imports and registers indicators
            from indicator_triggers.indicator_base import IndicatorRegistry
            registry = IndicatorRegistry()

            for indicator in indicators:
                indicator_class_name = indicator.get('indicator_class', '')

                if indicator_class_name and indicator_class_name not in class_to_layout:
                    try:
                        indicator_cls = registry.get_indicator_class(indicator_class_name)
                        layout_type = indicator_cls.get_layout_type()
                        class_to_layout[indicator_class_name] = layout_type
                        logger.debug(f"📊 Class '{indicator_class_name}' → layout: {layout_type}")
                    except ValueError as ve:
                        class_to_layout[indicator_class_name] = 'overlay'
                        logger.warning(f"⚠️ Class '{indicator_class_name}' not found, using default 'overlay'")
        except Exception as e:
            logger.warning(f"Could not build class to layout mapping: {e}")
            # Build default mapping
            for indicator in indicators:
                indicator_class_name = indicator.get('indicator_class', '')
                if indicator_class_name and indicator_class_name not in class_to_layout:
                    layout_type = 'stacked' if 'macd' in indicator_class_name.lower() else 'overlay'
                    class_to_layout[indicator_class_name] = layout_type

        chart_data = {
            'ticker': data_config['ticker'],
            'candlestick_data': candlestick_data,  # Primary timeframe (1m) for trade overlay
            'per_aggregator_candles': per_aggregator_candles,  # All timeframes for indicator charts
            'indicator_agg_mapping': indicator_agg_mapping,  # indicator_name -> agg_config
            'triggers': triggers,
            'trades': trades_with_pnl,  # Frontend expects 'trades' with pnl property
            'trade_history': trade_history,  # Keep for backwards compatibility
            'trade_details': trade_details,  # Detailed trade info for popup (timestamp -> details dict)
            'pnl_history': pnl_history,
            'pnl_data': pnl_data,  # Frontend expects 'pnl_data' for charting
            'raw_indicator_history': raw_indicator_history_formatted,  # Raw trigger values (0, 1)
            'indicator_history': indicator_history_formatted,  # Time-decayed values (1, 0.9, 0.8, etc.)
            'component_history': component_history_formatted,  # MACD components, SMA values, etc.
            'class_to_layout': class_to_layout,  # Class name → layout type (stacked or overlay)
            'indicators': indicators,  # Include indicators config for frontend
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

        # Return validation errors if any were collected
        if validation_errors:
            # Parse validation errors for better formatting
            error_details = {
                'main_error': str(e),
                'validation_errors': validation_errors,
                'has_validation_errors': True
            }
            raise ValueError(json.dumps(error_details))
        else:
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
        file = request.files.get('file')
        file_type = request.form.get('config_type', 'unknown')

        # Use FileUploadHandler for validation and saving
        result = upload_handler.save_file(file, prefix=file_type)

        if result['success']:
            result['type'] = file_type  # Add type to response

        return jsonify(result)

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

        # Check if error contains validation error details (JSON string)
        error_str = str(e)
        try:
            if error_str.startswith('{'):
                error_details = json.loads(error_str)
                if error_details.get('has_validation_errors'):
                    # Return structured error with validation details
                    return jsonify({
                        'success': False,
                        'error': 'Configuration validation failed',
                        'validation_errors': error_details.get('validation_errors', []),
                        'has_validation_errors': True
                    })
        except:
            pass

        return jsonify({'success': False, 'error': error_str})

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

@replay_bp.route('/api/run_replay', methods=['POST'])
def run_replay():
    """Run replay visualization with the new compact UI"""
    try:
        data = request.get_json()
        monitor_config = data.get('monitor_config')
        data_config = data.get('data_config')

        if not monitor_config or not data_config:
            return jsonify({'success': False, 'error': 'Both configurations are required'})

        # Create temporary files for the configs
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='_monitor_config.json', delete=False) as monitor_file:
            json.dump(monitor_config, monitor_file, indent=2)
            monitor_config_path = monitor_file.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='_data_config.json', delete=False) as data_file:
            json.dump(data_config, data_file, indent=2)
            data_config_path = data_file.name

        try:
            # Run the backtest
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
                pass

    except Exception as e:
        logger.error(f"Error running replay: {e}")
        import traceback
        traceback.print_exc()

        # Check if error contains validation error details (JSON string)
        error_str = str(e)
        try:
            if error_str.startswith('{'):
                error_details = json.loads(error_str)
                if error_details.get('has_validation_errors'):
                    # Return structured error with validation details
                    return jsonify({
                        'success': False,
                        'error': 'Configuration validation failed',
                        'validation_errors': error_details.get('validation_errors', []),
                        'has_validation_errors': True
                    })
        except:
            pass

        return jsonify({'success': False, 'error': error_str})

@replay_bp.route('/api/indicator_schemas', methods=['GET'])
def get_indicator_schemas():
    """Get all indicator schemas with their required fields"""
    try:
        # Late import to avoid conflicts at module load time
        import indicator_triggers.refactored_indicators  # This imports and registers indicators
        from indicator_triggers.indicator_base import IndicatorRegistry

        registry = IndicatorRegistry()
        schemas = registry.get_ui_schemas()

        # Format schemas for UI consumption
        formatted_schemas = {}
        for indicator_name, schema in schemas.items():
            formatted_schemas[indicator_name] = {
                'name': schema.get('indicator_name', indicator_name),
                'display_name': schema.get('display_name', indicator_name),
                'description': schema.get('description', ''),
                'layout_type': schema.get('layout_type', 'overlay'),
                'parameter_specs': schema.get('parameter_specs', [])
            }

        return jsonify({
            'success': True,
            'schemas': formatted_schemas
        })

    except ImportError as ie:
        logger.warning(f"Could not import indicator system: {ie}")
        return jsonify({
            'success': False,
            'error': f'Indicator system not available: {str(ie)}'
        })
    except Exception as e:
        logger.error(f"Error getting indicator schemas: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })


# Additional routes can be added here (download_config, etc.)
# Following the same pattern as the original replay_visualization/app.py