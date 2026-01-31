# portfolios/trade_executor_unified.py

from typing import Dict, Optional, List
from datetime import datetime, date
from collections import defaultdict

from models.monitor_configuration import MonitorConfiguration
from models.tick_data import TickData
from portfolios.portfolio_tool import Portfolio, TradeReason
from mlf_utils.log_manager import LogManager
from mlf_utils.timezone_utils import is_market_hours, ET

logger = LogManager().get_logger("TradeExecutorUnified")


def _format_bar_scores(bar_scores: Dict[str, float]) -> str:
    """Format bar scores for logging."""
    if not bar_scores:
        return "{}"
    return ", ".join(f"{k}={v:.4f}" for k, v in bar_scores.items())


def _format_indicators(indicators: Dict[str, float]) -> str:
    """Format indicator values for logging."""
    if not indicators:
        return "{}"
    return ", ".join(f"{k}={v:.4f}" for k, v in indicators.items())


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

        # Take profit type configuration: "percent" or "dollars"
        self.take_profit_type = getattr(trade_exec_config, 'take_profit_type', 'percent')
        self.take_profit_dollars = getattr(trade_exec_config, 'take_profit_dollars', 0.0)
        # Halt trading after hitting dollar target
        self.halt_after_target = getattr(trade_exec_config, 'halt_after_target', False)

        # Halt state tracking (reset at market open each day)
        self._trading_halted = False
        self._halt_date: Optional[date] = None  # The date when trading was halted

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

        self.trade_count = 0

        # Trade details history for UI visualization
        # Maps trade timestamp (ms) -> detailed trade information
        self.trade_details_history: Dict[int, Dict] = {}

        # Log initialization configuration
        logger.debug(f"TradeExecutorUnified initialized:")
        logger.debug(f"  Position size: {self.default_position_size}")
        logger.debug(f"  Stop loss: {self.stop_loss_pct:.2%}")
        if self.take_profit_type == "dollars":
            logger.debug(f"  Take profit: ${self.take_profit_dollars:.2f} (dollar-based)")
            logger.debug(f"  Halt after target: {self.halt_after_target}")
        else:
            logger.debug(f"  Take profit: {self.take_profit_pct:.2%} (percent-based)")
        logger.debug(f"  Trailing stop: {self.trailing_stop_loss} "
                    f"(distance={self.trailing_stop_distance_pct:.2%}, "
                    f"activation={self.trailing_stop_activation_pct:.2%})")
        logger.debug(f"  Ignore bear signals: {self.ignore_bear_signals}")


    def make_decision(self,
                      tick: TickData,
                      indicators: Dict[str, float],
                      bar_scores: Dict[str, float] = None) -> None:
        """
        Make trading decisions based on configuration and current market state
        """
        try:
            timestamp = int(tick.timestamp.timestamp() * 1000) if tick.timestamp else 0
            trade_time = tick.timestamp  # Preserve datetime for logging
            current_price = tick.close  # TickData uses 'close' not 'price'
            bar_scores = defaultdict(float, bar_scores or {})

            # Check if trading halt should be reset at market open
            self._check_halt_reset(trade_time)

            # Log decision context at DEBUG level for detailed tracing
            logger.debug(f"[DECISION] time={tick.timestamp}, price=${current_price:.2f}, "
                         f"in_position={self.portfolio.is_in_position()}, "
                         f"halted={self._trading_halted}, "
                         f"bar_scores=[{_format_bar_scores(bar_scores)}]")

            # Update trailing stop if in position
            if self.portfolio.is_in_position() and self.trailing_stop_loss:
                self._update_trailing_stop(current_price)

            # Check exit conditions first (if in position)
            if self.portfolio.is_in_position():
                logger.debug(f"[POSITION CHECK] Checking exit conditions at ${current_price:.2f}")
                if self._check_exit_conditions(timestamp, current_price, bar_scores, trade_time, indicators):
                    return  # Exit executed, no further action needed

            # Check entry conditions (if not in position)
            if not self.portfolio.is_in_position():
                # Check if trading is halted (dollar target reached)
                if self._trading_halted:
                    logger.debug(f"[TRADING HALTED] No entries allowed - daily target reached on {self._halt_date}")
                    return

                # Always check for signal conflicts to prevent contradictory actions
                if self._has_signal_conflicts(bar_scores):
                    logger.debug(f"[SIGNAL CONFLICT] No action taken - both bull and bear signals active")
                    return

                self._check_entry_conditions(timestamp, current_price, bar_scores, trade_time, indicators)

        except Exception as e:
            logger.error(f"Error in make_decision: {e}", exc_info=True)

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
                                bar_scores: Dict[str, float], trade_time: Optional[datetime] = None,
                                indicators: Optional[Dict[str, float]] = None) -> bool:
        """
        Check if enter_long conditions are triggered for entry

        Returns:
            True if entry was executed
        """
        enter_conditions = getattr(self.monitor_config, 'enter_long', [])

        # Log all entry condition checks
        logger.debug(f"[ENTRY CHECK] Evaluating {len(enter_conditions)} entry conditions at ${current_price:.2f}")

        # Check each enter_long condition
        for condition in enter_conditions:
            bar_name = condition.get('name')
            threshold = condition.get('threshold', 0.5)
            bar_score = bar_scores.get(bar_name, 0.0)

            logger.debug(f"  {bar_name}: score={bar_score:.4f}, threshold={threshold:.4f}, "
                         f"triggered={bar_score >= threshold}")


            if bar_score >= threshold:
                logger.debug(f"[ENTRY SIGNAL TRIGGERED] {bar_name}={bar_score:.4f} >= {threshold:.4f}")
                # Pass trigger details for comprehensive logging
                trigger_info = {
                    'bar_name': bar_name,
                    'bar_score': bar_score,
                    'threshold': threshold
                }
                self._execute_buy(timestamp, current_price, trade_time, bar_scores, indicators, trigger_info)
                return True

        return False

    def _check_exit_conditions(self, timestamp: int, current_price: float,
                               bar_scores: Dict[str, float], trade_time: Optional[datetime] = None,
                               indicators: Optional[Dict[str, float]] = None) -> bool:
        """
        Check all exit conditions: stop loss, take profit, and bear signals

        Returns:
            True if exit was executed
        """
        # Check stop loss (fixed or trailing)
        if self._check_stop_loss(timestamp, current_price, trade_time, bar_scores, indicators):
            return True

        # Check take profit
        if self._check_take_profit(timestamp, current_price, trade_time, bar_scores, indicators):
            return True

        # Check bear signal exits (unless disabled)
        if not self.ignore_bear_signals and self._check_bear_exit_conditions(timestamp, current_price, bar_scores, trade_time, indicators):
            return True

        return False

    def _check_stop_loss(self, timestamp: int, current_price: float, trade_time: Optional[datetime] = None,
                         bar_scores: Optional[Dict[str, float]] = None,
                         indicators: Optional[Dict[str, float]] = None) -> bool:
        """Check stop loss conditions"""
        stop_price = self.trailing_stop_price if self.trailing_stop_loss else self.stop_loss_price
        entry_price = self.portfolio.get_entry_price()

        # Log stop loss check details
        logger.debug(f"[STOP LOSS CHECK] current=${current_price:.2f}, "
                     f"stop_price=${stop_price:.2f}, "
                     f"trailing={self.trailing_stop_loss}")

        if stop_price and current_price <= stop_price:
            stop_type = "TRAILING STOP LOSS" if self.trailing_stop_loss else "FIXED STOP LOSS"
            loss_pct = ((current_price - entry_price) / entry_price * 100) if entry_price else 0
            # Calculate dollar P/L: position_size * (exit_price - entry_price)
            loss_dollars = self.portfolio.position_size * (current_price - entry_price) if entry_price else 0
            time_str = trade_time.strftime("%Y-%m-%d %H:%M:%S") if trade_time else "N/A"

            # Comprehensive exit logging
            logger.debug(f"{'='*60}")
            logger.debug(f"[EXIT - {stop_type}] Position closed")
            logger.debug(f"  Date/Time: {time_str}")
            logger.debug(f"  --- Exit Reason ---")
            logger.debug(f"  Price ${current_price:.2f} <= Stop ${stop_price:.2f}")
            logger.debug(f"  Entry price: ${entry_price:.2f}" if entry_price else "  Entry price: N/A")
            logger.debug(f"  P&L: {loss_pct:.2f}% (${loss_dollars:.2f})")
            logger.debug(f"  Position size: {self.portfolio.position_size}")
            if self.trailing_stop_loss:
                logger.debug(f"  Highest price since entry: ${self.highest_price_since_entry:.2f}"
                            if self.highest_price_since_entry else "  Highest price: N/A")
                logger.debug(f"  Initial stop: ${self.stop_loss_price:.2f}" if self.stop_loss_price else "")
            # Log bar scores at exit
            if bar_scores:
                logger.debug(f"  --- Bar Scores at Exit ---")
                for bar_name, score in bar_scores.items():
                    logger.debug(f"    {bar_name}: {score:.4f}")
            # Log indicator values at exit
            if indicators:
                logger.debug(f"  --- Indicator Values at Exit ---")
                for ind_name, value in indicators.items():
                    logger.debug(f"    {ind_name}: {value:.4f}")
            logger.debug(f"{'='*60}")


            # Store exit trade details for UI visualization
            self.trade_details_history[timestamp] = {
                'type': 'exit',
                'action': f'EXIT - {stop_type}',
                'datetime': time_str,
                'entry_price': entry_price,
                'exit_price': current_price,
                'stop_trigger': stop_price,
                'pnl_pct': loss_pct,
                'pnl_dollars': loss_dollars,
                'position_size': self.portfolio.position_size,
                'trigger_info': {
                    'reason': stop_type,
                    'trigger_price': stop_price,
                    'current_price': current_price
                },
                'bar_scores': dict(bar_scores) if bar_scores else {},
                'indicators': dict(indicators) if indicators else {},
                'highest_price_since_entry': self.highest_price_since_entry,
                'initial_stop': self.stop_loss_price,
                'trailing_stop_loss': self.trailing_stop_loss
            }

            self.portfolio.sell(timestamp, current_price, TradeReason.STOP_LOSS, self.portfolio.position_size)
            self._clear_exit_levels()
            self.trade_count += 1
            return True

        return False

    def _check_take_profit(self, timestamp: int, current_price: float, trade_time: Optional[datetime] = None,
                           bar_scores: Optional[Dict[str, float]] = None,
                           indicators: Optional[Dict[str, float]] = None) -> bool:
        """Check take profit conditions"""
        entry_price = self.portfolio.get_entry_price()

        # Log take profit check details
        logger.debug(f"[TAKE PROFIT CHECK] current=${current_price:.2f}, "
                     f"target=${(self.take_profit_price if self.take_profit_price else 0):.2f}")

        if self.take_profit_price and current_price >= self.take_profit_price:
            profit_pct = ((current_price - entry_price) / entry_price * 100) if entry_price else 0
            # Calculate dollar P/L: position_size * (exit_price - entry_price)
            profit_dollars = self.portfolio.position_size * (current_price - entry_price) if entry_price else 0
            time_str = trade_time.strftime("%Y-%m-%d %H:%M:%S") if trade_time else "N/A"

            # Comprehensive exit logging
            logger.debug(f"{'='*60}")
            logger.debug(f"[EXIT - TAKE PROFIT] Position closed")
            logger.debug(f"  Date/Time: {time_str}")
            logger.debug(f"  --- Exit Reason ---")
            if self.take_profit_type == "dollars":
                logger.debug(f"  Price ${current_price:.2f} >= Target ${self.take_profit_price:.2f} (dollar-based TP)")
            else:
                logger.debug(f"  Price ${current_price:.2f} >= Target ${self.take_profit_price:.2f}")
            logger.debug(f"  Entry price: ${entry_price:.2f}" if entry_price else "  Entry price: N/A")
            logger.debug(f"  P&L: +{profit_pct:.2f}% (${profit_dollars:.2f})")
            logger.debug(f"  Position size: {self.portfolio.position_size}")
            # Log bar scores at exit
            if bar_scores:
                logger.debug(f"  --- Bar Scores at Exit ---")
                for bar_name, score in bar_scores.items():
                    logger.debug(f"    {bar_name}: {score:.4f}")
            # Log indicator values at exit
            if indicators:
                logger.debug(f"  --- Indicator Values at Exit ---")
                for ind_name, value in indicators.items():
                    logger.debug(f"    {ind_name}: {value:.4f}")
            logger.debug(f"{'='*60}")


            # Store exit trade details for UI visualization
            self.trade_details_history[timestamp] = {
                'type': 'exit',
                'action': 'EXIT - TAKE PROFIT',
                'datetime': time_str,
                'entry_price': entry_price,
                'exit_price': current_price,
                'target_price': self.take_profit_price,
                'pnl_pct': profit_pct,
                'pnl_dollars': profit_dollars,
                'position_size': self.portfolio.position_size,
                'take_profit_type': self.take_profit_type,
                'trigger_info': {
                    'reason': 'TAKE PROFIT',
                    'target_price': self.take_profit_price,
                    'current_price': current_price,
                    'take_profit_type': self.take_profit_type
                },
                'bar_scores': dict(bar_scores) if bar_scores else {},
                'indicators': dict(indicators) if indicators else {}
            }

            self.portfolio.sell(timestamp, current_price, TradeReason.TAKE_PROFIT, self.portfolio.position_size)
            self._clear_exit_levels()
            self.trade_count += 1

            # Activate trading halt if configured (dollar mode only)
            if self.take_profit_type == "dollars" and self.halt_after_target:
                self._activate_trading_halt(trade_time)

            return True

        return False

    def _check_bear_exit_conditions(self, timestamp: int, current_price: float,
                                    bar_scores: Dict[str, float], trade_time: Optional[datetime] = None,
                                    indicators: Optional[Dict[str, float]] = None) -> bool:
        """Check bear signal exit conditions"""
        exit_conditions = getattr(self.monitor_config, 'exit_long', [])
        entry_price = self.portfolio.get_entry_price()

        # Log all exit condition checks
        logger.debug(f"[BEAR SIGNAL CHECK] Evaluating {len(exit_conditions)} exit conditions")

        for condition in exit_conditions:
            bar_name = condition.get('name')
            threshold = condition.get('threshold', 0.5)
            bar_score = bar_scores.get(bar_name, 0.0)

            logger.debug(f"  {bar_name}: score={bar_score:.4f}, threshold={threshold:.4f}, "
                         f"triggered={bar_score >= threshold}")


            if bar_score >= threshold:
                pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price else 0
                time_str = trade_time.strftime("%Y-%m-%d %H:%M:%S") if trade_time else "N/A"

                # Comprehensive exit logging
                logger.debug(f"{'='*60}")
                logger.debug(f"[EXIT - BEAR SIGNAL] Position closed")
                logger.debug(f"  Date/Time: {time_str}")
                logger.debug(f"  --- Exit Reason ---")
                logger.debug(f"  Trigger bar: {bar_name}")
                logger.debug(f"  Bar score: {bar_score:.4f} >= threshold {threshold:.4f}")
                logger.debug(f"  Entry price: ${entry_price:.2f}" if entry_price else "  Entry price: N/A")
                logger.debug(f"  Exit price: ${current_price:.2f}")
                logger.debug(f"  P&L: {pnl_pct:+.2f}%")
                logger.debug(f"  Position size: {self.portfolio.position_size}")
                # Log all bar scores
                if bar_scores:
                    logger.debug(f"  --- All Bar Scores ---")
                    for bn, score in bar_scores.items():
                        logger.debug(f"    {bn}: {score:.4f}")
                # Log indicator values at exit
                if indicators:
                    logger.debug(f"  --- Indicator Values at Exit ---")
                    for ind_name, value in indicators.items():
                        logger.debug(f"    {ind_name}: {value:.4f}")
                logger.debug(f"{'='*60}")


                # Store exit trade details for UI visualization
                self.trade_details_history[timestamp] = {
                    'type': 'exit',
                    'action': 'EXIT - BEAR SIGNAL',
                    'datetime': time_str,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'pnl_pct': pnl_pct,
                    'position_size': self.portfolio.position_size,
                    'trigger_info': {
                        'reason': 'BEAR SIGNAL',
                        'bar_name': bar_name,
                        'bar_score': bar_score,
                        'threshold': threshold
                    },
                    'bar_scores': dict(bar_scores) if bar_scores else {},
                    'indicators': dict(indicators) if indicators else {}
                }

                self.portfolio.sell(timestamp, current_price, TradeReason.EXIT_LONG, self.portfolio.position_size)
                self._clear_exit_levels()
                self.trade_count += 1
                return True

        return False

    def _execute_buy(self, timestamp: int, current_price: float, trade_time: Optional[datetime] = None,
                     bar_scores: Optional[Dict[str, float]] = None,
                     indicators: Optional[Dict[str, float]] = None,
                     trigger_info: Optional[Dict] = None) -> None:
        """
        Execute buy order and set stop loss and take profit levels
        """
        # Calculate stop loss price (always percentage-based)
        self.stop_loss_price = current_price * (1.0 - self.stop_loss_pct)

        # Calculate take profit price based on type
        if self.take_profit_type == "dollars":
            # Dollar-based: target price = entry + (target_dollars / position_size)
            # price_gain_per_share = target_dollars / shares
            if self.default_position_size > 0:
                price_gain_per_share = self.take_profit_dollars / self.default_position_size
                self.take_profit_price = current_price + price_gain_per_share
            else:
                # Fallback to percentage if position size is 0
                self.take_profit_price = current_price * (1.0 + self.take_profit_pct)
        else:
            # Percentage-based (default)
            self.take_profit_price = current_price * (1.0 + self.take_profit_pct)

        # Initialize trailing stop if enabled
        if self.trailing_stop_loss:
            # Trailing stop starts at the same level as fixed stop loss
            self.trailing_stop_price = self.stop_loss_price
            self.highest_price_since_entry = current_price

        # Execute the buy
        self.portfolio.buy(timestamp, current_price, TradeReason.ENTER_LONG, self.default_position_size)

        # Format datetime for logging
        time_str = trade_time.strftime("%Y-%m-%d %H:%M:%S") if trade_time else "N/A"

        # Comprehensive entry logging
        logger.debug(f"{'='*60}")
        logger.debug(f"[ENTRY - LONG] Position opened")
        logger.debug(f"  Date/Time: {time_str}")
        logger.debug(f"  Entry price: ${current_price:.2f}")
        logger.debug(f"  Position size: {self.default_position_size}")
        # Log trigger reason
        if trigger_info:
            logger.debug(f"  --- Trigger Reason ---")
            logger.debug(f"  Trigger bar: {trigger_info['bar_name']}")
            logger.debug(f"  Bar score: {trigger_info['bar_score']:.4f} >= threshold {trigger_info['threshold']:.4f}")
        # Log all bar scores
        if bar_scores:
            logger.debug(f"  --- All Bar Scores ---")
            for bar_name, score in bar_scores.items():
                logger.debug(f"    {bar_name}: {score:.4f}")
        # Log indicator values
        if indicators:
            logger.debug(f"  --- Indicator Values ---")
            for ind_name, value in indicators.items():
                logger.debug(f"    {ind_name}: {value:.4f}")
        logger.debug(f"  --- Exit Targets ---")
        logger.debug(f"  Stop loss: ${self.stop_loss_price:.2f} ({self.stop_loss_pct:.2%} below entry)")
        if self.take_profit_type == "dollars":
            logger.debug(f"  Take profit: ${self.take_profit_price:.2f} (${self.take_profit_dollars:.2f} dollar target)")
        else:
            logger.debug(f"  Take profit: ${self.take_profit_price:.2f} ({self.take_profit_pct:.2%} above entry)")
        if self.trailing_stop_loss:
            logger.debug(f"  Trailing stop enabled: initial=${self.trailing_stop_price:.2f}")
            logger.debug(f"    Distance: {self.trailing_stop_distance_pct:.2%}")
            logger.debug(f"    Activation: {self.trailing_stop_activation_pct:.2%}")
        logger.debug(f"  Trade #{self.trade_count + 1}")
        logger.debug(f"{'='*60}")

        # Store trade details for UI visualization
        self.trade_details_history[timestamp] = {
            'type': 'entry',
            'action': 'ENTRY - LONG',
            'datetime': time_str,
            'price': current_price,
            'position_size': self.default_position_size,
            'trigger_info': trigger_info,
            'bar_scores': dict(bar_scores) if bar_scores else {},
            'indicators': dict(indicators) if indicators else {},
            'stop_loss': self.stop_loss_price,
            'take_profit': self.take_profit_price,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'take_profit_type': self.take_profit_type,
            'take_profit_dollars': self.take_profit_dollars,
            'trailing_stop_loss': self.trailing_stop_loss,
            'trailing_stop_price': self.trailing_stop_price,
            'trailing_stop_distance_pct': self.trailing_stop_distance_pct,
            'trailing_stop_activation_pct': self.trailing_stop_activation_pct,
            'trade_number': self.trade_count + 1
        }


    def _update_trailing_stop(self, current_price: float) -> None:
        """
        Update trailing stop loss price based on current price movement
        """
        if not self.highest_price_since_entry:
            return

        # Update highest price since entry
        if current_price > self.highest_price_since_entry:
            old_highest = self.highest_price_since_entry
            self.highest_price_since_entry = current_price

            # Calculate new trailing stop price
            new_trailing_stop = current_price * (1.0 - self.trailing_stop_distance_pct)

            # Only move trailing stop up, never down
            if new_trailing_stop > self.trailing_stop_price:
                old_trailing_stop = self.trailing_stop_price
                self.trailing_stop_price = new_trailing_stop

                logger.debug(f"[TRAILING STOP UPDATE] price=${current_price:.2f}, "
                             f"new_high=${self.highest_price_since_entry:.2f} (was ${old_highest:.2f}), "
                             f"stop=${self.trailing_stop_price:.2f} (was ${old_trailing_stop:.2f})")


    def _clear_exit_levels(self) -> None:
        """Clear all exit levels after trade completion"""
        self.stop_loss_price = None
        self.take_profit_price = None
        self.trailing_stop_price = None
        self.highest_price_since_entry = None

    def _check_halt_reset(self, trade_time: Optional[datetime]) -> None:
        """
        Check if trading halt should be reset at the start of a new trading day.

        Halt is reset when:
        - We're in a new trading day (different date from when halt was set)
        - Current time is during market hours (after 9:30 AM ET)
        """
        if not self._trading_halted or not self._halt_date or not trade_time:
            return

        # Convert trade time to ET for date comparison
        try:
            trade_time_et = trade_time.astimezone(ET)
            current_date = trade_time_et.date()

            # Check if it's a new trading day
            if current_date > self._halt_date:
                # Verify we're in market hours (after market open)
                if is_market_hours(trade_time):
                    logger.info(f"[HALT RESET] New trading day detected. "
                               f"Halt date: {self._halt_date}, Current: {current_date}. "
                               f"Trading resumed at {trade_time_et.strftime('%Y-%m-%d %H:%M:%S')} ET")
                    self._trading_halted = False
                    self._halt_date = None
        except Exception as e:
            logger.warning(f"Error checking halt reset: {e}")

    def _activate_trading_halt(self, trade_time: Optional[datetime]) -> None:
        """Activate trading halt after hitting dollar target."""
        self._trading_halted = True

        if trade_time:
            try:
                trade_time_et = trade_time.astimezone(ET)
                self._halt_date = trade_time_et.date()
                logger.info(f"[TRADING HALTED] Dollar profit target reached. "
                           f"Trading halted for the rest of {self._halt_date}. "
                           f"Will resume at next market open.")
            except Exception as e:
                self._halt_date = date.today()
                logger.warning(f"Error setting halt date: {e}, using today's date")
        else:
            self._halt_date = date.today()
            logger.info(f"[TRADING HALTED] Dollar profit target reached. "
                       f"Trading halted for rest of day.")

    def is_trading_halted(self) -> bool:
        """Check if trading is currently halted."""
        return self._trading_halted

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
            'take_profit_type': self.take_profit_type,
            'take_profit_dollars': self.take_profit_dollars,
            'halt_after_target': self.halt_after_target,
            'trading_halted': self._trading_halted,
            'halt_date': str(self._halt_date) if self._halt_date else None,
            'trailing_stop_loss': self.trailing_stop_loss,
            'ignore_bear_signals': self.ignore_bear_signals,
            'total_trades': len(self.portfolio.trade_history)
        }