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
        stats = self.data_link.get_stats()
        self.preprocessor.reset_state(stats)

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

