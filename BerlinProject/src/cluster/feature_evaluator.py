# The FeatureEvaluator will run through N samples and calculate the feature vectors and
# resulting reward.  This is aggregated into a set of points in FV + R dimensional space.
import numpy as np

from data_streamer import TickData, ExternalTool


class FeatureEvaluator(ExternalTool):

    def __init__(self):
        super().__init__()
        self.fv = []
        self.evaluation = []

    def feature_vector(self, fv: np.array, tick: TickData) -> bool:
        self.fv = fv
        # Tell the data streamer to continue to next function call:  present_sample
        return True

    def present_sample(self, sample: dict, index: int):
        # calculate the desirability of being in a position at this point in time
        # for fun, let's make that the max profit looking forward F steps - the max profile looking back B steps
        lookback = 19
        forward = 20
        data = sample['data']
        if len(data) < index + forward:
            return

        now_price = data[index].close
        back_price = data[index-lookback].close
        back_profit = (now_price - back_price) / now_price
        forward_prices = [d.close for d in data[index:index+forward]]
        forward_profit = (max(forward_prices) - now_price) / now_price
        self.evaluation.append(self.fv + [forward_profit*100.0] + [back_profit*100.0])





profile_data = [{
#    "profile_id": "6701cbcfbed728701fa3b767",
    "profile_id": "670d98f95c9ef9a75c7281de",
    "number": 2
}]

model_config = {
    "preprocess_config": "SMA",
    "normalization": "min_max",
    "action_space":
        {
            "type": "Discrete",
            "actions":
                {"1": "Buy",
                 "2": "Sell",
                 "0": "Hold"}
        }
    ,
    "state": {
        "klass": "SimplePosition"
    },
    "feature_vector_dim": 1,
    "feature_vector": [
        {
            "name": "SMADiff",
            "parameters": {
                "fast_period": 5,
                "slow_period": 20,
            },
        }
    ]
}
# from data_streamer import DataStreamer
# fe = FeatureEvaluator()
# streamer = DataStreamer(profile_data, model_config)
# streamer.connect_tool(fe)
# streamer.run()
