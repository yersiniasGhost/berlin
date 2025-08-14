# portfolios/trade_executor_unified.py

import logging
from typing import Dict, Optional
from datetime import datetime
from collections import defaultdict

from models.monitor_configuration import MonitorConfiguration
from models.tick_data import TickData
from portfolios.portfolio_tool import Portfolio, TradeReason

logger = logging.getLogger('TradeExecutorUnified')


class TradeExecutorUnified:
    """
    Unified Trade Executor with configurable parameters from monitor config.

    Incorporates logic from all previous trade executor subclasses:
    - Bull signal entries
    - Bear signal exits (configurable)
    - Stop loss exits (fixed or trailing)
    - Take profit exits
    - Signal conflict handling
    """

    def __init__(self, monitor_config: MonitorConfiguration):
        """
        Initialize TradeExecutorUnified with configuration from monitor_config

        Args:
            monitor_config: Monitor configuration containing trade_executor parameters
        """
        self.monitor_config = monitor_config

        # Extract trade executor configuration
        trade_exec_config = monitor_config.trade_executor

        # Core trading parameters
        self.default_position_size = trade_exec_config.default_position_size
        self.stop_loss_pct = trade_exec_config.stop_loss_pct
        self.take_profit_pct = trade_exec_config.take_profit_pct

        # Behavior configuration
        self.ignore_bear_signals = trade_exec_config.ignore_bear_signals
        self.check_signal_conflicts = True  # Always check for signal conflicts

        # Trailing stop loss configuration
        self.trailing_stop_loss = trade_exec_config.trailing_stop_loss
        self.trailing_stop_distance_pct = trade_exec_config.trailing_stop_distance_pct
        self.trailing_stop_activation_pct = trade_exec_config.trailing_stop_activation_pct

        # Initialize portfolio
        self.portfolio = Portfolio()

        # Track stop loss and take profit levels
        self.stop_loss_price: Optional[float] = None
        self.take_profit_price: Optional[float] = None
        self.trailing_stop_price: Optional[float] = None
        self.highest_price_since_entry: Optional[float] = None

        # Debug tracking
        self.debug_mode = False
        self.trade_count = 0

    def enable_debug_mode(self):
        """Enable debug logging for first few trades"""
        self.debug_mode = True

    def make_decision(self,
                      tick: TickData,
                      indicators: Dict[str, float],
                      bar_scores: Dict[str, float] = None) -> None:
        """
        Make trading decisions based on configuration and current market state
        """
        try:
            timestamp = int(tick.timestamp.timestamp() * 1000) if tick.timestamp else 0
            current_price = tick.close  # TickData uses 'close' not 'price'
            bar_scores = defaultdict(float, bar_scores or {})

            # Update trailing stop if in position
            if self.portfolio.is_in_position() and self.trailing_stop_loss:
                self._update_trailing_stop(current_price)

            # Check exit conditions first (if in position)
            if self.portfolio.is_in_position():
                if self._check_exit_conditions(timestamp, current_price, bar_scores):
                    return  # Exit executed, no further action needed

            # Check entry conditions (if not in position)
            if not self.portfolio.is_in_position():
                # Always check for signal conflicts to prevent contradictory actions
                if self._has_signal_conflicts(bar_scores):
                    if self.debug_mode and self.trade_count < 10:
                        print("Signal conflict detected - no action taken")
                    return

                self._check_entry_conditions(timestamp, current_price, bar_scores)

        except Exception as e:
            logger.error(f"Error in make_decision: {e}")

    def _has_signal_conflicts(self, bar_scores: Dict[str, float]) -> bool:
        """
        Check if both bullish and bearish signals are above their thresholds.
        Returns True if there's a conflict.
        """
        enter_conditions = getattr(self.monitor_config, 'enter_long', [])
        exit_conditions = getattr(self.monitor_config, 'exit_long', [])

        bull_triggered = False
        bear_triggered = False

        # Check if any entry conditions are triggered
        for condition in enter_conditions:
            bar_name = condition.get('name')
            threshold = condition.get('threshold', 0.5)
            bar_score = bar_scores.get(bar_name, 0.0)

            if bar_score >= threshold:
                bull_triggered = True
                break

        # Check if any exit conditions are triggered
        for condition in exit_conditions:
            bar_name = condition.get('name')
            threshold = condition.get('threshold', 0.5)
            bar_score = bar_scores.get(bar_name, 0.0)

            if bar_score >= threshold:
                bear_triggered = True
                break

        return bull_triggered and bear_triggered

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

    def _check_exit_conditions(self, timestamp: int, current_price: float,
                               bar_scores: Dict[str, float]) -> bool:
        """
        Check all exit conditions: stop loss, take profit, and bear signals

        Returns:
            True if exit was executed
        """
        # Check stop loss (fixed or trailing)
        if self._check_stop_loss(timestamp, current_price):
            return True

        # Check take profit
        if self._check_take_profit(timestamp, current_price):
            return True

        # Check bear signal exits (unless disabled)
        if not self.ignore_bear_signals and self._check_bear_exit_conditions(timestamp, current_price, bar_scores):
            return True

        return False

    def _check_stop_loss(self, timestamp: int, current_price: float) -> bool:
        """Check stop loss conditions"""
        stop_price = self.trailing_stop_price if self.trailing_stop_loss else self.stop_loss_price

        if stop_price and current_price <= stop_price:
            reason = "Trailing Stop Loss" if self.trailing_stop_loss else "Stop Loss"
            if self.debug_mode:
                print(f"{reason} HIT: ${current_price:.2f} <= ${stop_price:.2f}")

            self.portfolio.sell(timestamp, current_price, TradeReason.STOP_LOSS, self.portfolio.position_size)
            self._clear_exit_levels()
            self.trade_count += 1
            return True

        return False

    def _check_take_profit(self, timestamp: int, current_price: float) -> bool:
        """Check take profit conditions"""
        if self.take_profit_price and current_price >= self.take_profit_price:
            if self.debug_mode:
                print(f"TAKE PROFIT HIT: ${current_price:.2f} >= ${self.take_profit_price:.2f}")

            self.portfolio.sell(timestamp, current_price, TradeReason.TAKE_PROFIT, self.portfolio.position_size)
            self._clear_exit_levels()
            self.trade_count += 1
            return True

        return False

    def _check_bear_exit_conditions(self, timestamp: int, current_price: float,
                                    bar_scores: Dict[str, float]) -> bool:
        """Check bear signal exit conditions"""
        exit_conditions = getattr(self.monitor_config, 'exit_long', [])

        for condition in exit_conditions:
            bar_name = condition.get('name')
            threshold = condition.get('threshold', 0.5)
            bar_score = bar_scores.get(bar_name, 0.0)

            if self.debug_mode and self.trade_count < 10:
                print(f"Exit Check: {bar_name} = {bar_score:.3f} vs threshold {threshold:.3f}")

            if bar_score >= threshold:
                if self.debug_mode:
                    print(f"EXIT SIGNAL: {bar_name} = {bar_score:.3f} >= {threshold:.3f}")

                self.portfolio.sell(timestamp, current_price, TradeReason.EXIT_LONG, self.portfolio.position_size)
                self._clear_exit_levels()
                self.trade_count += 1
                return True

        return False

    def _execute_buy(self, timestamp: int, current_price: float) -> None:
        """
        Execute buy order and set stop loss and take profit levels
        """
        # Calculate stop loss and take profit prices
        self.stop_loss_price = current_price * (1.0 - self.stop_loss_pct)
        self.take_profit_price = current_price * (1.0 + self.take_profit_pct)

        # Initialize trailing stop if enabled
        if self.trailing_stop_loss:
            # Trailing stop starts at the same level as fixed stop loss
            self.trailing_stop_price = self.stop_loss_price
            self.highest_price_since_entry = current_price

        # Execute the buy
        self.portfolio.buy(timestamp, current_price, TradeReason.ENTER_LONG, self.default_position_size)

        if self.debug_mode:
            print(f"BUY EXECUTED: {self.default_position_size} @ ${current_price:.2f}")
            print(f"Stop Loss: ${self.stop_loss_price:.2f}")
            print(f"Take Profit: ${self.take_profit_price:.2f}")
            if self.trailing_stop_loss:
                print(f"Trailing Stop: ${self.trailing_stop_price:.2f}")

    def _update_trailing_stop(self, current_price: float) -> None:
        """
        Update trailing stop loss price based on current price movement
        """
        if not self.highest_price_since_entry:
            return

        # Update highest price since entry
        if current_price > self.highest_price_since_entry:
            self.highest_price_since_entry = current_price

            # Calculate new trailing stop price
            new_trailing_stop = current_price * (1.0 - self.trailing_stop_distance_pct)

            # Only move trailing stop up, never down
            if new_trailing_stop > self.trailing_stop_price:
                self.trailing_stop_price = new_trailing_stop

                if self.debug_mode:
                    print(f"Trailing stop updated: ${self.trailing_stop_price:.2f} (price: ${current_price:.2f})")

    def _clear_exit_levels(self) -> None:
        """Clear all exit levels after trade completion"""
        self.stop_loss_price = None
        self.take_profit_price = None
        self.trailing_stop_price = None
        self.highest_price_since_entry = None

    def get_status(self) -> Dict:
        """Get current executor status for debugging"""
        return {
            'in_position': self.portfolio.is_in_position(),
            'position_size': self.portfolio.position_size,
            'stop_loss_price': self.stop_loss_price,
            'take_profit_price': self.take_profit_price,
            'trailing_stop_price': self.trailing_stop_price,
            'highest_price_since_entry': self.highest_price_since_entry,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'trailing_stop_loss': self.trailing_stop_loss,
            'ignore_bear_signals': self.ignore_bear_signals,
            'total_trades': len(self.portfolio.trade_history)
        }