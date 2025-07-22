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

        logger.info(f"TradeExecutorNew initialized: "
                    f"Stop Loss: {stop_loss_pct:.1%}, Take Profit: {take_profit_pct:.1%}")

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

        # If we're in a position, check for exits FIRST
        if self.portfolio.is_in_position():
            self._check_exit_conditions(timestamp, current_price, bar_scores)

        # If not in position (or just exited), check for entry signals
        if not self.portfolio.is_in_position():
            self._check_entry_conditions(timestamp, current_price, bar_scores)

    def _check_exit_conditions(self, timestamp: int, current_price: float,
                               bar_scores: Dict[str, float]) -> None:
        """
        Check all exit conditions in priority order:
        1. Stop Loss
        2. Take Profit
        3. Exit Long Signals
        """

        # 1. Check Stop Loss (highest priority)
        if self.stop_loss_price and current_price <= self.stop_loss_price:
            # logger.info(f"STOP LOSS executed @ ${current_price:.2f} (Stop: ${self.stop_loss_price:.2f})")
            self.portfolio.exit_long(timestamp, current_price, TradeReason.STOP_LOSS)
            self._clear_exit_levels()
            return

        # 2. Check Take Profit
        if self.take_profit_price and current_price >= self.take_profit_price:
            # logger.info(f"TAKE PROFIT executed @ ${current_price:.2f} (Target: ${self.take_profit_price:.2f})")
            self.portfolio.exit_long(timestamp, current_price, TradeReason.TAKE_PROFIT)
            self._clear_exit_levels()
            return

        # 3. Check Exit Long Signals
        exit_triggered = self._check_exit_long_signals(bar_scores)
        if exit_triggered:
            # logger.info(f"EXIT LONG SIGNAL executed @ ${current_price:.2f}")
            self.portfolio.exit_long(timestamp, current_price, TradeReason.EXIT_LONG)
            self._clear_exit_levels()
            return

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

            if bar_score >= threshold:
                # logger.info(f"Exit signal triggered: {bar_name} = {bar_score:.3f} "
                #             f"(threshold: {threshold:.3f})")
                return True
            # else:
                # logger.debug(f"Exit signal {bar_name}: {bar_score:.3f} < {threshold:.3f}")

        return False

    def _check_entry_conditions(self, timestamp: int, current_price: float,
                                bar_scores: Dict[str, float]) -> None:
        """
        Check if enter_long conditions are triggered for entry
        """
        enter_conditions = getattr(self.monitor_config, 'enter_long', [])

        # Check each enter_long condition
        for condition in enter_conditions:
            bar_name = condition.get('name')
            threshold = condition.get('threshold')
            bar_score = bar_scores.get(bar_name)

            if bar_score >= threshold:
                # logger.info(f"BUY SIGNAL triggered: {bar_name} = {bar_score:.3f} "
                #             f"(threshold: {threshold:.3f})")
                self._execute_buy(timestamp, current_price)
                return  # Exit after first successful entry
            else:
                logger.debug(f"No entry {bar_name}: {bar_score:.3f} < {threshold:.3f}")

    def _execute_buy(self, timestamp: int, current_price: float) -> None:
        """
        Execute buy order and set stop loss and take profit levels
        """
        # Calculate stop loss and take profit prices
        self.stop_loss_price = current_price * (1.0 - self.stop_loss_pct)
        self.take_profit_price = current_price * (1.0 + self.take_profit_pct)

        # Execute the buy
        self.portfolio.buy(timestamp, current_price, TradeReason.ENTER_LONG, self.default_position_size)

        # logger.info(f"BUY executed: {self.default_position_size} @ ${current_price:.2f} "
        #             f"Stop: ${self.stop_loss_price:.2f} Target: ${self.take_profit_price:.2f}")

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