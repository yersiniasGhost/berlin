# portfolios/trade_executor_unified.py

from typing import Dict, Optional, List
from datetime import datetime
from collections import defaultdict

from models.monitor_configuration import MonitorConfiguration
from models.tick_data import TickData
from portfolios.portfolio_tool import Portfolio, TradeReason
from mlf_utils.log_manager import LogManager

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

        # Trade details history for UI visualization
        # Maps trade timestamp (ms) -> detailed trade information
        self.trade_details_history: Dict[int, Dict] = {}

        # Log initialization configuration
        logger.info(f"TradeExecutorUnified initialized:")
        logger.info(f"  Position size: {self.default_position_size}")
        logger.info(f"  Stop loss: {self.stop_loss_pct:.2%}")
        logger.info(f"  Take profit: {self.take_profit_pct:.2%}")
        logger.info(f"  Trailing stop: {self.trailing_stop_loss} "
                    f"(distance={self.trailing_stop_distance_pct:.2%}, "
                    f"activation={self.trailing_stop_activation_pct:.2%})")
        logger.info(f"  Ignore bear signals: {self.ignore_bear_signals}")

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
            trade_time = tick.timestamp  # Preserve datetime for logging
            current_price = tick.close  # TickData uses 'close' not 'price'
            bar_scores = defaultdict(float, bar_scores or {})

            # Log decision context at DEBUG level for detailed tracing
            logger.debug(f"[DECISION] time={tick.timestamp}, price=${current_price:.2f}, "
                         f"in_position={self.portfolio.is_in_position()}, "
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
                # Always check for signal conflicts to prevent contradictory actions
                if self._has_signal_conflicts(bar_scores):
                    logger.debug(f"[SIGNAL CONFLICT] No action taken - both bull and bear signals active")
                    if self.debug_mode and self.trade_count < 10:
                        print("Signal conflict detected - no action taken")
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

            if self.debug_mode and self.trade_count < 10:
                print(f"Entry Check: {bar_name} = {bar_score:.3f} vs threshold {threshold:.3f}")

            if bar_score >= threshold:
                logger.info(f"[ENTRY SIGNAL TRIGGERED] {bar_name}={bar_score:.4f} >= {threshold:.4f}")
                if self.debug_mode:
                    print(f"ENTRY SIGNAL: {bar_name} = {bar_score:.3f} >= {threshold:.3f}")
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
            time_str = trade_time.strftime("%Y-%m-%d %H:%M:%S") if trade_time else "N/A"

            # Comprehensive exit logging
            logger.info(f"{'='*60}")
            logger.info(f"[EXIT - {stop_type}] Position closed")
            logger.info(f"  Date/Time: {time_str}")
            logger.info(f"  --- Exit Reason ---")
            logger.info(f"  Price ${current_price:.2f} <= Stop ${stop_price:.2f}")
            logger.info(f"  Entry price: ${entry_price:.2f}" if entry_price else "  Entry price: N/A")
            logger.info(f"  P&L: {loss_pct:.2f}%")
            logger.info(f"  Position size: {self.portfolio.position_size}")
            if self.trailing_stop_loss:
                logger.info(f"  Highest price since entry: ${self.highest_price_since_entry:.2f}"
                            if self.highest_price_since_entry else "  Highest price: N/A")
                logger.info(f"  Initial stop: ${self.stop_loss_price:.2f}" if self.stop_loss_price else "")
            # Log bar scores at exit
            if bar_scores:
                logger.info(f"  --- Bar Scores at Exit ---")
                for bar_name, score in bar_scores.items():
                    logger.info(f"    {bar_name}: {score:.4f}")
            # Log indicator values at exit
            if indicators:
                logger.info(f"  --- Indicator Values at Exit ---")
                for ind_name, value in indicators.items():
                    logger.info(f"    {ind_name}: {value:.4f}")
            logger.info(f"{'='*60}")

            if self.debug_mode:
                print(f"{stop_type} HIT: ${current_price:.2f} <= ${stop_price:.2f}")

            # Store exit trade details for UI visualization
            self.trade_details_history[timestamp] = {
                'type': 'exit',
                'action': f'EXIT - {stop_type}',
                'datetime': time_str,
                'entry_price': entry_price,
                'exit_price': current_price,
                'stop_trigger': stop_price,
                'pnl_pct': loss_pct,
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
            time_str = trade_time.strftime("%Y-%m-%d %H:%M:%S") if trade_time else "N/A"

            # Comprehensive exit logging
            logger.info(f"{'='*60}")
            logger.info(f"[EXIT - TAKE PROFIT] Position closed")
            logger.info(f"  Date/Time: {time_str}")
            logger.info(f"  --- Exit Reason ---")
            logger.info(f"  Price ${current_price:.2f} >= Target ${self.take_profit_price:.2f}")
            logger.info(f"  Entry price: ${entry_price:.2f}" if entry_price else "  Entry price: N/A")
            logger.info(f"  P&L: +{profit_pct:.2f}%")
            logger.info(f"  Position size: {self.portfolio.position_size}")
            # Log bar scores at exit
            if bar_scores:
                logger.info(f"  --- Bar Scores at Exit ---")
                for bar_name, score in bar_scores.items():
                    logger.info(f"    {bar_name}: {score:.4f}")
            # Log indicator values at exit
            if indicators:
                logger.info(f"  --- Indicator Values at Exit ---")
                for ind_name, value in indicators.items():
                    logger.info(f"    {ind_name}: {value:.4f}")
            logger.info(f"{'='*60}")

            if self.debug_mode:
                print(f"TAKE PROFIT HIT: ${current_price:.2f} >= ${self.take_profit_price:.2f}")

            # Store exit trade details for UI visualization
            self.trade_details_history[timestamp] = {
                'type': 'exit',
                'action': 'EXIT - TAKE PROFIT',
                'datetime': time_str,
                'entry_price': entry_price,
                'exit_price': current_price,
                'target_price': self.take_profit_price,
                'pnl_pct': profit_pct,
                'position_size': self.portfolio.position_size,
                'trigger_info': {
                    'reason': 'TAKE PROFIT',
                    'target_price': self.take_profit_price,
                    'current_price': current_price
                },
                'bar_scores': dict(bar_scores) if bar_scores else {},
                'indicators': dict(indicators) if indicators else {}
            }

            self.portfolio.sell(timestamp, current_price, TradeReason.TAKE_PROFIT, self.portfolio.position_size)
            self._clear_exit_levels()
            self.trade_count += 1
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

            if self.debug_mode and self.trade_count < 10:
                print(f"Exit Check: {bar_name} = {bar_score:.3f} vs threshold {threshold:.3f}")

            if bar_score >= threshold:
                pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price else 0
                time_str = trade_time.strftime("%Y-%m-%d %H:%M:%S") if trade_time else "N/A"

                # Comprehensive exit logging
                logger.info(f"{'='*60}")
                logger.info(f"[EXIT - BEAR SIGNAL] Position closed")
                logger.info(f"  Date/Time: {time_str}")
                logger.info(f"  --- Exit Reason ---")
                logger.info(f"  Trigger bar: {bar_name}")
                logger.info(f"  Bar score: {bar_score:.4f} >= threshold {threshold:.4f}")
                logger.info(f"  Entry price: ${entry_price:.2f}" if entry_price else "  Entry price: N/A")
                logger.info(f"  Exit price: ${current_price:.2f}")
                logger.info(f"  P&L: {pnl_pct:+.2f}%")
                logger.info(f"  Position size: {self.portfolio.position_size}")
                # Log all bar scores
                if bar_scores:
                    logger.info(f"  --- All Bar Scores ---")
                    for bn, score in bar_scores.items():
                        logger.info(f"    {bn}: {score:.4f}")
                # Log indicator values at exit
                if indicators:
                    logger.info(f"  --- Indicator Values at Exit ---")
                    for ind_name, value in indicators.items():
                        logger.info(f"    {ind_name}: {value:.4f}")
                logger.info(f"{'='*60}")

                if self.debug_mode:
                    print(f"EXIT SIGNAL: {bar_name} = {bar_score:.3f} >= {threshold:.3f}")

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

        # Format datetime for logging
        time_str = trade_time.strftime("%Y-%m-%d %H:%M:%S") if trade_time else "N/A"

        # Comprehensive entry logging
        logger.info(f"{'='*60}")
        logger.info(f"[ENTRY - LONG] Position opened")
        logger.info(f"  Date/Time: {time_str}")
        logger.info(f"  Entry price: ${current_price:.2f}")
        logger.info(f"  Position size: {self.default_position_size}")
        # Log trigger reason
        if trigger_info:
            logger.info(f"  --- Trigger Reason ---")
            logger.info(f"  Trigger bar: {trigger_info['bar_name']}")
            logger.info(f"  Bar score: {trigger_info['bar_score']:.4f} >= threshold {trigger_info['threshold']:.4f}")
        # Log all bar scores
        if bar_scores:
            logger.info(f"  --- All Bar Scores ---")
            for bar_name, score in bar_scores.items():
                logger.info(f"    {bar_name}: {score:.4f}")
        # Log indicator values
        if indicators:
            logger.info(f"  --- Indicator Values ---")
            for ind_name, value in indicators.items():
                logger.info(f"    {ind_name}: {value:.4f}")
        logger.info(f"  --- Exit Targets ---")
        logger.info(f"  Stop loss: ${self.stop_loss_price:.2f} ({self.stop_loss_pct:.2%} below entry)")
        logger.info(f"  Take profit: ${self.take_profit_price:.2f} ({self.take_profit_pct:.2%} above entry)")
        if self.trailing_stop_loss:
            logger.info(f"  Trailing stop enabled: initial=${self.trailing_stop_price:.2f}")
            logger.info(f"    Distance: {self.trailing_stop_distance_pct:.2%}")
            logger.info(f"    Activation: {self.trailing_stop_activation_pct:.2%}")
        logger.info(f"  Trade #{self.trade_count + 1}")
        logger.info(f"{'='*60}")

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
            'trailing_stop_loss': self.trailing_stop_loss,
            'trailing_stop_price': self.trailing_stop_price,
            'trailing_stop_distance_pct': self.trailing_stop_distance_pct,
            'trailing_stop_activation_pct': self.trailing_stop_activation_pct,
            'trade_number': self.trade_count + 1
        }

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