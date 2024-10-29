from dataclasses import dataclass
from typing import Dict
from optimization.genetic_optimizer.support.types import Json

from optimization.mlf_optimizer.mlf_objectives import MaximizeProfit, MinimizeLosingTrades


@dataclass
class Objective:
    name: str
    weight: float
    parameters: Dict[str, float]

    @staticmethod
    def from_json(json: Json) -> 'Objective':
        return Objective(name=json['objective'],
                         weight=json['weight'],
                         parameters=json.get('parameters', {}))

    def create_objective(self):
        if self.name == "MaximizeProfit":
            return MaximizeProfit(weight=self.weight)
        if self.name == "MinimizeLosingTrades":
            return MinimizeLosingTrades(weight=self.weight)
        raise ValueError(f"NO such objective {self.name}")

