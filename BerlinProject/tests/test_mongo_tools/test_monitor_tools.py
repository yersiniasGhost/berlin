import unittest
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

from bson import ObjectId
from config.types import PYMONGO_ID, MONITOR_COLLECTION, PyObjectId
from models.monitor_model import Monitor
from pymongo.collection import Collection
from mongo_tools.mongo import Mongo
import json
from mongo_tools.monitor_tools import MonitorTools


class TestMonitorTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Sample monitor data for testing
        cls.sample_monitor = Monitor(
            name="test_monitor",
            user_id=ObjectId(),
            description="Test description",
            triggers=[{ObjectId(): 5}, {ObjectId(): 7}],
            candles={"Hammer": 4}
        )

        # Create a mock MongoDB collection
        cls.mock_collection = MagicMock()

        # Patch the get_collection method
        cls.patcher = patch.object(MonitorTools, 'get_collection', return_value=cls.mock_collection)
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    def setUp(self):
        # Reset mock collection before each test
        self.mock_collection.reset_mock()

    def test_create_monitor(self):
        """Test creating a new monitor"""
        # Setup mock
        self.mock_collection.find_one.return_value = None
        self.mock_collection.insert_one.return_value.inserted_id = ObjectId()

        # Create monitor
        MonitorTools.create_monitor(self.sample_monitor)

        # Assertions
        self.mock_collection.find_one.assert_called_once()
        self.mock_collection.insert_one.assert_called_once()
        self.assertIsNotNone(self.sample_monitor.id)

    def test_create_monitor_duplicate(self):
        """Test creating a monitor with duplicate name fails"""
        # Setup mock to simulate existing monitor
        self.mock_collection.find_one.return_value = {"name": self.sample_monitor.name}

        # Assert raises
        with self.assertRaises(ValueError) as context:
            MonitorTools.create_monitor(self.sample_monitor)

        self.assertIn("already", str(context.exception))

    def test_get_profile(self):
        """Test getting a monitor profile"""
        # Setup mock
        mock_data = self.sample_monitor.dict()
        self.mock_collection.find_one.return_value = mock_data

        # Get profile
        result = MonitorTools.get_profile("test_monitor")

        # Assertions
        self.assertIsInstance(result, Monitor)
        self.assertEqual(result.name, self.sample_monitor.name)
        self.mock_collection.find_one.assert_called_once()

    def test_list_profiles(self):
        """Test listing all profiles"""
        # Setup mock
        mock_profiles = [
            {"_id": ObjectId(), "name": "profile1"},
            {"_id": ObjectId(), "name": "profile2"}
        ]
        self.mock_collection.find.return_value = mock_profiles

        # Get profiles
        result = MonitorTools.list_profiles()

        # Assertions
        self.assertEqual(len(result), 2)
        self.mock_collection.find.assert_called_once()
        self.assertEqual(result, mock_profiles)

    def test_update_profile(self):
        """Test updating a monitor profile"""
        # Setup mock
        self.mock_collection.update_one.return_value.modified_count = 1

        # Update profile
        result = MonitorTools.update_profile(self.sample_monitor)

        # Assertions
        self.assertTrue(result)
        self.mock_collection.update_one.assert_called_once()

    def test_update_profile_no_changes(self):
        """Test updating a monitor profile with no changes"""
        # Setup mock
        self.mock_collection.update_one.return_value.modified_count = 0

        # Update profile
        result = MonitorTools.update_profile(self.sample_monitor)

        # Assertions
        self.assertFalse(result)
        self.mock_collection.update_one.assert_called_once()

    def test_update_profile(self):
        """Test updating a monitor profile"""
        # Create test monitor
        test_monitor = Monitor(
            id=ObjectId(),
            name="test_monitor",
            user_id=ObjectId(),
            description="Original description",
            triggers=[{ObjectId(): 0.5}],
            candles={"1h": 0.1}
        )

        # Setup mock
        self.mock_collection.update_one.return_value.modified_count = 1

        # Update monitor with new description
        test_monitor.description = "Updated description"
        result = MonitorTools.update_profile(test_monitor)

        # Assertions
        self.assertTrue(result)  # Check update was successful
        self.mock_collection.update_one.assert_called_once()

        # Check the update was called with correct parameters
        call_args = self.mock_collection.update_one.call_args
        filter_dict, update_dict = call_args[0]  # Get the positional arguments

        self.assertEqual(filter_dict, {"_id": test_monitor.id})
        self.assertIn("$set", update_dict)
        self.assertEqual(update_dict["$set"]["description"], "Updated description")
        self.assertNotIn("_id", update_dict["$set"])  # Verify _id was removed from update
