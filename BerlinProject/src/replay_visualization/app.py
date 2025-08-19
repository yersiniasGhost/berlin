import os
import sys
import json
import logging
from pathlib import Path
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
logger = logging.getLogger('MonitorVisualizationApp')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'monitor-viz-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")


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

        # Create monitor configuration object directly
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
        indicator_history, raw_indicator_history, bar_score_history_dict = (
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

        chart_data = {
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

        logger.info("✅ Successfully generated chart data")
        return chart_data

    except Exception as e:
        logger.error(f"❌ Error running monitor backtest: {e}")
        import traceback
        traceback.print_exc()
        raise


@app.route('/')
def index():
    """Main page for the monitor visualization app"""
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


@app.route('/api/run_visualization', methods=['POST'])
def run_visualization():
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

        return jsonify({
            'success': True,
            'chart_data': chart_data,
            'monitor_config': monitor_config,
            'data_config': data_config
        })

    except Exception as e:
        logger.error(f"Error running visualization: {e}")
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    # Create uploads directory if it doesn't exist
    uploads_dir = Path('uploads')
    uploads_dir.mkdir(exist_ok=True)
    logger.info(f"Created uploads directory: {uploads_dir.absolute()}")

    app.run(debug=True, host='0.0.0.0', port=5003)