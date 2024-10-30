from dataclasses import dataclass
from optimization.genetic_optimizer.abstractions.objective_function_base import ObjectiveFunctionBase
from .mlf_individual import MlfIndividual
from operations.monitor_backtest_results import MonitorResultsBacktest


@dataclass
class MaximizeProfit(ObjectiveFunctionBase):
    mode: str = "negative"  # Could be "reciprocal" or "scaling"

    def __post_init__(self):
        self.name = "Maximize Profit"


    def calculate_objective(self, *args) -> float:
        # Ensure there is no grid charges during this time frame.
        individual: MlfIndividual = args[0]
        bt: MonitorResultsBacktest = args[1]
        total_profit = bt.get_total_percent_profits()
        if total_profit == 0.0:
            return 100.0
        return (1.0 - total_profit) / self.normalization_factor * self.weight
        # return -total_profit / self.normalization_factor * self.weight


@dataclass
class MinimizeLoss(ObjectiveFunctionBase):
    mode: str = "negative"  # Could be "reciprocal" or "scaling"

    def __post_init__(self):
        self.name = "Minimize Loss"


    def calculate_objective(self, *args) -> float:
        # Ensure there is no grid charges during this time frame.
        individual: MlfIndividual = args[0]
        bt: MonitorResultsBacktest = args[1]
        total_loss = bt.get_total_percent_losses()
        return total_loss / self.normalization_factor * self.weight
        # return -total_profit / self.normalization_factor * self.weight


@dataclass
class MinimizeLosingTrades(ObjectiveFunctionBase):

    def __post_init__(self):
        self.name = "Minimize Losing Trades"

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        bt: MonitorResultsBacktest = args[1]

        number_of_trades = bt.results['success'] + bt.results['fail'] + 1
        number_of_losing_trades = bt.results['fail']

        return (number_of_losing_trades / number_of_trades) / self.normalization_factor * self.weight
