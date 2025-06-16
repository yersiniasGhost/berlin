from typing import Dict
from collections import defaultdict
import logging

from models.tick_data import TickData

import sys
import os
sys.path.append(os.path.dirname(__file__))

from trade_executor import TradeExecutor
from portfolio_tool import TradeReason

logger = logging.getLogger('TradeExecutorSimple')


class TradeExecutorSimple(TradeExecutor):
    """
    Simple trade executor that:
    - Buys when bull bars trigger (and not in position)
    - Sells when bear bars trigger (and in position)
    - Uses trailing stop loss
    """

    def __init__(self,
                 monitor_config,
                 default_position_size: float = 1.0,
                 stop_loss_pct: float = 0.5):
        super().__init__(monitor_config, default_position_size, stop_loss_pct)
        self.trailing_stop_price = 0.0
        logger.info(
            f"TradeExecutorSimple initialized with position size: {default_position_size}, stop loss: {stop_loss_pct}%")

    def make_decision(self,
                      tick: TickData,
                      indicators: Dict[str, float],
                      bar_scores: Dict[str, float] = None) -> None:
        """
        Make trading decisions based on bull/bear bar scores vs thresholds with trailing stop loss
        """
        try:
            timestamp = int(tick.timestamp.timestamp() * 1000) if tick.timestamp else 0
            bar_scores = defaultdict(float, bar_scores or {})

            threshold = getattr(self.monitor_config, 'threshold')
            bear_threshold = getattr(self.monitor_config, 'bear_threshold')
            bars_config = getattr(self.monitor_config, 'bars', {})

            # ARE WE IN A POSITION?
            if self.portfolio.position_size == 0:
                # NOT IN POSITION - Look for BUY signals
                for bar_name, bar_config in bars_config.items():
                    bar_score = bar_scores[bar_name]
                    bar_type = bar_config.get('type', '')

                    if bar_type == 'bull' and bar_score >= threshold:
                        self.portfolio.buy(
                            time=timestamp,
                            price=tick.close,
                            reason=TradeReason.ENTER_LONG,
                            size=self.default_position_size
                        )

                        # Set initial trailing stop loss
                        # Convert percentage to decimal if needed
                        stop_loss_decimal = self.stop_loss_pct / 100.0 if self.stop_loss_pct > 1 else self.stop_loss_pct
                        self.trailing_stop_price = tick.close * (1 - stop_loss_decimal)

                        logger.info(
                            f"BUY executed: {self.default_position_size} @ ${tick.close:.2f} Stop: ${self.trailing_stop_price:.2f}")
                        return

            else:
                # IN POSITION - Look for SELL signals or stop loss

                # Update trailing stop loss (move up with price, never down)
                stop_loss_decimal = self.stop_loss_pct / 100.0 if self.stop_loss_pct > 1 else self.stop_loss_pct
                new_stop_price = tick.close * (1 - stop_loss_decimal)
                if new_stop_price > self.trailing_stop_price:
                    self.trailing_stop_price = new_stop_price

                # Check bear trigger first
                for bar_name, bar_config in bars_config.items():
                    bar_score = bar_scores[bar_name]
                    bar_type = bar_config.get('type', '')

                    if bar_type == 'bear' and bar_score >= bear_threshold:
                        self.portfolio.exit_long(time=timestamp, price=tick.close)
                        logger.info(f"SELL executed @ ${tick.close:.2f} (Bear signal)")
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
