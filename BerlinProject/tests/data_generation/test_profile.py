import os
import unittest
from pathlib import Path
from data_generation.profile import Profile


class TestProfile(unittest.TestCase):

    def get_data_file(self, file_name: str) -> Path:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        current_path = Path(current_dir)
        data_file = current_path / f"../test_data/{file_name}"
        return data_file


    def test_from_json(self):
        bad_file = self.get_data_file("doesnt_exist.json")
        with self.assertRaises(ValueError):
            Profile.from_json(bad_file)

        data_file = self.get_data_file("profile_test_01.json")
        profile = Profile.from_json(data_file)

        # test profile data
        self.assertIsNotNone(profile.profile_definition)
        self.assertIsInstance(profile.profile_definition, list)

    def test_get_sections(self):
        data_file = self.get_data_file("profile_test_01.json")
        profile = Profile.from_json(data_file)
        number_of_sections = 2
        self.assertTrue(len(profile.profile_definition) == number_of_sections)

        cnt = 0
        for section in profile.get_sections():
            self.assertIsNotNone(section)
            cnt += 1
        self.assertEqual(cnt, 2)

        self.assertTrue(profile.number_of_sections() == number_of_sections)





