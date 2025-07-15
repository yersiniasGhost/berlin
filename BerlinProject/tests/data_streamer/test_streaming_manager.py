import os, sys, json, logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SimpleTest')

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..', 'src'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from data_streamer.candle_aggregator import CandleAggregator
from data_streamer.data_streamer import DataStreamer
from models.monitor_configuration import MonitorConfiguration
from models.indicator_definition import IndicatorDefinition
from models.tick_data import TickData


def load_monitor_config():
    config_path = '../../src/stock_analysis_ui/monitor_config_example_time_intervals.json'
    with open(config_path, 'r') as f:
        config_data = json.load(f)

    indicators = [IndicatorDefinition(
        name=ind['name'], type=ind['type'], function=ind['function'],
        parameters=ind['parameters'], time_increment=ind.get('time_increment', '1m')
    ) for ind in config_data['indicators']]

    return MonitorConfiguration(name="test_monitor", indicators=indicators)


def load_historical_data(filename):
    tick_data = []
    with open(filename, 'r') as f:
        for line in f.readlines()[1:]:
            parts = line.strip().split(',')
            if len(parts) >= 7:
                timestamp = datetime.fromtimestamp(int(parts[0]) / 1000)
                tick = TickData(
                    symbol=parts[6] if len(parts) > 6 else "NVDA",
                    timestamp=timestamp, open=float(parts[2]), high=float(parts[3]),
                    low=float(parts[4]), close=float(parts[5]),
                    volume=int(float(parts[6]) if len(parts) > 6 else 0), time_increment="1m"
                )
                tick_data.append(tick)
    logger.info(f"Loaded {len(tick_data)} historical candles")
    return tick_data


def load_pip_data(filename):
    try:
        with open(filename, 'r') as f:
            pip_data = [json.loads(line.strip().rstrip(',')) for line in f if line.strip()]
    except:
        with open(filename, 'r') as f:
            pip_data = json.load(f)
    logger.info(f"Loaded {len(pip_data)} PIP records")
    return pip_data


class SimpleExternalTool:
    def __init__(self):
        self.update_count = 0

    def indicator_vector(self, indicators, tick, index, raw_indicators=None):
        self.update_count += 1
        logger.info(f"Update #{self.update_count} - Indicators: {indicators}")

    def feature_vector(self, fv, tick):
        pass


def run_test():
    symbol = "NVDA"

    monitor_config = load_monitor_config()
    logger.info(f"Loaded monitor with {len(monitor_config.indicators)} indicators")

    aggregator = CandleAggregator(symbol, "1m")

    historical_data = load_historical_data("NVDA_1m_data_20250522.txt")
    aggregator.history = historical_data[:-1]
    aggregator.current_candle = historical_data[-1]
    logger.info(f"Prepopulated with {len(aggregator.history)} candles")

    model_config = {"feature_vector": [{"name": "close"}]}
    data_streamer = DataStreamer(model_config, monitor_config)

    tool = SimpleExternalTool()
    data_streamer.connect_tool(tool)

    aggregators = {"1m": aggregator}
    data_streamer.process_tick(aggregators)

    pip_data = load_pip_data("../../tests/data_streamer/quote_data/NVDA_quotes2.txt")
    logger.info("Processing PIP data...")

    for i, pip in enumerate(pip_data[:1000]):
        aggregator.process_pip(pip)
        data_streamer.process_tick(aggregators)

        if (i + 1) % 20 == 0:
            logger.info(f"Processed {i + 1} PIPs")

    logger.info(f"Test complete. Total indicator updates: {tool.update_count}")


if __name__ == "__main__":
    run_test()