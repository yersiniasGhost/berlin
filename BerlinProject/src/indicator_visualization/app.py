import os
import sys
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..'))

from optimization.calculators.yahoo_finance_historical import YahooFinanceHistorical
from models.monitor_configuration import MonitorConfiguration
from models.indicator_definition import IndicatorDefinition
from features.indicators import macd_calculation, sma_indicator
import talib
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('IndicatorVisualizerApp')

app = Flask(__name__)


class SimpleIndicatorVisualizer:
    def __init__(self):
        self.yahoo_finance = YahooFinanceHistorical()

    def load_and_process_data(self, ticker: str, start_date: str, end_date: str, indicator_configs: list):
        """Load data exactly like optimizer_visualization does"""
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
            return None, None, None

        # Get aggregators (same as optimizer)
        aggregators = self.yahoo_finance.aggregators

        # Get the main aggregator key (usually "1m-normal")
        main_key = None
        for key in aggregators.keys():
            if "1m" in key:
                main_key = key
                break

        if not main_key:
            main_key = list(aggregators.keys())[0]

        # Get candles from aggregator history
        candles = aggregators[main_key].history

        # Calculate RAW indicator values directly (not processed triggers)
        raw_indicator_values = self.calculate_raw_indicator_values(candles, indicator_configs)

        logger.info(f"Loaded {len(candles)} candles from {main_key}")
        logger.info(f"Calculated raw indicators: {list(raw_indicator_values.keys())}")

        return candles, raw_indicator_values, monitor_config

    def calculate_raw_indicator_values(self, candles, indicator_configs):
        """Calculate the actual raw indicator values AND trigger signals"""
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

                macd, signal_line, histogram = macd_calculation(tick_data_list, fast, slow, signal)

                # Get trigger signals (0s and 1s)
                from features.indicators import macd_histogram_crossover
                trigger_signals = macd_histogram_crossover(tick_data_list, parameters)

                # Store each component separately
                raw_values[f"{name}_macd"] = macd.tolist()
                raw_values[f"{name}_signal"] = signal_line.tolist()
                raw_values[f"{name}_histogram"] = histogram.tolist()
                raw_values[f"{name}_triggers"] = trigger_signals.tolist()

                logger.info(
                    f"MACD raw values calculated: MACD len={len(macd)}, Signal len={len(signal_line)}, Histogram len={len(histogram)}")
                logger.info(f"Trigger count: {sum(trigger_signals)} out of {len(trigger_signals)} total points")

            elif function == 'sma_crossover':
                period = parameters.get('period', 20)
                sma_values = sma_indicator(tick_data_list, period)

                # Get trigger signals (0s and 1s)
                from features.indicators import sma_crossover
                trigger_signals = sma_crossover(tick_data_list, parameters)

                raw_values[f"{name}_sma"] = sma_values.tolist()
                raw_values[f"{name}_triggers"] = trigger_signals.tolist()

                logger.info(f"SMA raw values calculated: len={len(sma_values)}")
                logger.info(f"SMA trigger count: {sum(trigger_signals)} out of {len(trigger_signals)} total points")

            # Add more indicator types as needed

        return raw_values


# Global visualizer instance
visualizer = SimpleIndicatorVisualizer()


@app.route('/')
def index():
    return render_template('main.html')


@app.route('/api/visualize', methods=['POST'])
def visualize_indicators():
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

        # Load data using the same method as optimizer_visualization
        candles, raw_indicators, monitor_config = visualizer.load_and_process_data(
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

        # Format indicator data for Highcharts
        indicators_data = {}
        for indicator_name, values in raw_indicators.items():
            # Create timestamp-value pairs for each indicator
            indicator_series = []
            for i, value in enumerate(values):
                if i < len(candles) and value is not None:
                    timestamp = int(candles[i].timestamp.timestamp() * 1000)
                    # Convert NaN to None for JSON serialization
                    if np.isnan(value) or str(value) == 'nan':
                        clean_value = None
                    else:
                        clean_value = float(value)

                    if clean_value is not None:
                        indicator_series.append([timestamp, clean_value])

            indicators_data[indicator_name] = {
                "data": indicator_series,
                "name": indicator_name
            }

        response = {
            "success": True,
            "ticker": ticker,
            "data": {
                "candlestick": candlestick_data,
                "indicators": indicators_data
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
    app.run(debug=True, host='0.0.0.0', port=5002)