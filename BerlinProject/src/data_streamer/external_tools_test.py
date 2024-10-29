import json
from typing import List, Dict, Optional, Union
from mongo_tools.sample_tools import SampleTools
from data_streamer import DataStreamer
from data_preprocessor.data_preprocessor import DataPreprocessor, TickData

class MockExternalTool():
    def __init__(self):
        self.cnt = 0
    def feature_vector(self, fv: List):
        self.cnt += 1

class TestExternalTool:

    def test_external_tool(self):
        data_config = {
            "SampleTools": {
                "Profiles": [ {"name": "TEST",  "number": 1} ]
            }
        }

        model_config = {
            "feature_vector": [
                {
                    "name": "close"
                }]
        }

        test_tool = MockExternalTool()
        ds = DataStreamer(data_config, model_config)
        ds.connect_tool(test_tool)
        ds.run()

        assert(test_tool.cnt == 360)