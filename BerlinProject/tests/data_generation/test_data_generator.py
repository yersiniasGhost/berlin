import os
import unittest
from pathlib import Path

from data_generation.profile import Profile
from data_generation.data_generator import DataGenerator


class TestDataGenerator(unittest.TestCase):

    def get_data_file(self, file_name: str) -> Path:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        current_path = Path(current_dir)
        data_file = current_path / f"../test_data/{file_name}"
        return data_file

    def test_construction(self):
        data_file = self.get_data_file("profile_test_01.json")
        profile = Profile.from_json(data_file)

        generator = DataGenerator(profile)
        self.assertIsNotNone(generator.profile)
        self.assertTrue(len(generator.data_profiles) == 0)

    def test_generate_simple_case(self):
        data_file = self.get_data_file("profile_test_01.json")
        profile = Profile.from_json(data_file)

        generator = DataGenerator(profile)
        number_of_profiles = 10
        length = 20
        start_price = 50

        self.assertTrue(len(generator.data_profiles) == 0)
        generator.generate_data(number_of_profiles, length, start_price)
        self.assertTrue(len(generator.data_profiles) == number_of_profiles)
        for p in generator.get_profiles():
            self.assertEqual(len(p), length)
            self.assertAlmostEqual(p[0], start_price)


    def test_generate_next_simple_case(self):
        data_file = self.get_data_file("profile_test_02.json")
        profile = Profile.from_json(data_file)

        generator = DataGenerator(profile)
        number_of_profiles = 2
        length = 20
        start_price = 50

        self.assertTrue(len(generator.data_profiles) == 0)
        generator.generate_data(number_of_profiles, length, start_price)
        self.assertTrue(len(generator.data_profiles) == number_of_profiles)

        profiles = generator.data_profiles
        self.assertTrue(profiles[0][-1] != profiles[1][-1])


    def test_consistent_profile_lengths(self):
        data_file = self.get_data_file("profile_test_03.json")

        # Create a Profile instance using the class method
        profile = Profile.from_json(data_file)

        # Now create the DataGenerator with the profile instance
        generator = DataGenerator(profile)

        number_of_profiles = 2
        length = 100
        start_price = 50

        # Now you can call generate_data
        generator.generate_data(number_of_profiles, length, start_price)
        for p in generator.get_profiles():
            self.assertEqual(len(p), length)

