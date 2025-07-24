import logging
from typing import Dict, Optional
from datetime import datetime

from models.monitor_configuration import MonitorConfiguration
from models.tick_data import TickData
from portfolios.portfolio_tool import Portfolio, TradeReason
from portfolios.trade_executor import TradeExecutor

logger = logging.getLogger('TradeExecutorNew')


class TradeExecutorNew(TradeExecutor):
    """
    Enhanced Trade Executor with:
    - Bull signal entries
    - Bear signal exits
    - Stop loss exits
    - Take profit exits
    """

    def __init__(self, monitor_config: MonitorConfiguration,
                 default_position_size: float = 100.0,
                 stop_loss_pct: float = 0.01,
                 take_profit_pct: float = 0.01):
        """
        Initialize TradeExecutorNew

        Args:
            monitor_config: Monitor configuration with thresholds and bars
            default_position_size: Default size for trades
            stop_loss_pct: Stop loss percentage (e.g., 0.08 = 8%)
            take_profit_pct: Take profit percentage (e.g., 0.05 = 5%)
        """
        # Call parent constructor
        super().__init__(monitor_config, default_position_size, stop_loss_pct)

        # Add take profit capability
        self.take_profit_pct = take_profit_pct

        # Track stop loss and take profit levels
        self.stop_loss_price: Optional[float] = None
        self.take_profit_price: Optional[float] = None

        # DEBUG: Add debug mode flag
        self.debug_mode = False
        self.trade_count = 0

        logger.info(f"TradeExecutorNew initialized: "
                    f"Stop Loss: {stop_loss_pct:.1%}, Take Profit: {take_profit_pct:.1%}")

    def enable_debug_mode(self):
        """Enable debug logging for first few trades"""
        self.debug_mode = True

    def make_decision(self, tick: TickData, indicators: Dict[str, float],
                      bar_scores: Dict[str, float] = None) -> None:
        """
        Main decision logic: check exits first, then entries

        Args:
            tick: Current tick data
            indicators: Individual indicator values
            bar_scores: Weighted bar scores (optional)
        """
        if bar_scores is None:
            bar_scores = {}

        current_price = tick.close
        timestamp = int(tick.timestamp.timestamp() * 1000)  # Convert to milliseconds

        # DEBUG: Log first 10 decisions
        if self.trade_count < 10 and self.debug_mode:
            print(f"\n=== TRADE DECISION #{self.trade_count} ===")
            print(f"Time: {tick.timestamp}")
            print(f"Price: ${current_price:.2f}")
            print(f"In Position: {self.portfolio.is_in_position()}")
            print(f"Position Size: {self.portfolio.position_size}")
            print(f"Bar Scores: {bar_scores}")
            print(f"Enter Conditions: {getattr(self.monitor_config, 'enter_long', [])}")
            print(f"Exit Conditions: {getattr(self.monitor_config, 'exit_long', [])}")

        # If we're in a position, check for exits FIRST
        if self.portfolio.is_in_position():
            exit_executed = self._check_exit_conditions(timestamp, current_price, bar_scores)
            if exit_executed and self.debug_mode:
                print(f"EXIT executed at ${current_price:.2f}")

        # If not in position (or just exited), check for entry signals
        if not self.portfolio.is_in_position():
            entry_executed = self._check_entry_conditions(timestamp, current_price, bar_scores)
            if entry_executed and self.debug_mode:
                print(f"ENTRY executed at ${current_price:.2f}")

        self.trade_count += 1

    def _check_exit_conditions(self, timestamp: int, current_price: float,
                               bar_scores: Dict[str, float]) -> bool:
        """
        Check all exit conditions in priority order:
        1. Stop Loss
        2. Take Profit
        3. Exit Long Signals

        Returns:
            True if exit was executed
        """

        # 1. Check Stop Loss (highest priority)
        if self.stop_loss_price and current_price <= self.stop_loss_price:
            if self.debug_mode:
                print(f"STOP LOSS TRIGGERED: ${current_price:.2f} <= ${self.stop_loss_price:.2f}")
            self.portfolio.exit_long(timestamp, current_price, TradeReason.STOP_LOSS)
            self._clear_exit_levels()
            return True

        # 2. Check Take Profit
        if self.take_profit_price and current_price >= self.take_profit_price:
            if self.debug_mode:
                print(f"TAKE PROFIT TRIGGERED: ${current_price:.2f} >= ${self.take_profit_price:.2f}")
            self.portfolio.exit_long(timestamp, current_price, TradeReason.TAKE_PROFIT)
            self._clear_exit_levels()
            return True

        # 3. Check Exit Long Signals
        exit_triggered = self._check_exit_long_signals(bar_scores)
        if exit_triggered:
            if self.debug_mode:
                print(f"EXIT SIGNAL TRIGGERED")
            self.portfolio.exit_long(timestamp, current_price, TradeReason.EXIT_LONG)
            self._clear_exit_levels()
            return True

        return False

    def _check_exit_long_signals(self, bar_scores: Dict[str, float]) -> bool:
        """
        Check if any exit_long conditions are triggered

        Returns:
            True if exit should be triggered
        """
        exit_conditions = getattr(self.monitor_config, 'exit_long', [])

        # Check each exit_long condition
        for condition in exit_conditions:
            bar_name = condition.get('name')
            threshold = condition.get('threshold', 0.8)
            bar_score = bar_scores.get(bar_name, 0.0)

            if self.debug_mode and self.trade_count < 10:
                print(f"Exit Check: {bar_name} = {bar_score:.3f} vs threshold {threshold:.3f}")

            if bar_score >= threshold:
                if self.debug_mode:
                    print(f"EXIT SIGNAL: {bar_name} = {bar_score:.3f} >= {threshold:.3f}")
                return True

        return False

    def _check_entry_conditions(self, timestamp: int, current_price: float,
                                bar_scores: Dict[str, float]) -> bool:
        """
        Check if enter_long conditions are triggered for entry

        Returns:
            True if entry was executed
        """
        enter_conditions = getattr(self.monitor_config, 'enter_long', [])

        # Check each enter_long condition
        for condition in enter_conditions:
            bar_name = condition.get('name')
            threshold = condition.get('threshold', 0.5)
            bar_score = bar_scores.get(bar_name, 0.0)

            if self.debug_mode and self.trade_count < 10:
                print(f"Entry Check: {bar_name} = {bar_score:.3f} vs threshold {threshold:.3f}")

            if bar_score >= threshold:
                if self.debug_mode:
                    print(f"ENTRY SIGNAL: {bar_name} = {bar_score:.3f} >= {threshold:.3f}")
                self._execute_buy(timestamp, current_price)
                return True

        return False

    def _execute_buy(self, timestamp: int, current_price: float) -> None:
        """
        Execute buy order and set stop loss and take profit levels
        """
        # Calculate stop loss and take profit prices
        self.stop_loss_price = current_price * (1.0 - self.stop_loss_pct)
        self.take_profit_price = current_price * (1.0 + self.take_profit_pct)

        # Execute the buy
        self.portfolio.buy(timestamp, current_price, TradeReason.ENTER_LONG, self.default_position_size)

        if self.debug_mode:
            print(f"BUY EXECUTED: {self.default_position_size} @ ${current_price:.2f}")
            print(f"Stop Loss: ${self.stop_loss_price:.2f}")
            print(f"Take Profit: ${self.take_profit_price:.2f}")

    def _clear_exit_levels(self) -> None:
        """Clear stop loss and take profit levels after exit"""
        self.stop_loss_price = None
        self.take_profit_price = None

    def get_status(self) -> Dict:
        """Get current executor status for debugging"""
        return {
            'in_position': self.portfolio.is_in_position(),
            'position_size': self.portfolio.position_size,
            'stop_loss_price': self.stop_loss_price,
            'take_profit_price': self.take_profit_price,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'total_trades': len(self.portfolio.trade_history)
        }