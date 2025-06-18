from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime


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
    Portfolio data object with performance calculation methods
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
            size=self.position_size,  # Exit full position
            price=price,
            reason=reason
        )
        self.trade_history.append(trade)

        self.position_size = 0.0

    def sell(self, time: int, price: float, reason: TradeReason, size: float) -> None:
        self.position_size -= size

        trade = Trade(
            time=time,
            size=size,  # Negative size to indicate selling
            price=price,
            reason=reason
        )
        self.trade_history.append(trade)

    def is_in_position(self) -> bool:
        """Check if currently in a position"""
        return self.position_size > 0

    def get_entry_price(self) -> Optional[float]:
        """Get the entry price of current position"""
        if not self.is_in_position():
            return None

        # Find the most recent entry trade
        for trade in reversed(self.trade_history):
            if trade.reason in [TradeReason.ENTER_LONG, TradeReason.ENTER_SHORT]:
                return trade.price
        return None

    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L for current position"""
        if not self.is_in_position():
            return 0.0

        entry_price = self.get_entry_price()
        if entry_price is None:
            return 0.0

        # For long positions: (current_price - entry_price) * position_size
        return (current_price - entry_price) * self.position_size

    def calculate_realized_pnl(self) -> float:
        """Calculate realized P&L from completed round trips"""
        realized_pnl = 0.0
        entry_price = None
        entry_size = 0.0

        for trade in self.trade_history:
            if trade.reason in [TradeReason.ENTER_LONG, TradeReason.ENTER_SHORT]:
                entry_price = trade.price
                entry_size = trade.size
            elif trade.reason in [TradeReason.EXIT_LONG, TradeReason.EXIT_SHORT, TradeReason.STOP_LOSS,
                                  TradeReason.TAKE_PROFIT]:
                if entry_price is not None:
                    # Calculate P&L for this round trip
                    if trade.reason in [TradeReason.EXIT_LONG, TradeReason.STOP_LOSS, TradeReason.TAKE_PROFIT]:
                        # Long position exit
                        pnl = (trade.price - entry_price) * entry_size
                    else:
                        # Short position exit (if we implement shorts later)
                        pnl = (entry_price - trade.price) * entry_size

                    realized_pnl += pnl
                    entry_price = None
                    entry_size = 0.0

        return realized_pnl

    def reset(self) -> None:
        """Reset portfolio to initial state"""
        self.position_size = 0.0
        self.trade_history.clear()