"""
MlfIndividualStats - Extended Individual Statistics for MLF Optimization

This module extends IndividualStats to include pre-calculated performance metrics
that are used by the optimizer visualization routes, eliminating the need to
recalculate these metrics during visualization.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np
import math

from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
from portfolios.portfolio_tool import Portfolio, TradeReason
from models.tick_data import TickData


@dataclass
class MlfIndividualStats(IndividualStats):
    """
    Extended IndividualStats for MLF optimization with pre-calculated
    performance metrics to avoid recalculation in visualization routes.

    All metrics are calculated once during fitness evaluation and stored
    for efficient access during visualization and analysis.
    """

    # ===== Trade Statistics =====
    total_trades: int = 0
    winning_trades_count: int = 0
    losing_trades_count: int = 0

    # ===== P&L Metrics =====
    total_pnl: float = 0.0          # Cumulative P&L percentage
    avg_win: float = 0.0            # Average winning trade P&L
    avg_loss: float = 0.0           # Average losing trade P&L
    market_return: float = 0.0      # Buy-and-hold return

    # ===== Trade History (for visualization) =====
    trade_history: List[Dict] = field(default_factory=list)
    pnl_history: List[Dict] = field(default_factory=list)

    # ===== Distribution Data (for histogram charts) =====
    winning_trades_distribution: List[tuple] = field(default_factory=list)
    losing_trades_distribution: List[tuple] = field(default_factory=list)

    # ===== Raw Data References (optional, for advanced analysis) =====
    # Note: These should NOT be serialized/pickled for large-scale storage
    # MEMORY OPTIMIZATION: These are cleared after metric calculation to prevent memory bloat
    portfolio_instance: Optional[Portfolio] = field(default=None, repr=False)
    tick_history: Optional[List[TickData]] = field(default=None, repr=False)

    # Flag to control whether to retain raw data (default: False for memory efficiency)
    _retain_raw_data: bool = field(default=False, repr=False)


    @classmethod
    def from_backtest(cls, index: int, fitness_values: np.array, individual,
                     portfolio: Portfolio, tick_history: List[TickData],
                     retain_raw_data: bool = False):
        """
        Factory method to create MlfIndividualStats with all metrics calculated.

        This method should be called from mlf_fitness_calculator.__calculate_individual_stats()
        to create fully populated stats instances.

        MEMORY OPTIMIZATION: By default, portfolio and tick_history references are cleared
        after metrics are calculated. Set retain_raw_data=True only if you need them later.

        Args:
            index: Individual's index in population
            fitness_values: Array of objective function values
            individual: MlfIndividual instance
            portfolio: Portfolio result from backtest
            tick_history: Historical tick data for market return calculation
            retain_raw_data: If True, keep portfolio/tick_history references (default: False)

        Returns:
            MlfIndividualStats instance with all metrics pre-calculated
        """
        instance = cls(
            index=index,
            fitness_values=fitness_values,
            individual=individual,
            portfolio_instance=portfolio,
            tick_history=tick_history,
            _retain_raw_data=retain_raw_data
        )

        # Calculate all metrics in order
        instance._extract_trade_history(portfolio)
        instance._calculate_trade_statistics()
        instance._calculate_pnl_metrics()
        instance._calculate_market_return()
        instance._calculate_distributions()

        # MEMORY OPTIMIZATION: Clear large data references after calculation
        # unless explicitly requested to retain them
        if not retain_raw_data:
            instance._clear_raw_data()

        return instance

    def _clear_raw_data(self):
        """
        Clear large raw data references to free memory.
        Called automatically after metrics calculation unless retain_raw_data=True.
        """
        self.portfolio_instance = None
        self.tick_history = None


    def _extract_trade_history(self, portfolio: Portfolio):
        """
        Extract trade history and P&L timeline from portfolio.

        This mirrors the logic from optimizer_routes.py:extract_trade_history_and_pnl_from_portfolio()
        """
        if not portfolio or not hasattr(portfolio, 'trade_history') or not portfolio.trade_history:
            return

        cumulative_pnl = 0.0
        trade_pairs = []  # Store entry/exit pairs for P&L calculation

        for i, trade in enumerate(portfolio.trade_history):
            # Determine trade type based on TradeReason
            trade_type = 'buy'
            if trade.reason in [TradeReason.EXIT_LONG, TradeReason.STOP_LOSS, TradeReason.TAKE_PROFIT]:
                trade_type = 'sell'

            # Convert timestamp to milliseconds for JavaScript
            timestamp_ms = int(trade.time.timestamp() * 1000) if hasattr(trade.time, 'timestamp') else trade.time

            trade_entry = {
                'timestamp': timestamp_ms,
                'type': trade_type,
                'price': trade.price,
                'quantity': trade.size,
                'reason': trade.reason.value if hasattr(trade.reason, 'value') else str(trade.reason)
            }
            self.trade_history.append(trade_entry)

            # Calculate P&L for completed trades (entry -> exit pairs)
            if trade_type == 'buy':
                trade_pairs.append({'entry': trade, 'exit': None})
            elif trade_type == 'sell' and trade_pairs:
                for pair in reversed(trade_pairs):
                    if pair['exit'] is None:
                        pair['exit'] = trade
                        entry_price = pair['entry'].price
                        exit_price = trade.price
                        trade_pnl = ((exit_price - entry_price) / entry_price) * 100.0
                        cumulative_pnl += trade_pnl

                        self.pnl_history.append({
                            'timestamp': timestamp_ms,
                            'cumulative_pnl': cumulative_pnl,
                            'trade_pnl': trade_pnl
                        })
                        break


    def _calculate_trade_statistics(self):
        """
        Calculate basic trade counts from trade history and P&L data.

        This mirrors the logic from optimizer_routes.py:generate_optimizer_chart_data()
        """
        # Count sell trades (exits) as total trades
        self.total_trades = len([t for t in self.trade_history if t['type'] == 'sell'])

        # Count winning and losing trades from P&L history
        winning_pnls = [p for p in self.pnl_history if p['trade_pnl'] > 0]
        losing_pnls = [p for p in self.pnl_history if p['trade_pnl'] < 0]

        self.winning_trades_count = len(winning_pnls)
        self.losing_trades_count = len(losing_pnls)


    def _calculate_pnl_metrics(self):
        """
        Calculate P&L averages and total from P&L history.

        This mirrors the logic from optimizer_routes.py:generate_optimizer_chart_data()
        """
        if not self.pnl_history:
            self.total_pnl = 0.0
            self.avg_win = 0.0
            self.avg_loss = 0.0
            return

        # Total P&L is the final cumulative value
        self.total_pnl = self.pnl_history[-1]['cumulative_pnl']

        # Calculate average win and loss
        winning_trades = [p['trade_pnl'] for p in self.pnl_history if p['trade_pnl'] > 0]
        losing_trades = [p['trade_pnl'] for p in self.pnl_history if p['trade_pnl'] < 0]

        self.avg_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0.0
        self.avg_loss = sum(losing_trades) / len(losing_trades) if losing_trades else 0.0


    def _calculate_market_return(self):
        """
        Calculate market return (buy-and-hold from first to last close).

        This mirrors the logic from optimizer_routes.py:generate_optimizer_chart_data()
        """
        self.market_return = -6969.0  # Default error value

        if not self.tick_history or len(self.tick_history) < 2:
            return

        try:
            first_close = self.tick_history[0].close
            last_close = self.tick_history[-1].close
            self.market_return = ((last_close - first_close) / first_close) * 100.0
        except (AttributeError, ZeroDivisionError, IndexError):
            pass


    def _calculate_distributions(self):
        """
        Calculate histogram distributions for winning and losing trades.

        This mirrors the logic from optimizer_routes.py:generate_optimizer_chart_data()
        """
        if not self.pnl_history:
            return

        # Separate winning and losing trades
        winning_trades = [p['trade_pnl'] for p in self.pnl_history if p['trade_pnl'] > 0]
        losing_trades = [p['trade_pnl'] for p in self.pnl_history if p['trade_pnl'] < 0]

        # Calculate winning trades distribution
        if winning_trades:
            self.winning_trades_distribution = self._create_histogram_bins(winning_trades)

        # Calculate losing trades distribution
        if losing_trades:
            self.losing_trades_distribution = self._create_histogram_bins(losing_trades)


    @staticmethod
    def _create_histogram_bins(trade_values: List[float]) -> List[tuple]:
        """
        Create histogram bins with dynamic bin sizing.

        This mirrors the binning logic from optimizer_routes.py:generate_optimizer_chart_data()

        Args:
            trade_values: List of P&L values to bin

        Returns:
            List of (bin_label, count) tuples
        """
        if not trade_values:
            return []

        min_val = min(trade_values)
        max_val = max(trade_values)
        range_val = max_val - min_val

        # Dynamic bin size based on range
        if range_val <= 5:
            bin_size = 0.25
        elif range_val <= 10:
            bin_size = 0.5
        elif range_val <= 20:
            bin_size = 1.0
        else:
            bin_size = 2.0

        bin_start = math.floor(min_val / bin_size) * bin_size
        bin_end = math.ceil(max_val / bin_size) * bin_size

        # Create bins
        bins = {}
        for i in range(int((bin_end - bin_start) / bin_size) + 1):
            bin_low = bin_start + (i * bin_size)
            bin_high = bin_low + bin_size
            bin_key = f"{bin_low:.1f}% to {bin_high:.1f}%"
            bins[bin_key] = 0

        # Count trades in bins
        for trade_pnl in trade_values:
            bin_index = int((trade_pnl - bin_start) / bin_size)
            bin_low = bin_start + (bin_index * bin_size)
            bin_high = bin_low + bin_size
            bin_key = f"{bin_low:.1f}% to {bin_high:.1f}%"
            if bin_key in bins:
                bins[bin_key] += 1

        return list(bins.items())


    def get_performance_metrics_dict(self) -> Dict:
        """
        Get all performance metrics as a dictionary for easy serialization.

        This format matches what optimizer_routes.py expects in the performance_metrics table.
        """
        return {
            'total_pnl': self.total_pnl,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades_count,
            'losing_trades': self.losing_trades_count,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'market_return': self.market_return
        }


    def to_dict(self) -> Dict:
        """
        Serialize all metrics to a dictionary (excluding portfolio/streamer references).

        Useful for JSON serialization and storage.
        """
        return {
            'index': self.index,
            'fitness_values': self.fitness_values.tolist() if isinstance(self.fitness_values, np.ndarray) else self.fitness_values,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades_count,
            'losing_trades': self.losing_trades_count,
            'total_pnl': self.total_pnl,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'market_return': self.market_return,
            'trade_history': self.trade_history,
            'pnl_history': self.pnl_history,
            'winning_trades_distribution': self.winning_trades_distribution,
            'losing_trades_distribution': self.losing_trades_distribution
        }
