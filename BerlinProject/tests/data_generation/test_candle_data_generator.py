import os
import unittest
from pathlib import Path

from data_generation.profile import Profile
from data_generation.candle_data_generator import CandleDataGenerator


class TestDataGenerator(unittest.TestCase):

    def get_data_file(self, file_name: str) -> Path:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        current_path = Path(current_dir)
        data_file = current_path / f"../test_data/{file_name}"
        return data_file

    def test_construction(self):
        data_file = self.get_data_file("candle_profile_test_01.json")
        profile = Profile.from_json(data_file)

        generator = CandleDataGenerator(profile)
        self.assertIsNotNone(generator.profile)
        self.assertTrue(len(generator.data_profiles) == 0)

    def test_generate_simple_case(self):
        data_file = self.get_data_file("candle_profile_test_01.json")
        profile = Profile.from_json(data_file)

        generator = CandleDataGenerator(profile)
        number_of_profiles = 10
        length = 20
        start_price = 50
        open_factor = .005
        high_factor = .005
        low_factor = .005

        self.assertEqual(len(generator.data_profiles), 0)
        generator.generate_data(number_of_profiles, length, start_price, open_factor, high_factor, low_factor)
        self.assertEqual(len(generator.data_profiles), number_of_profiles)

        for p in generator.get_profiles():
            self.assertEqual(len(p), length)

            # Check the structure of the first candle
            first_candle = p[0]
            self.assertEqual(len(first_candle), 4)  # Should have 4 values: open, high, low, close

            # Check if high is the highest and low is the lowest for each candle
            for candle in p:
                open, high, low, close = candle
                self.assertGreaterEqual(high, max(open, close))
                self.assertLessEqual(low, min(open, close))

    def test_generate_next_simple_case(self):
        data_file = self.get_data_file("candle_profile_test_01.json")
        profile = Profile.from_json(data_file)

        generator = CandleDataGenerator(profile)
        number_of_profiles = 2
        length = 20
        start_price = 50
        open_factor = .005
        high_factor = .005
        low_factor = .005

        self.assertTrue(len(generator.data_profiles) == 0)
        generator.generate_data(number_of_profiles, length, start_price, open_factor, high_factor, low_factor)
        self.assertTrue(len(generator.data_profiles) == number_of_profiles)

        profiles = generator.data_profiles
        self.assertTrue(profiles[0][-1] != profiles[1][-1])

    def test_consistent_profile_lengths(self):
        data_file = self.get_data_file("candle_profile_test_01.json")

        # Create a Profile instance using the class method
        profile = Profile.from_json(data_file)

        # Now create the DataGenerator with the profile instance
        generator = CandleDataGenerator(profile)

        number_of_profiles = 2
        length = 100
        start_price = 50
        open_factor = .005
        high_factor = .005
        low_factor = .005

        # Now you can call generate_data
        generator.generate_data(number_of_profiles, length, start_price, open_factor, high_factor, low_factor)
        for p in generator.get_profiles():
            self.assertEqual(len(p), length)

