import unittest
from models import IndicatorConfiguration
from data_streamer.indicator_processor import IndicatorProcessor
from config.types import CANDLE_STICK_PATTERN
from environments.tick_data import TickData


class TestIndicatorProcessor(unittest.TestCase):

    def test_single_candle(self):
        indicators = [
            {"name": "Three Black Crows", "parameters": {"talib": "CDL3BLACKCROWS"},"type": CANDLE_STICK_PATTERN},
        {"name": "Hammer pattern", "parameters": {"talib": "CDLHAMMER"}, "type": CANDLE_STICK_PATTERN}]
        config = {"name": "CDL Test", "indicators": indicators}
        config = IndicatorConfiguration(**config)

        processor = IndicatorProcessor(config)

        # Create simple data
        history = [
            TickData(open=1.20, high=1.22, low=1.14, close=1.15),  # First black candle
            TickData(open=1.15, high=1.16, low=1.10, close=1.11),  # Second black candle
            TickData(open=1.11, high=1.12, low=1.05, close=1.06)  # Third black candle
        ]
        tick = TickData(open=1.05, high=1.06, low=0.95, close=1.04)  # CDLHAMMER
        result = processor.calculate_vector(tick, history)
        # test result



    # def test_model_trainer(self):
    #     st = SampleTools.get_specific_sample("6701d819886b1284b27f3d6c")
    #     bt = Backtester()
    #
    #     for tick in st.serve_next_tick():
    #         bt.agent_actions([], tick)
    #
