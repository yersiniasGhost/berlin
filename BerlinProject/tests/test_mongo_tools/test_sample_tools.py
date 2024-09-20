import unittest
import json
from pathlib import Path
import numpy as np

from data_preprocessor.data_preprocessor import TickData
from mongo_tools.sample_tools import SampleTools


class TestSampleTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        json_profile = [{
            "profile_id": "66e3499280c8e93a7756fbd1",
            "number": 5
        },
            {
                "profile_id": "66e34a036bf640360fdd7326",
                "number": 2
            }]

        # Create SampleTools instance
        cls.sample_tools = SampleTools.get_tools(json_profile)


    def test_tick_count_equals_700(self):
        """Test that the total number of ticks equals 700"""
        count = sum(1 for _ in self.sample_tools.serve_next_tick())
        self.assertEqual(count, 700, f"Expected 700 ticks, but got {count}")

    def test_tick_data_structure(self):
        """Test that each tick has the correct data structure"""
        for tick in self.sample_tools.serve_next_tick():
            self.assertIsInstance(tick, TickData)  # Assuming TickData is the class used
            self.assertTrue(hasattr(tick, 'open'))
            self.assertTrue(hasattr(tick, 'high'))
            self.assertTrue(hasattr(tick, 'low'))
            self.assertTrue(hasattr(tick, 'close'))


    def test_get_specific_sample(self):

        data = SampleTools.get_specific_sample("66e1f09f7c6789752c190ca0")
        samples = data.samples
        self.assertEqual(len(samples), 100)

    def test_get_next(self):

        data = SampleTools.get_specific_sample("66e1f09f7c6789752c190ca0")
        tick = data.get_next()
        cnt = 0
        while (tick):
            cnt += 1
            tick = data.get_next()
        self.assertEqual(cnt, len(data.samples))





