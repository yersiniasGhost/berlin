from operations.runtime_analytics import RuntimeAnalytics
from data_streamer.data_streamer_orig import DataStreamer
from operations.backtester import Backtester

profile_data = [{
    "profile_id": "6701cbcfbed728701fa3b767",
    "number": 2
}]

model_path = "/home/warnd/devel/berlin/BerlinProject/labs/saved_models/macd_model2.zip"

model_config = {
    "preprocess_config": "macd_norm_discrete_3",
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
    "feature_vector_dim": 3,
    "feature_vector": [
        {
            "name": "MACD",
            "history": 2,
            "parameters": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9
            },
        },{
            "name": "close",
            "history": 3
        }
    ]
}

in_out_model = {
    "preprocess_config": "macd_norm_discrete_3",
    "normalization": "min_max",
    "action_space":
        {
            "type": "NormalBox",
            "actions":
                {"1": "In",
                 "0": "Out"
                 }
        }
    ,
    "state": {
        "klass": "InoutPosition",
        "parameters": {"reward_type": "x"}
    },
    "feature_vector_dim": 12,
    "feature_vector": [
        {
            "name": "MACD",
            "history": 2,
            "parameters": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9
            }
        }, {
            "name": "close",
            "history": 3
        }
    ]
}

bt = Backtester()
rt = RuntimeAnalytics(model_config, model_path)
rt.connect_backtest(bt)
streamer = DataStreamer(profile_data, model_config)
streamer.connect_tool(rt)
streamer.run()

