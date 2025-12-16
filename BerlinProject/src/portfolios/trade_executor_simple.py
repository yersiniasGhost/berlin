from typing import Dict
from collections import defaultdict

from models.tick_data import TickData

import sys
import os
sys.path.append(os.path.dirname(__file__))

from trade_executor import TradeExecutor
from portfolio_tool import TradeReason
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("TradeExecutorSimple")


class TradeExecutorSimple(TradeExecutor):
    """
    Simple trade executor that:
    - Buys when bull bars trigger (and not in position)
    - Sells when bear bars trigger (and in position)
    - Uses trailing stop loss
    """

    def __init__(self,
                 monitor_config,
                 default_position_size: float = 10.0,
                 stop_loss_pct: float = 0.005):
        super().__init__(monitor_config, default_position_size, stop_loss_pct)
        self.trailing_stop_price = 0.0
        logger.info(
            f"TradeExecutorSimple initialized with position size: {default_position_size}, stop loss: {stop_loss_pct}%")

    def make_decision(self,
                      tick: TickData,
                      indicators: Dict[str, float],
                      bar_scores: Dict[str, float] = None) -> None:
        """
        Make trading decisions based on enter_long/exit_long conditions with trailing stop loss
        """
        try:
            timestamp = int(tick.timestamp.timestamp() * 1000) if tick.timestamp else 0
            bar_scores = defaultdict(float, bar_scores or {})

            # Get enter_long and exit_long conditions (now arrays)
            enter_conditions = getattr(self.monitor_config, 'enter_long', [])
            exit_conditions = getattr(self.monitor_config, 'exit_long', [])
            bars_config = getattr(self.monitor_config, 'bars', {})

            # ARE WE IN A POSITION?
            if self.portfolio.position_size == 0:
                # NOT IN POSITION - Look for BUY signals
                # Check each enter_long condition
                for condition in enter_conditions:
                    bar_name = condition.get('name')
                    threshold = condition.get('threshold', 0.5)
                    bar_score = bar_scores.get(bar_name, 0.0)

                    if bar_score >= threshold:
                        self.portfolio.buy(
                            time=timestamp,
                            price=tick.close,
                            reason=TradeReason.ENTER_LONG,
                            size=self.default_position_size
                        )

                        # Set initial trailing stop loss
                        stop_loss_decimal = self.stop_loss_pct / 100.0 if self.stop_loss_pct > 1 else self.stop_loss_pct
                        self.trailing_stop_price = tick.close * (1 - stop_loss_decimal)

                        logger.info(
                            f"BUY executed: {self.default_position_size} @ ${tick.close:.2f} "
                            f"Stop: ${self.trailing_stop_price:.2f} "
                            f"Condition: {bar_name} = {bar_score:.3f} >= {threshold:.3f}")
                        return

            else:
                # IN POSITION - Look for SELL signals or stop loss

                # Update trailing stop loss (move up with price, never down)
                stop_loss_decimal = self.stop_loss_pct / 100.0 if self.stop_loss_pct > 1 else self.stop_loss_pct
                new_stop_price = tick.close * (1 - stop_loss_decimal)
                if new_stop_price > self.trailing_stop_price:
                    self.trailing_stop_price = new_stop_price

                # Check exit_long conditions first
                for condition in exit_conditions:
                    bar_name = condition.get('name')
                    threshold = condition.get('threshold', 0.8)
                    bar_score = bar_scores.get(bar_name, 0.0)

                    if bar_score >= threshold:
                        self.portfolio.exit_long(time=timestamp, price=tick.close)
                        logger.info(f"SELL executed @ ${tick.close:.2f} "
                                    f"Condition: {bar_name} = {bar_score:.3f} >= {threshold:.3f}")
                        self.trailing_stop_price = 0.0
                        return

                # Check trailing stop loss
                if tick.close <= self.trailing_stop_price:
                    self.portfolio.exit_long(time=timestamp, price=tick.close, reason=TradeReason.STOP_LOSS)
                    logger.info(f"STOP LOSS executed @ ${tick.close:.2f} (Stop: ${self.trailing_stop_price:.2f})")
                    self.trailing_stop_price = 0.0
                    return

        except Exception as e:
            logger.error(f"Error processing indicators: {e}")