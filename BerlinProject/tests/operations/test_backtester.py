import unittest
from operations.backtester import Backtester
from mongo_tools.sample_tools import SampleTools


# class TestBacktester(unittest.TestCase):
#
#     def test_random_trader(self):
#         st = SampleTools.get_specific_sample("6701d819886b1284b27f3d6c")
#         bt = Backtester()
#
#         for tick in st.serve_next_tick():
#             bt.agent_actions([], tick)
#
#         self.assertEqual(len(bt.portfolio)-1, len(st.samples))

    # def test_model_trainer(self):
    #     st = SampleTools.get_specific_sample("6701d819886b1284b27f3d6c")
    #     bt = Backtester()
    #
    #     for tick in st.serve_next_tick():
    #         bt.agent_actions([], tick)
    #


