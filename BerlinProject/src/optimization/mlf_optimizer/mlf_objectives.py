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
        portfolio: Portfolio = args[1]

        total_profit = portfolio.get_total_percent_profits()  # This returns percentage values

        # DEBUG: Print for first few individuals
        if hasattr(portfolio, 'debug_mode') and portfolio.debug_mode:
            print(f"MaximizeProfit: Total profits = {total_profit:.2f}%")

        if total_profit <= 0.0:
            return 100.0  # High penalty for no profits or losses

        # FIXED: For maximization in a minimization framework, use reciprocal
        # Lower objective value = better fitness
        objective_value = 1.0 / total_profit

        if hasattr(portfolio, 'debug_mode') and portfolio.debug_mode:
            print(f"MaximizeProfit: Objective value = {objective_value:.6f} (lower is better)")

        return objective_value * self.weight


@dataclass
class MinimizeLoss(ObjectiveFunctionBase):

    def __post_init__(self):
        self.name = "Minimize Loss"

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]

        total_loss = portfolio.get_total_percent_losses()  # This returns percentage values

        # DEBUG: Print for first few individuals
        if hasattr(portfolio, 'debug_mode') and portfolio.debug_mode:
            print(f"MinimizeLoss: Total losses = {total_loss:.2f}%")

        # FIXED: Direct minimization - higher losses = higher objective value (worse)
        objective_value = total_loss

        if hasattr(portfolio, 'debug_mode') and portfolio.debug_mode:
            print(f"MinimizeLoss: Objective value = {objective_value:.6f} (lower is better)")

        return objective_value * self.weight


@dataclass
class MinimizeLosingTrades(ObjectiveFunctionBase):

    def __post_init__(self):
        self.name = "Minimize Losing Trades"

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]

        losing_trades = portfolio.get_losing_trades_count()
        winning_trades = portfolio.get_winning_trades_count()
        total_trades = losing_trades + winning_trades

        # DEBUG: Print for first few individuals
        if hasattr(portfolio, 'debug_mode') and portfolio.debug_mode:
            print(f"MinimizeLosingTrades: {losing_trades} losing, {winning_trades} winning, {total_trades} total")

        if total_trades == 0:
            return 100.0  # High penalty for no trading activity

        losing_ratio = losing_trades / total_trades

        if hasattr(portfolio, 'debug_mode') and portfolio.debug_mode:
            print(f"MinimizeLosingTrades: Losing ratio = {losing_ratio:.3f}")

        return losing_ratio * self.weight