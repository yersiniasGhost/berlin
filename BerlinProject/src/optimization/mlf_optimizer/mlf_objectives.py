"""
MLF Objective Functions for Genetic Algorithm Optimization.

Each objective function defines a fitness metric that the GA tries to optimize.
Objectives can have configurable parameters exposed through get_parameter_specs().
"""

from typing import List, Optional
from dataclasses import dataclass
from optimization.genetic_optimizer.abstractions.objective_function_base import (
    ObjectiveFunctionBase,
    ObjectiveParameterSpec,
    ObjectiveParameterType
)
from portfolios.portfolio_tool import Portfolio
from .mlf_individual import MlfIndividual
from models.tick_data import TickData


@dataclass
class MaximizeProfit(ObjectiveFunctionBase):
    """Maximize average profit per winning trade.

    Uses target_profit_per_trade as the benchmark - trades achieving this
    target get objective value approaching 0 (optimal).
    """

    def __post_init__(self):
        self.name = "MaximizeProfit"
        self.display_name = "Maximize Profit per Trade"
        self.description = "Optimize for higher profit percentage per winning trade"
        super().__post_init__()

    @classmethod
    def get_parameter_specs(cls) -> List[ObjectiveParameterSpec]:
        return [
            ObjectiveParameterSpec(
                name="target_profit_per_trade",
                display_name="Target Profit per Trade",
                parameter_type=ObjectiveParameterType.FLOAT,
                default_value=0.05,
                min_value=0.01,
                max_value=0.50,
                step=0.01,
                description="Target profit percentage per trade (e.g., 0.05 = 5%)",
                ui_group="Profit Settings"
            )
        ]

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]

        target_profit = self.get_parameter("target_profit_per_trade", 0.05)

        total_profit = portfolio.get_total_percent_profits()  # Returns percentage values
        trade_count = portfolio.get_winning_trades_count()

        if total_profit <= 0.0:
            return 100.0  # High penalty for no profits or losses

        total_profit = total_profit / 100.0
        if trade_count == 0:
            return 100.0

        # For maximization in a minimization framework, use reciprocal
        # Lower objective value = better fitness
        per_trade = (total_profit / trade_count)
        objective_value = max(0.0, 1.0 - per_trade / target_profit)

        return objective_value * self.weight


@dataclass
class MinimizeLoss(ObjectiveFunctionBase):
    """Minimize average loss per losing trade."""

    def __post_init__(self):
        self.name = "MinimizeLoss"
        self.display_name = "Minimize Loss per Trade"
        self.description = "Minimize the average loss percentage on losing trades"
        super().__post_init__()

    @classmethod
    def get_parameter_specs(cls) -> List[ObjectiveParameterSpec]:
        return []  # No configurable parameters

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]

        total_loss = portfolio.get_total_percent_losses()  # Returns percentage values
        trade_count = portfolio.get_losing_trades_count()
        if trade_count == 0:
            return 0.0
        # Direct minimization - higher losses = higher objective value (worse)
        objective_value = total_loss / trade_count

        return objective_value * self.weight


@dataclass
class MinimizeLosingTrades(ObjectiveFunctionBase):
    """Minimize the ratio of losing trades to total trades."""

    def __post_init__(self):
        self.name = "MinimizeLosingTrades"
        self.display_name = "Minimize Losing Trades Ratio"
        self.description = "Minimize the percentage of trades that result in losses"
        super().__post_init__()

    @classmethod
    def get_parameter_specs(cls) -> List[ObjectiveParameterSpec]:
        return []  # No configurable parameters

    def calculate_objective(self, *args) -> float:
        portfolio: Portfolio = args[1]

        losing_trades = portfolio.get_losing_trades_count()
        winning_trades = portfolio.get_winning_trades_count()
        total_trades = losing_trades + winning_trades

        if total_trades == 0:
            return 100.0  # High penalty for no trading activity

        losing_ratio = losing_trades / total_trades

        return losing_ratio * self.weight


@dataclass
class MinimizeTrades(ObjectiveFunctionBase):
    """Minimize total number of trades (reduce overtrading)."""

    def __post_init__(self):
        self.name = "MinimizeTrades"
        self.display_name = "Minimize Total Trades"
        self.description = "Reduce overtrading by minimizing total trade count"
        super().__post_init__()

    @classmethod
    def get_parameter_specs(cls) -> List[ObjectiveParameterSpec]:
        return []  # No configurable parameters

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]
        total_trades = portfolio.get_winning_trades_count() + portfolio.get_losing_trades_count()
        objective = total_trades / 100.0
        return objective * self.weight


@dataclass
class MaximizeNetPnL(ObjectiveFunctionBase):
    """Maximize net profit and loss (total profits minus total losses)."""

    def __post_init__(self):
        self.name = "MaximizeNetPnL"
        self.display_name = "Maximize Net PnL"
        self.description = "Maximize overall net profit (profits minus losses)"
        super().__post_init__()

    @classmethod
    def get_parameter_specs(cls) -> List[ObjectiveParameterSpec]:
        return [
            ObjectiveParameterSpec(
                name="mode",
                display_name="Calculation Mode",
                parameter_type=ObjectiveParameterType.CHOICE,
                default_value="inverse",
                choices=["inverse", "volatility", "maxdrawdown"],
                description="Method for calculating objective: inverse (simple), volatility-adjusted, or drawdown-adjusted",
                ui_group="Calculation Settings"
            )
        ]

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]

        total_profit = portfolio.get_total_percent_profits()
        total_loss = portfolio.get_total_percent_losses()

        net_pnl = (total_profit - total_loss) / 100.0
        if total_profit == 0.0 and total_loss == 0.0:
            return 100.0 * self.weight
        elif net_pnl <= 0.0:
            return 100.0 * self.weight

        mode = self.get_parameter("mode", "inverse")

        if mode == "inverse":
            objective_value = 1.0 / net_pnl
        elif mode == "volatility":
            data_streamer = args[2]
            primary_data = data_streamer.primary_aggregator
            metric, adj_netpnl = primary_data.get_volatility(net_pnl)
            objective_value = 1.0 - adj_netpnl
            print(metric, adj_netpnl, net_pnl, objective_value)
        elif mode == "maxdrawdown":
            data_streamer = args[2]
            primary_data = data_streamer.primary_aggregator
            metric = primary_data.get_maximum_drawdown() / 100.0
            objective_value = max(0.0, 3.0 - (net_pnl - metric) / abs(metric))
        else:
            objective_value = 1.0 / net_pnl

        return objective_value * self.weight


@dataclass
class MaximizeScaledNetPnL(ObjectiveFunctionBase):
    """Maximize net PnL scaled relative to the maximum possible return.

    Uses the price range during the period to calculate what the maximum
    possible return could have been, then scales the actual return against it.
    """
    global_pct: Optional[float] = None

    def __post_init__(self):
        self.name = "MaximizeScaledNetPnL"
        self.display_name = "Maximize Scaled Net PnL"
        self.description = "Maximize net PnL relative to the maximum possible return in the period"
        super().__post_init__()

    @classmethod
    def get_parameter_specs(cls) -> List[ObjectiveParameterSpec]:
        return []  # global_pct is computed in preprocess, not user-configurable

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]

        total_profit = portfolio.get_total_percent_profits()
        total_loss = portfolio.get_total_percent_losses()

        net_pnl = (total_profit - total_loss) / 100.0
        if total_profit == 0.0 and total_loss == 0.0:
            return 100.0

        objective_value = max(0.0, 1.0 - net_pnl / self.global_pct)
        return objective_value * self.weight

    def preprocess(self, *args):
        """Calculate maximum expected return from price range."""
        tick_history: List[TickData] = args[0]
        max_close = max(tick_history, key=lambda x: x.close).close
        min_close = min(tick_history, key=lambda x: x.close).close
        self.global_pct = abs((max_close - min_close) / min_close)


@dataclass
class MaximizeCashProfit(ObjectiveFunctionBase):
    """Maximize total cash profit over a time period.

    This objective focuses on absolute dollar profits rather than percentages.
    Useful when position sizing varies or when targeting specific dollar amounts.
    """

    def __post_init__(self):
        self.name = "MaximizeCashProfit"
        self.display_name = "Maximize Cash Profit"
        self.description = "Maximize total dollar profit over the trading period"
        super().__post_init__()

    @classmethod
    def get_parameter_specs(cls) -> List[ObjectiveParameterSpec]:
        return [
            ObjectiveParameterSpec(
                name="target_cash_profit",
                display_name="Target Cash Profit",
                parameter_type=ObjectiveParameterType.FLOAT,
                default_value=1000.0,
                min_value=100.0,
                max_value=100000.0,
                step=100.0,
                description="Target total cash profit in dollars for the period",
                ui_group="Profit Target"
            ),
            ObjectiveParameterSpec(
                name="penalty_multiplier",
                display_name="Loss Penalty Multiplier",
                parameter_type=ObjectiveParameterType.FLOAT,
                default_value=2.0,
                min_value=1.0,
                max_value=5.0,
                step=0.5,
                description="How much to penalize losses relative to rewarding gains",
                ui_group="Risk Settings"
            ),
            ObjectiveParameterSpec(
                name="minimum_trades",
                display_name="Minimum Trades Required",
                parameter_type=ObjectiveParameterType.INTEGER,
                default_value=5,
                min_value=1,
                max_value=100,
                step=1,
                description="Minimum number of trades required to avoid penalty",
                ui_group="Trade Requirements"
            )
        ]

    def calculate_objective(self, *args) -> float:
        individual: MlfIndividual = args[0]
        portfolio: Portfolio = args[1]

        # Get parameters
        target_profit = self.get_parameter("target_cash_profit", 1000.0)
        penalty_mult = self.get_parameter("penalty_multiplier", 2.0)
        min_trades = self.get_parameter("minimum_trades", 5)

        # Get cash profits and losses
        total_cash_profit = portfolio.get_total_cash_profits()
        total_cash_loss = portfolio.get_total_cash_losses()
        total_trades = portfolio.get_winning_trades_count() + portfolio.get_losing_trades_count()

        # Penalty for not meeting minimum trade requirement
        if total_trades < min_trades:
            trade_penalty = (min_trades - total_trades) * 10.0
            return (100.0 + trade_penalty) * self.weight

        # Net cash P&L with asymmetric penalty for losses
        net_cash = total_cash_profit - (total_cash_loss * penalty_mult)

        if net_cash <= 0:
            # Negative or zero - high penalty proportional to loss
            return (100.0 + abs(net_cash) / 100.0) * self.weight

        # Objective: how far from target (lower is better)
        # If exceeding target, reward continues (objective approaches 0)
        objective_value = max(0.0, 1.0 - net_cash / target_profit)

        return objective_value * self.weight


# Registry of all available objective functions
OBJECTIVE_CLASSES = {
    'MaximizeProfit': MaximizeProfit,
    'MinimizeLoss': MinimizeLoss,
    'MinimizeLosingTrades': MinimizeLosingTrades,
    'MinimizeTrades': MinimizeTrades,
    'MaximizeNetPnL': MaximizeNetPnL,
    'MaximizeScaledNetPnL': MaximizeScaledNetPnL,
    'MaximizeCashProfit': MaximizeCashProfit,
}
