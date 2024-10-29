from typing import List, Dict, Optional, Tuple
from mongo_tools.sample_tools import SampleTools
from .data_preprocessor import DataPreprocessor
from .indicator_processor import IndicatorProcessor
from models.monitor_configuration import MonitorConfiguration
from data_streamer.external_tool import ExternalTool


class DataStreamer:
    def __init__(self, data_configuration: List[Dict], model_configuration: dict,
                 indicator_configuration: Optional[MonitorConfiguration] = None):
        self.preprocessor = DataPreprocessor(model_configuration)
        self.indicators: Optional[IndicatorProcessor] = IndicatorProcessor(indicator_configuration) if indicator_configuration else None
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

        # Set the sample state on the data preprocessor so it can
        # normalize the data.
        sample_stats = self.data_link.get_stats()
        self.preprocessor.reset_state(sample_stats)
        for tick in self.data_link.serve_next_tick():
            if tick:
                fv = self.preprocessor.next_tick(tick)
                indicator_results = {}
                if self.indicators:
                    indicator_results = self.indicators.next_tick(tick, self.preprocessor.history)


                if None not in fv:
                    send_sample = self.external_tool.feature_vector(fv, tick)
                    if send_sample:
                        s, i = self.get_present_sample()
                        self.external_tool.present_sample(s, i)
                    if indicator_results:
                        self.external_tool.indicator_vector(indicator_results, tick)

            else:
                self.external_tool.reset_next_sample()
                self.preprocessor.reset_state(sample_stats)

    def reset(self):
        self.data_link.reset_index()
        stats = self.data_link.get_stats()
        self.preprocessor.reset_state(stats)

    def get_next(self):
        if self.data_link is None:
            raise ValueError("Data link is not initialized")
        bad_fv = True
        while bad_fv:
            tick = self.data_link.get_next2()
            if tick is None:
                return [None], None
            fv = self.preprocessor.next_tick(tick)
            bad_fv = None in fv

        return fv, tick

    def connect_tool(self, external_tool: ExternalTool) -> None:
        self.external_tool = external_tool

    def get_present_sample(self) -> Tuple[dict, int]:
        if not isinstance(self.data_link, SampleTools):
            raise ValueError("Data link in data streamer is not SampleTools")
        return self.data_link.get_present_sample_and_index()
