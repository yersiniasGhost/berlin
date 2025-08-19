from dataclasses import dataclass
from typing import Dict, Any
from optimization.genetic_optimizer.support.types import Json

from optimization.mlf_optimizer.mlf_objectives import MaximizeProfit, MinimizeLosingTrades, MinimizeLoss
from optimization.mlf_optimizer.mlf_objectives import MinimizeTrades, MaximizeNetPnL


@dataclass
class Objective:
    name: str
    weight: float
    parameters: Dict[str, Any]

    @staticmethod
    def from_json(json: Json) -> 'Objective':
        return Objective(name=json['objective'],
                         weight=json['weight'],
                         parameters=json.get('parameters', {}))

    def create_objective(self):
        if self.name == "MaximizeProfit":
            return MaximizeProfit(weight=self.weight, parameters=self.parameters)
        if self.name == "MinimizeLosingTrades":
            return MinimizeLosingTrades(weight=self.weight, parameters=self.parameters)
        elif self.name == "MinimizeLoss":
            return MinimizeLoss(weight=self.weight, parameters=self.parameters)
        elif self.name == "MinimizeTrades":
            return MinimizeTrades(weight=self.weight, parameters=self.parameters)
        elif self.name == "MaximizeNetPnL":
            return MaximizeNetPnL(weight=self.weight, parameters=self.parameters)
        raise ValueError(f"NO such objective {self.name}")

