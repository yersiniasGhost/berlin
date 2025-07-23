from dataclasses import dataclass
from optimization.genetic_optimizer.abstractions.objective_function_base import ObjectiveFunctionBase
from portfolios.portfolio_tool import Portfolio
from .mlf_individual import MlfIndividual


@dataclass
class MaximizeProfit(ObjectiveFunctionBase):

    def __post_init__(self):
        self.name = "Maximize Profit"

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]  # Changed from MonitorResultsBacktest to Portfolio

        total_profit = portfolio.get_total_percent_profits()  # Use new Portfolio method

        if total_profit == 0.0:
            return 100.0  # High penalty for no profits

        # Use reciprocal - higher profits give lower objective values (better for minimization)
        return (1.0 / total_profit) / self.normalization_factor * self.weight





@dataclass
class MinimizeLoss(ObjectiveFunctionBase):

    def __post_init__(self):
        self.name = "Minimize Loss"

    def calculate_objective(self, *args) -> float:
        # Ensure there is no grid charges during this time frame.
        individual: MlfIndividual = args[0]
        bt: Portfolio = args[1]
        total_loss = bt.get_total_percent_losses()
        return total_loss / self.normalization_factor * self.weight
        # return -total_profit / self.normalization_factor * self.weight


@dataclass
class MinimizeLosingTrades(ObjectiveFunctionBase):

    def __post_init__(self):
        self.name = "Minimize Losing Trades"

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]

        losing_trades = portfolio.get_losing_trades_count()  # Use new Portfolio method
        winning_trades = portfolio.get_winning_trades_count()  # Use new Portfolio method
        total_trades = losing_trades + winning_trades

        if total_trades == 0:
            return 100.0  # High penalty for no trading activity

        losing_ratio = losing_trades / total_trades

        return losing_ratio / self.normalization_factor * self.weight


