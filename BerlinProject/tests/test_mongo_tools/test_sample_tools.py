import unittest
import json
from pathlib import Path
import numpy as np
from bson import ObjectId

from data_preprocessor.data_preprocessor import TickData
from mongo_tools.sample_tools import SampleTools


class TestSampleTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile_id = "6701cbcfbed728701fa3b767"
        json_profile = [{
            "profile_id": cls.profile_id,
            "number": 5
        }]

        # Create SampleTools instance
        cls.sample_tools = SampleTools.get_tools(json_profile)
        print(f"Number of samples in sample_tools: {len(cls.sample_tools.samples)}")

    def test_get_next2(self):
        data = SampleTools.get_samples2({"profile_id": self.profile_id, "number": 1})
        print(f"Number of samples: {len(data.samples)}")

        tick = data.get_next2()
        cnt = 0
        while tick:
            cnt += 1
            tick = data.get_next2()
        print(f"Number of ticks processed: {cnt}")
        self.assertEqual(cnt, sum(len(sample["ticks"]) for sample in data.samples))

    def test_get_samples2(self):
        b = SampleTools.get_samples2({"profile_id": self.profile_id, "number": 5})
        print(f"Number of samples: {len(b.samples)}")

        tick = b.get_next2()
        cnt = 0
        while tick:
            cnt += 1
            tick = b.get_next2()
        print(f"Number of ticks processed: {cnt}")
        self.assertEqual(cnt, sum(len(sample["ticks"]) for sample in b.samples))

    def test_get_stats(self):
        b = SampleTools.get_samples2({"profile_id": self.profile_id, "number": 5})

        for i in range(len(b.samples)):
            stats = b.get_stats()
            print(f"Stats for sample {i}: {stats}")

            self.assertIsNotNone(stats)
            self.assertIn('open', stats)
            self.assertIn('high', stats)
            self.assertIn('low', stats)
            self.assertIn('close', stats)

            for key in ['open', 'high', 'low', 'close']:
                self.assertIn('min', stats[key])
                self.assertIn('max', stats[key])
                self.assertIn('sd', stats[key])

            # Move to the next sample
            b.reset_index()
            b.sample_index = i + 1
