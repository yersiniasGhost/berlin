from mongo_tools.tick_history_tools import TickHistoryTools
from .feature_vector_calculator import FeatureVectorCalculator
from typing import List, Dict, Optional, Tuple
from mongo_tools.sample_tools import SampleTools
from .data_preprocessor import DataPreprocessor
from .indicator_processor import IndicatorProcessor
from models.indicator_configuration import IndicatorConfiguration
from data_streamer.external_tool import ExternalTool


class DataStreamer:
    def __init__(self, data_configuration: List[Dict], model_configuration: dict,
                 indicator_configuration: Optional[IndicatorConfiguration] = None):
        self.preprocessor = DataPreprocessor(model_configuration)
        self.feature_vector_calculator = FeatureVectorCalculator(model_configuration)
        self.indicators: Optional[IndicatorProcessor] = IndicatorProcessor(indicator_configuration) if indicator_configuration else None
        self.data_link: Optional[SampleTools] = None
        self.configure_data(data_configuration)
        self.external_tool: List[ExternalTool] = []

    def configure_data(self, data_config: List[Dict]) -> None:
        # TODO finish testing:
        if data_config.get('type', None) == "TickHistory":
            self.data_link = TickHistoryTools.get_history_data()
        else:
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
        index=0
        for tick in self.data_link.serve_next_tick():
            if tick:
                self.preprocessor.next_tick(tick)
                fv = self.feature_vector_calculator.next_tick(self.preprocessor)
                indicator_results = {}
                if self.indicators:
                    indicator_results = self.indicators.next_tick(self.preprocessor)

                if None not in fv:
                    for et in self.external_tool:
                        et.feature_vector(fv, tick)

                    s, i = self.get_present_sample()
                    for et in self.external_tool:
                        et.present_sample(s, i)
                    if indicator_results:
                        for et in self.external_tool:
                            et.indicator_vector(indicator_results, tick, index)
                index += 1
            else:
                index = 0
                for et in self.external_tool:
                    et.reset_next_sample()
                self.preprocessor.reset_state(sample_stats)

    def reset(self):
        self.data_link.reset_index()
        stats = self.data_link.get_stats()
        self.preprocessor.reset_state(stats)


    # Used for training of the RL Agents
    def get_next(self):
        if self.data_link is None:
            raise ValueError("Data link is not initialized")
        bad_fv = True
        while bad_fv:
            tick = self.data_link.get_next2()
            if tick is None:
                return [None], None
            self.preprocessor.next_tick(tick)
            fv = self.feature_vector_calculator.next_tick(self.preprocessor)
            bad_fv = None in fv

        return fv, tick

    def connect_tool(self, external_tool: ExternalTool) -> None:
        self.external_tool.append(external_tool)


    def get_present_sample(self) -> Tuple[dict, int]:
        if not isinstance(self.data_link, SampleTools):
            raise ValueError("Data link in data streamer is not SampleTools")
        return self.data_link.get_present_sample_and_index()
