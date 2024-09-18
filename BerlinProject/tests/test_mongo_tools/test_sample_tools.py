import unittest
import json
from pathlib import Path
import numpy as np

from data_preprocessor.data_preprocessor import TickData
from mongo_tools.sample_tools import SampleTools


class TestSampleTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set up the file path and load the JSON data
        cls.file_path = Path('/home/warnd/devel/berlin/BerlinProject/tests/test_data/sample_tools_json_test.json')
        with open(cls.file_path, 'r') as file:
            cls.json_profile = json.load(file)

        # Create SampleTools instance
        cls.sample_tools = SampleTools.get_tools(cls.json_profile)

    def test_json_file_exists(self):
        """Test that the JSON file exists"""
        self.assertTrue(self.file_path.exists(), f"File not found: {self.file_path}")

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
