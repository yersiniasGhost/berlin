import unittest
from operations import Backtester
from data_streamer import TickData
from mongo_tools import SampleTools

class TestBacktester(unittest.TestCase):

    def test_random_trader(self):
        st = SampleTools.get_specific_samples(["66e1f09f7c6789752c190ca0"])
        bt = Backtester()

        for tick in st.server_next_tick():
            bt.agent_actions([], tick)

        self.assertEqual(len(bt.portfolio)-1, len(st.samples))


    pass

