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
from data_streamer.indicator_processor import IndicatorProcessor
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('IndicatorVisualizerApp')

app = Flask(__name__)


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
    app.run(debug=True, host='0.0.0.0', port=5002)