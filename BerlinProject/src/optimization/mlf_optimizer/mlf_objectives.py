from dataclasses import dataclass
from optimization.genetic_optimizer.abstractions.objective_function_base import ObjectiveFunctionBase
from .mlf_individual import MlfIndividual


@dataclass
class MaximizeProfit(ObjectiveFunctionBase):
    mode: str = "negative"  # Could be "reciprocal" or "scaling"

    def __post_init__(self):
        self.name = "Maximize Profit"


    def calculate_objective(self, *args) -> float:
        # Ensure there is no grid charges during this time frame.
        individual: MlfIndividual = args[0]
        bt: MonitorBacktest = args[1]
        total_profit = 0

        return -total_profit / self.normalization_factor * self.weight


@dataclass
class MinimizeLosingTrades(ObjectiveFunctionBase):

    def __post_init__(self):
        self.name = "Minimize Losing Trades"

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        bt: MonitorBacktest = args[1]

        number_of_trades = 1
        number_of_losing_trades = 0

        return (number_of_losing_trades / number_of_trades) / self.normalization_factor * self.weight
