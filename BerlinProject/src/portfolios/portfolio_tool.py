from dataclasses import dataclass, field
from enum import Enum
from typing import List


class TradeReason(Enum):
    ENTER_LONG = "enter_long"
    EXIT_LONG = "exit_long"
    ENTER_SHORT = "enter_short"
    EXIT_SHORT = "exit_short"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


@dataclass
class Trade:
    time: int
    size: float
    price: float
    reason: TradeReason


@dataclass
class Portfolio:
    """
    Simple portfolio data object - just holds state, no logic
    """
    # Position state
    position_size: float = 0.0
    trade_size: float = 1.0

    # Trade history
    trade_history: List[Trade] = field(default_factory=list)

    def buy(self, time: int, price: float, reason: TradeReason, size: float) -> None:

        # Update position
        self.position_size += size

        # Record trade
        trade = Trade(
            time=time,
            size=size,
            price=price,
            reason=reason
        )
        self.trade_history.append(trade)

    def exit_long(self, time: int, price: float, reason: TradeReason = TradeReason.EXIT_LONG) -> None:
        trade = Trade(
            time=time,
            size=self.position_size,
            price=price,
            reason=reason
        )
        self.trade_history.append(trade)

    def sell(self, time: int, price: float, reason: TradeReason, size: float) -> None:

        self.position_size -= size

        trade = Trade(
            time=time,
            size=size,
            price=price,
            reason=reason
        )
        self.trade_history.append(trade)