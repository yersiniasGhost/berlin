import os
import unittest
from mongo_tools.mongo import Mongo



class TestMongo(unittest.TestCase):

    def test_mongo(self):
        db = Mongo().database