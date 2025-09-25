from typing import List, Optional
from dataclasses import dataclass
from optimization.genetic_optimizer.abstractions.objective_function_base import ObjectiveFunctionBase
from portfolios.portfolio_tool import Portfolio
from .mlf_individual import MlfIndividual
from models.tick_data import TickData


@dataclass
class MaximizeProfit(ObjectiveFunctionBase):

    def __post_init__(self):
        self.name = "Maximize Profit per Trade"

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]

        total_profit = portfolio.get_total_percent_profits()  # This returns percentage values
        trade_count = portfolio.get_winning_trades_count()

        if total_profit <= 0.0:
            return 100.0  # High penalty for no profits or losses

        total_profit = total_profit / 100.0
        if trade_count == 0:
            return 100.0
        # FIXED: For maximization in a minimization framework, use reciprocal
        # Lower objective value = better fitness
        objective_value = 1.0 - (total_profit/trade_count)
        # objective_value = 100 * (0.06 - (total_profit/trade_count))
        # objective_value = 1.0 / total_profit
        # print(objective_value, total_profit, objective_value*self.weight)

        return objective_value * self.weight


# get winning trade info: return a tuple of total profit and number of profitable trade

@dataclass
class MinimizeLoss(ObjectiveFunctionBase):

    def __post_init__(self):
        self.name = "Minimize Loss per trade"

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]

        total_loss = portfolio.get_total_percent_losses()  # This returns percentage values
        trade_count = portfolio.get_losing_trades_count()
        if trade_count == 0:
            return 0.0
        # FIXED: Direct minimization - higher losses = higher objective value (worse)
        objective_value = total_loss / trade_count

        return objective_value * self.weight


@dataclass
class MinimizeLosingTrades(ObjectiveFunctionBase):

    def __post_init__(self):
        self.name = "Minimize Losing Trades (ratio)"

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]

        losing_trades = portfolio.get_losing_trades_count()
        winning_trades = portfolio.get_winning_trades_count()
        total_trades = losing_trades + winning_trades

        if total_trades == 0:
            return 100.0  # High penalty for no trading activity

        losing_ratio = losing_trades / total_trades

        return losing_ratio * self.weight + 0.2


@dataclass
class MinimizeTrades(ObjectiveFunctionBase):

    def __post_init__(self):
        self.name = "Minimize Total Trades"

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]
        total_trades = portfolio.get_winning_trades_count() + portfolio.get_losing_trades_count()
        objective = total_trades / 100.0
        return objective * self.weight


# function for maximizing overall pnl

@dataclass
class MaximizeNetPnL(ObjectiveFunctionBase):
    def __post_init__(self):
        self.name = "Maximize Net PnL"

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]

        total_profit = portfolio.get_total_percent_profits()
        total_loss = portfolio.get_total_percent_losses()

        net_pnl = (total_profit - total_loss) / 100.0
        if total_profit == 0.0 and total_loss == 0.0:
            objective_value = 100.0
        elif net_pnl <= 0.0:
            objective_value = 100.0  #   abs(net_pnl) + 10.0
        else:
            objective_value = 1.0 / net_pnl

        return objective_value * self.weight


@dataclass
class MaximizeNetPnL2(ObjectiveFunctionBase):
    global_pct: Optional[float] = None

    def __post_init__(self):
        self.name = "Maximize Net PnL"


    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]

        total_profit = portfolio.get_total_percent_profits()
        total_loss = portfolio.get_total_percent_losses()

        net_pnl = (total_profit - total_loss) / 100.0
        if total_profit == 0.0 and total_loss == 0.0:
            objective_value = 100.0

        objective_value = max(0.0, 1.0 - net_pnl / self.global_pct)
        return objective_value * self.weight

    # Let's calculate a "maximum expected return" and shoot for that as our objective
    def preprocess(self, *args):
        tick_history: List[TickData] = args[0]
        # simply grab first and last
        start = tick_history[0].close
        end = tick_history[-1].close
        self.global_pct = abs(end - start / start)


