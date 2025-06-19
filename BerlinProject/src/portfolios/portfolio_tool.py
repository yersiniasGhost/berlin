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
    Portfolio data object with PERCENT-BASED P&L and proper realized P&L tracking
    """
    # Position state
    position_size: float = 0.0
    trade_size: float = 1.0

    # Trade history
    trade_history: List[Trade] = field(default_factory=list)

    # P&L tracking - NEW: Track realized P&L properly
    total_realized_pnl_percent: float = 0.0  # Cumulative realized P&L as percentage

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
        """Exit long position and properly add to realized P&L"""

        # Calculate realized P&L BEFORE clearing position
        entry_price = self.get_entry_price()
        if entry_price and entry_price > 0 and self.position_size > 0:
            # Calculate percent gain/loss: (exit_price - entry_price) / entry_price * 100
            realized_pnl_percent = ((price - entry_price) / entry_price) * 100.0

            # Add to cumulative realized P&L
            self.total_realized_pnl_percent += realized_pnl_percent

            print(f"REALIZED P&L: Entry: ${entry_price:.4f}, Exit: ${price:.4f}, "
                  f"Gain: {realized_pnl_percent:.2f}%, Total Realized: {self.total_realized_pnl_percent:.2f}%")

        # Record the exit trade
        trade = Trade(
            time=time,
            size=self.position_size,  # Exit full position
            price=price,
            reason=reason
        )
        self.trade_history.append(trade)

        # Clear position AFTER calculating P&L
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

        # Find the most recent entry trade by looking backwards through trade history
        for trade in reversed(self.trade_history):
            if trade.reason in [TradeReason.ENTER_LONG, TradeReason.ENTER_SHORT]:
                return trade.price

        # If no explicit entry trade found, look for any BUY trade while we're in position
        for trade in reversed(self.trade_history):
            if trade.size > 0:  # Positive size indicates a buy
                return trade.price

        return None

    def calculate_unrealized_pnl_percent(self, current_price: float) -> float:
        """Calculate unrealized P&L as PERCENTAGE"""
        if not self.is_in_position() or not current_price:
            return 0.0

        entry_price = self.get_entry_price()
        if entry_price is None or entry_price == 0.0:
            return 0.0

        # Calculate percent change: (current_price - entry_price) / entry_price * 100
        unrealized_percent = ((current_price - entry_price) / entry_price) * 100.0
        return unrealized_percent

    def calculate_realized_pnl_percent(self) -> float:
        """Get total realized P&L as percentage"""
        return self.total_realized_pnl_percent

    def get_performance_metrics(self, current_price: float = None) -> Dict[str, Any]:
        """
        Get comprehensive portfolio performance metrics with PERCENT-BASED P&L

        Args:
            current_price: Current market price for unrealized P&L calculation

        Returns:
            Dictionary with position and P&L information in PERCENTAGES
        """
        # Get entry price
        entry_price = self.get_entry_price() or 0.0

        # Position information
        position_data = {
            'is_in_position': self.is_in_position(),
            'position_size': self.position_size,
            'entry_price': entry_price,
            'current_price': current_price or 0.0
        }

        # P&L calculations in PERCENTAGES
        realized_pnl_percent = self.calculate_realized_pnl_percent()
        unrealized_pnl_percent = self.calculate_unrealized_pnl_percent(current_price) if current_price else 0.0
        total_pnl_percent = realized_pnl_percent + unrealized_pnl_percent

        pnl_data = {
            'realized_pnl_percent': realized_pnl_percent,
            'unrealized_pnl_percent': unrealized_pnl_percent,
            'total_pnl_percent': total_pnl_percent
        }

        return {
            'position': position_data,
            'pnl': pnl_data
        }

    def get_trade_summary(self) -> Dict[str, Any]:
        """Get a summary of all trades for debugging"""
        return {
            'total_trades': len(self.trade_history),
            'current_position_size': self.position_size,
            'total_realized_pnl_percent': self.total_realized_pnl_percent,
            'trades': [
                {
                    'time': trade.time,
                    'reason': trade.reason.value,
                    'size': trade.size,
                    'price': trade.price
                }
                for trade in self.trade_history[-5:]  # Last 5 trades
            ]
        }

    def reset(self) -> None:
        """Reset portfolio to initial state"""
        self.position_size = 0.0
        self.trade_history.clear()
        self.total_realized_pnl_percent = 0.0  # Reset realized P&L too