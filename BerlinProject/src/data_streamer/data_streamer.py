import json
from typing import List, Dict, Optional, Union
from mongo_tools.sample_tools import SampleTools
from data_preprocessor.data_preprocessor import DataPreprocessor, TickData


class DataStreamer:

    def __init__(self, data_configuration: dict, model_configuration: dict):
        self.preprocessor = DataPreprocessor(model_configuration)
        self.data_link = Optional[SampleTools] = None
        self.data_configuration(data_configuration)

    def data_configuration(self, data_config: dict) -> None:
        if "SampleTools" in data_config.keys():
            profiles = data_config["SampleTools"]['Profiles']
            self.data_link = SampleTools.get_tools(profiles)

    def run(self):
        # Get the feature vector
        for tick in self.data_link.serve_next_tick():
            fv = self.preprocessor.next_tick(tick)
            # Send feature vector to the external tool
            self.external_tool.feature_vector(fv)

    def connect_tool(self, external_tool) -> None:
        self.external_tool = external_tool

    # def __init__(self, config_path: str):
    #     with open(config_path, 'r') as file:
    #         self.config = json.load(file)
    #     self.preprocessor = DataPreprocessor(self.config["ModelConfiguration"])
    #     self.data_link = Optional[SampleTools] = None
    #     self.load_configuration()
    #


    # config = {
    #     "SampleTools": {
    #         "Profiles": [ {"id": 12323, "number": 10, "randomize": True},
    #                       {"id": 123, "number": 230, "randomize": True}
    #                       ]
    #     },
    # "ModelConfiguration": {
    #
    # }
    # }

    def data_configuration(self, data_config: dict) -> None:
        if "SampleTools" in data_config.keys():
            profiles = data_config["SampleTools"]['Profiles']
            self.data_link = SampleTools.get_tools(profiles)


    # Run will use the data source (SampleData or DataLink)
    # and forward pre-calculated feature vectors to the external tool
    def run(self):
        # Get the feature vector
        for tick in self.data_link.serve_next_tick():
            fv = self.preprocessor.next_tick(tick)
            # Send feature vector to the external tool
            self.external_tool.feature_vector(fv)

    # def stream(self):
    #     for sample in self.samples:
    #         # Reset the preprocessor's state for each new sample
    #         self.preprocessor.reset_state()
    #
    #         for tick_data in sample['data']:
    #             tick = TickData(
    #                 open=tick_data['open'],
    #                 high=tick_data['high'],
    #                 low=tick_data['low'],
    #                 close=tick_data['close']
    #             )
    #             yield self.preprocessor.next_tick(tick)
    #
    def connect_tool(self, external_tool) -> None:
        self.external_tool = external_tool

