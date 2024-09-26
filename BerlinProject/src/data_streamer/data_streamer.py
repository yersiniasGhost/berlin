import json
from typing import List, Dict, Optional, Union, Tuple
from mongo_tools.sample_tools import SampleTools
from data_preprocessor.data_preprocessor import DataPreprocessor
from data_streamer.external_tool import ExternalTool


class DataStreamer:
    def __init__(self, data_configuration: List[Dict], model_configuration: dict):
        self.preprocessor = DataPreprocessor(model_configuration)
        self.data_link: Optional[SampleTools] = None
        self.configure_data(data_configuration)
        self.external_tool: Optional[ExternalTool] = None

    def configure_data(self, data_config: List[Dict]) -> None:
        self.data_link = SampleTools.get_samples2(data_config[0])

    def run(self):
        if self.data_link is None:
            raise ValueError("Data link is not initialized")
        if self.external_tool is None:
            raise ValueError("External tool is not connected")

        for tick in self.data_link.serve_next_tick():
            fv = self.preprocessor.next_tick(tick)
            self.external_tool.feature_vector(fv)

    def reset(self):
        self.data_link.reset_index()

    def get_next(self):
        if self.data_link is None:
            raise ValueError("Data link is not initialized")
        tick = self.data_link.get_next2()
        if tick is None:
            return None, None
        fv = self.preprocessor.next_tick(tick)
        return fv, tick

    def connect_tool(self, external_tool: ExternalTool) -> None:
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


    # Run will use the data source (SampleData or DataLink)
    # and forward pre-calculated feature vectors to the external tool

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
