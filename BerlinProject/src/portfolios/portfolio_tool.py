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
        """Get the entry price of current position - FIXED VERSION"""
        if not self.is_in_position():
            return None

        # Find the most recent entry trade by looking backwards through trade history
        for trade in reversed(self.trade_history):
            if trade.reason in [TradeReason.ENTER_LONG, TradeReason.ENTER_SHORT]:
                return trade.price

        # If no explicit entry trade found, look for any BUY trade while we're in position
        # This handles cases where the reason might not be set correctly
        for trade in reversed(self.trade_history):
            if trade.size > 0:  # Positive size indicates a buy
                return trade.price

        return None

    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L for current position"""
        if not self.is_in_position() or not current_price:
            return 0.0

        entry_price = self.get_entry_price()
        if entry_price is None or entry_price == 0.0:
            return 0.0

        # For long positions: (current_price - entry_price) * position_size
        unrealized = (current_price - entry_price) * self.position_size
        return unrealized

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

    def get_performance_metrics(self, current_price: float = None) -> Dict[str, Any]:
        """
        Get comprehensive portfolio performance metrics

        Args:
            current_price: Current market price for unrealized P&L calculation

        Returns:
            Dictionary with position and P&L information
        """
        # Get entry price - this should now work correctly
        entry_price = self.get_entry_price() or 0.0

        # Position information
        position_data = {
            'is_in_position': self.is_in_position(),
            'position_size': self.position_size,
            'entry_price': entry_price,
            'current_price': current_price or 0.0
        }

        # P&L calculations with proper current_price handling
        realized_pnl = self.calculate_realized_pnl()
        unrealized_pnl = self.calculate_unrealized_pnl(current_price) if current_price else 0.0
        total_pnl = realized_pnl + unrealized_pnl

        pnl_data = {
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_pnl,
            'total_pnl': total_pnl
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