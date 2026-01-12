"""
Chart Data Generation
Functions for generating chart data for optimizer visualization
"""

import json
import math
from typing import List, Dict
from pathlib import Path

from optimization.mlf_optimizer.mlf_individual_stats import MlfIndividualStats
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
from portfolios.portfolio_tool import TradeReason
from .constants import get_table_columns_from_data
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("OptimizerVisualization")


def generate_optimizer_chart_data(best_individual, elites, io, data_config_path, best_individuals_log, objectives):
    """Generate chart data specifically for optimizer visualization"""
    logger.info("🎯 Generating optimizer chart data...")

    try:
        # Get best individual stats from elites[0] for cached trade data
        best_individual_stats = elites[0] if elites and isinstance(elites[0], MlfIndividualStats) else None

        # Get basic chart data from individual (OPTIMIZED: uses cached data from best_individual_stats)
        logger.info(f"🎯 Generating chart data for best individual in generation...")
        chart_data = generate_chart_data_for_individual_with_new_indicators(
            best_individual, io, data_config_path, best_individual_stats=best_individual_stats
        )
        logger.info(f"📊 Chart data generated: {list(chart_data.keys()) if chart_data else 'EMPTY'}")

        # 1. Objective Evolution Data - separate line for each objective
        objective_evolution = {}

        if best_individuals_log and objectives:
            # Initialize data structure for each objective
            for obj_name in objectives:
                objective_evolution[obj_name] = []

            for entry in best_individuals_log:
                generation = entry['generation']
                metrics = entry['metrics']

                # Add data point for each objective
                for obj_name in objectives:
                    if obj_name in metrics:
                        objective_evolution[obj_name].append([generation, metrics[obj_name]])

        logger.info(f"📈 Objective evolution data: {list(objective_evolution.keys())}")

        # 2. Trade Distribution Data - separate winning and losing trades like old app
        winning_trades_distribution = []
        losing_trades_distribution = []

        # Check if best_individual (elites[0]) has pre-calculated distributions
        best_individual_stats = elites[0] if elites and isinstance(elites[0], MlfIndividualStats) else None

        logger.info(f"📊 Processing trade distribution data... Using MlfIndividualStats: {best_individual_stats is not None}")
        if best_individual_stats:
            # Use pre-calculated distributions from MlfIndividualStats
            winning_trades_distribution = best_individual_stats.winning_trades_distribution
            losing_trades_distribution = best_individual_stats.losing_trades_distribution
            logger.info(f"✅ Using pre-calculated distributions: {len(winning_trades_distribution)} winning bins, {len(losing_trades_distribution)} losing bins")
        elif chart_data.get('pnl_history'):
            # Get P&L data from completed trades
            winning_trades = []
            losing_trades = []

            for pnl_entry in chart_data['pnl_history']:
                trade_pnl = pnl_entry['trade_pnl']
                if trade_pnl > 0:
                    winning_trades.append(trade_pnl)
                elif trade_pnl < 0:
                    losing_trades.append(trade_pnl)

            # Create winning trades histogram bins
            if winning_trades:
                min_val = min(winning_trades)
                max_val = max(winning_trades)
                range_val = max_val - min_val

                # Dynamic bin size based on range (like old app)
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

                # Create bins and count trades
                winning_bins = {}
                for i in range(int((bin_end - bin_start) / bin_size) + 1):
                    bin_low = bin_start + (i * bin_size)
                    bin_high = bin_low + bin_size
                    bin_key = f"{bin_low:.1f}% to {bin_high:.1f}%"
                    winning_bins[bin_key] = 0

                # Count trades in bins
                for trade_pnl in winning_trades:
                    bin_index = int((trade_pnl - bin_start) / bin_size)
                    bin_low = bin_start + (bin_index * bin_size)
                    bin_high = bin_low + bin_size
                    bin_key = f"{bin_low:.1f}% to {bin_high:.1f}%"
                    if bin_key in winning_bins:
                        winning_bins[bin_key] += 1

                winning_trades_distribution = list(winning_bins.items())

            # Create losing trades histogram bins (similar logic)
            if losing_trades:
                min_val = min(losing_trades)
                max_val = max(losing_trades)
                range_val = max_val - min_val

                # Dynamic bin size
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

                # Create bins and count trades
                losing_bins = {}
                for i in range(int((bin_end - bin_start) / bin_size) + 1):
                    bin_low = bin_start + (i * bin_size)
                    bin_high = bin_low + bin_size
                    bin_key = f"{bin_low:.1f}% to {bin_high:.1f}%"
                    losing_bins[bin_key] = 0

                # Count trades in bins
                for trade_pnl in losing_trades:
                    bin_index = int((trade_pnl - bin_start) / bin_size)
                    bin_low = bin_start + (bin_index * bin_size)
                    bin_high = bin_low + bin_size
                    bin_key = f"{bin_low:.1f}% to {bin_high:.1f}%"
                    if bin_key in losing_bins:
                        losing_bins[bin_key] += 1

                losing_trades_distribution = list(losing_bins.items())

        # 3. Elite Population Data (for parallel coordinates like old app)
        elite_population_data = []
        logger.info(f"📊 Processing elite population data... Elites: {len(elites) if elites else 0}")
        if elites and objectives:
            for i, elite in enumerate(elites[:20]):  # Top 20 elites
                try:
                    # Check different possible fitness attribute names
                    fitness_values = None
                    if hasattr(elite, 'fitness_values') and elite.fitness_values is not None:
                        fitness_values = elite.fitness_values
                    elif hasattr(elite, 'fitness') and elite.fitness is not None:
                        fitness_values = elite.fitness
                    elif hasattr(elite, 'individual') and hasattr(elite.individual, 'fitness_values'):
                        fitness_values = elite.individual.fitness_values

                    if fitness_values is not None and len(fitness_values) >= len(objectives):
                        # Each elite is an array of objective values [obj1, obj2, obj3, ...]
                        elite_values = [float(val) for val in fitness_values]
                        elite_population_data.append(elite_values)
                        logger.info(f"✅ Elite {i+1}: {elite_values}")
                    else:
                        logger.warning(f"⚠️ Elite {i+1} missing fitness values: {type(elite)}")
                except Exception as e:
                    logger.error(f"❌ Error processing elite {i+1}: {e}")
                    continue

        # 4. Individual P&L Ranking Data (sorted by Total P&L)
        individual_pnl_ranking = []
        logger.info(f"📊 Processing individual P&L ranking... Elites: {len(elites) if elites else 0}")
        if elites and objectives:
            # Find which objective index corresponds to Total P&L
            pnl_objective_index = None
            for idx, obj_name in enumerate(objectives):
                # Check for variations of P&L objective names
                obj_lower = obj_name.lower()
                if 'total_pnl' in obj_lower or 'total pnl' in obj_lower or 'pnl' in obj_lower:
                    pnl_objective_index = idx
                    logger.info(f"📈 Found P&L objective at index {idx}: '{obj_name}'")
                    break

            if pnl_objective_index is None:
                logger.warning(f"⚠️ Could not find P&L objective in objectives: {objectives}")
                logger.warning(f"⚠️ Individual P&L ranking chart will be empty")
            else:
                # Extract P&L from each elite (all MlfIndividualStats)
                pnl_list = [elite.total_pnl for elite in elites]

                # Sort by P&L descending (highest to lowest)
                pnl_list_sorted = sorted(pnl_list, reverse=True)

                # Convert to chart format: [[0, pnl1], [1, pnl2], [2, pnl3], ...]
                # X-axis is index, Y-axis is sorted P&L value
                individual_pnl_ranking = [[i, pnl] for i, pnl in enumerate(pnl_list_sorted)]

                logger.info(f"📈 Generated {len(individual_pnl_ranking)} individual P&L ranking points")

        # 5. Performance Metrics Table Data (like old app table format)
        performance_metrics = []
        logger.info(f"📊 Processing performance metrics... Using MlfIndividualStats: {best_individual_stats is not None}")
        if best_individuals_log:
            current_generation = best_individuals_log[-1]['generation'] if best_individuals_log else 1

            # Use pre-calculated metrics from MlfIndividualStats if available
            if best_individual_stats:
                # Direct access to all pre-calculated metrics
                perf_data = {
                    'generation': current_generation,
                    'total_pnl': best_individual_stats.total_pnl,
                    'total_trades': best_individual_stats.total_trades,
                    'winning_trades': best_individual_stats.winning_trades_count,
                    'losing_trades': best_individual_stats.losing_trades_count,
                    'avg_win': best_individual_stats.avg_win,
                    'avg_loss': best_individual_stats.avg_loss,
                    'market_return': best_individual_stats.market_return
                }
                performance_metrics = [perf_data]
                logger.info(f"✅ Performance metrics from MlfIndividualStats: {perf_data}")
            elif chart_data.get('pnl_history'):
                try:
                    pnl_data = chart_data['pnl_history']
                    trade_data = chart_data.get('trade_history', [])

                    # Calculate performance metrics from trade data
                    total_trades = len([t for t in trade_data if t['type'] == 'sell'])  # Only count exit trades

                    winning_trades = [p for p in pnl_data if p['trade_pnl'] > 0]
                    losing_trades = [p for p in pnl_data if p['trade_pnl'] < 0]

                    total_pnl = pnl_data[-1]['cumulative_pnl'] if pnl_data else 0.0
                    avg_win = sum(p['trade_pnl'] for p in winning_trades) / len(winning_trades) if winning_trades else 0.0
                    avg_loss = sum(p['trade_pnl'] for p in losing_trades) / len(losing_trades) if losing_trades else 0.0

                    # Calculate market return (first close to last close)
                    market_return = -6969.0  # Default error value
                    candlestick_data = chart_data.get('candlestick_data', [])
                    if candlestick_data and len(candlestick_data) >= 2:
                        first_close = candlestick_data[0][4]  # [timestamp, open, high, low, close]
                        last_close = candlestick_data[-1][4]
                        market_return = ((last_close - first_close) / first_close) * 100.0

                    # THIS IS WHERE YOU ADD NEW FUNCTIONS TO BE DISPLAYED IN THE PERFORMANCE METRIC TABLE
                    perf_data = {
                        'generation': current_generation,
                        'total_pnl': total_pnl,
                        'total_trades': total_trades,
                        'winning_trades': len(winning_trades),
                        'losing_trades': len(losing_trades),
                        'avg_win': avg_win,
                        'avg_loss': avg_loss,
                        'market_return': market_return
                    }
                    performance_metrics = [perf_data]
                    logger.info(f"✅ Performance metrics calculated: {perf_data}")
                except Exception as e:
                    logger.error(f"❌ Error calculating performance metrics: {e}")
            else:
                # Fallback: Use basic metrics from objectives if no trade data
                try:
                    final_metrics = best_individuals_log[-1]['metrics']
                    perf_data = {
                        'generation': current_generation,
                        'total_pnl': list(final_metrics.values())[0] if final_metrics else 0.0,
                        'total_trades': 0,
                        'winning_trades': 0,
                        'losing_trades': 0,
                        'avg_win': 0.0,
                        'avg_loss': 0.0
                    }
                    performance_metrics = [perf_data]
                    logger.info(f"⚠️ Using fallback performance metrics: {perf_data}")
                except Exception as e:
                    logger.error(f"❌ Error creating fallback performance metrics: {e}")

        # Auto-detect table columns from performance metrics
        table_columns = get_table_columns_from_data(performance_metrics)

        # Combine all chart data (matching old app format)
        optimizer_charts = {
            'objective_evolution': objective_evolution,
            'winning_trades_distribution': winning_trades_distribution,
            'losing_trades_distribution': losing_trades_distribution,
            'elite_population_data': elite_population_data,
            'objective_names': objectives,
            'performance_metrics': performance_metrics,
            'table_columns': table_columns,  # Dynamic table column definitions
            'individual_pnl_ranking': individual_pnl_ranking,  # Individual P&L sorted by rank
            'best_strategy': {
                'candlestick_data': chart_data.get('candlestick_data', []),
                'triggers': chart_data.get('triggers', [])
            }
        }

        # Log success with proper objective evolution structure
        total_points = sum(len(values) for values in objective_evolution.values()) if objective_evolution else 0
        logger.info(f"📊 Generated optimizer charts with {total_points} objective points across {len(objective_evolution)} objectives")
        return optimizer_charts

    except Exception as e:
        logger.error(f"❌ Error generating optimizer chart data: {e}")
        import traceback
        traceback.print_exc()
        return {}


def load_raw_candle_data(data_config_path: str, io):
    """Load raw candlestick data from MongoDB using the same data as trade execution"""
    logger.info("📊 Loading raw candle data for visualization")

    try:
        # Load data config
        with open(data_config_path) as f:
            data_config = json.load(f)

        ticker = data_config['ticker']
        start_date = data_config['start_date']
        end_date = data_config['end_date']

        logger.info(f"📈 Chart data generation for ticker: {ticker}")
        logger.info(f"   Date Range: {start_date} to {end_date}")
        logger.info(f"   Data config path: {data_config_path}")

        # Use the SAME data source as trade execution to ensure consistency
        backtest_streamer = io.fitness_calculator.selected_streamer

        # Debug: Check what ticker is actually loaded in the streamer
        actual_ticker = getattr(backtest_streamer, 'ticker', 'UNKNOWN')
        logger.info(f"🔍 Backtest streamer ticker: {actual_ticker}")
        if actual_ticker != ticker:
            logger.warning(f"⚠️  TICKER MISMATCH! Config: {ticker}, Streamer: {actual_ticker}")

        tick_history = backtest_streamer.tick_history

        # Format candlestick data for Highcharts
        candlestick_data = []
        for tick in tick_history:
            timestamp = int(tick.timestamp.timestamp() * 1000)
            candlestick_data.append([
                timestamp,
                tick.open,
                tick.high,
                tick.low,
                tick.close
            ])

        logger.info(f"📈 Loaded {len(candlestick_data)} candles")
        return candlestick_data, data_config

    except Exception as e:
        logger.error(f"❌ Error loading candle data: {e}")
        raise


def extract_trade_history_and_pnl_from_portfolio(portfolio, backtest_streamer):
    """Extract trade history, triggers, P&L history, bar scores, and trade details from portfolio"""
    logger.info("💼 Extracting trade history and P&L from portfolio")

    trade_history = []
    triggers = []
    pnl_history = []
    bar_scores_history = []
    trade_details = {}  # Detailed trade info for UI popup

    # Get trade details from the executor if available
    if hasattr(backtest_streamer, 'trade_executor') and backtest_streamer.trade_executor:
        trade_details = backtest_streamer.trade_executor.trade_details_history or {}

    try:
        # Generate bar scores history from the stored calculation
        try:
            if (hasattr(backtest_streamer, 'bar_score_history_dict') and
                    backtest_streamer.bar_score_history_dict and
                    backtest_streamer.tick_history):

                bar_score_history_dict = backtest_streamer.bar_score_history_dict
                tick_history = backtest_streamer.tick_history

                logger.info(f"📊 Found bar scores history with {len(bar_score_history_dict)} bars")

                # Create timeline of bar scores
                timeline_length = len(tick_history)
                for i in range(timeline_length):
                    if i < len(tick_history):
                        tick = tick_history[i]
                        timestamp = int(tick.timestamp.timestamp() * 1000)

                        scores = {}
                        for bar_name, bar_values in bar_score_history_dict.items():
                            if i < len(bar_values):
                                scores[bar_name] = bar_values[i]
                            else:
                                scores[bar_name] = 0.0

                        bar_scores_history.append({
                            'timestamp': timestamp,
                            'scores': scores
                        })

                logger.info(f"📈 Generated {len(bar_scores_history)} bar score history entries")
            else:
                logger.warning("⚠️  No bar score history data available from backtest streamer")

        except Exception as bar_error:
            logger.warning(f"⚠️  Could not generate bar scores history: {bar_error}")
            import traceback
            traceback.print_exc()

        if portfolio and hasattr(portfolio, 'trade_history') and portfolio.trade_history:
            logger.info(f"📊 Found {len(portfolio.trade_history)} trades in portfolio")

            # Calculate cumulative P&L over time
            cumulative_pnl = 0.0
            trade_pairs = []  # Store entry/exit pairs for P&L calculation

            # Process trades to build P&L history
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
                trade_history.append(trade_entry)

                # Add to triggers for chart display
                triggers.append({
                    'timestamp': timestamp_ms,
                    'type': trade_type,
                    'price': trade.price,
                    'reason': trade_entry['reason']
                })

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

                            pnl_history.append({
                                'timestamp': timestamp_ms,
                                'cumulative_pnl': cumulative_pnl,
                                'trade_pnl': trade_pnl
                            })
                            break

            logger.info(
                f"📈 Processed {len(trade_history)} trades, {len(triggers)} signals, {len(pnl_history)} P&L points")
        else:
            logger.warning("⚠️  No trade history found in portfolio")

    except Exception as e:
        logger.error(f"❌ Error extracting trade history: {e}")
        import traceback
        traceback.print_exc()

    return trade_history, triggers, pnl_history, bar_scores_history, trade_details


def generate_chart_data_for_individual_with_new_indicators(best_individual, io, data_config_path, best_individual_stats=None):
    """
    Generate chart data for the given the best individual using NEW indicator system.

    PERFORMANCE OPTIMIZATION: If best_individual_stats (MlfIndividualStats) is provided,
    uses pre-calculated trade_history and pnl_history from fitness evaluation instead of
    re-running the entire backtest. This dramatically reduces inter-epoch processing time.

    Args:
        best_individual: The MlfIndividual to generate chart data for
        io: OptimizationIO instance with fitness calculator
        data_config_path: Path to data configuration file
        best_individual_stats: Optional MlfIndividualStats with pre-calculated metrics
    """
    # Load candle data
    candlestick_data, data_config = load_raw_candle_data(data_config_path, io)

    backtest_streamer = io.fitness_calculator.selected_streamer
    tick_history = backtest_streamer.tick_history

    # PERFORMANCE OPTIMIZATION: Use cached results from MlfIndividualStats if available
    # This avoids re-running the full backtest for visualization
    if best_individual_stats is not None and hasattr(best_individual_stats, 'trade_history') and best_individual_stats.trade_history:
        logger.info("📊 Using cached trade data from MlfIndividualStats (skipping backtest re-run)")

        # Use pre-calculated data from fitness evaluation
        trade_history = best_individual_stats.trade_history
        pnl_history = best_individual_stats.pnl_history

        # Convert trade history to triggers format
        triggers = [
            {
                'timestamp': t['timestamp'],
                'type': t['type'],
                'price': t['price'],
                'reason': t['reason']
            }
            for t in trade_history
        ]

        # Get bar scores from streamer if available (cached from evaluation)
        bar_scores_history = []
        bar_score_history_dict = getattr(backtest_streamer, 'bar_score_history_dict', {})
        if bar_score_history_dict and tick_history:
            for i in range(len(tick_history)):
                tick = tick_history[i]
                timestamp = int(tick.timestamp.timestamp() * 1000)
                scores = {}
                for bar_name, bar_values in bar_score_history_dict.items():
                    if i < len(bar_values):
                        scores[bar_name] = bar_values[i]
                    else:
                        scores[bar_name] = 0.0
                bar_scores_history.append({'timestamp': timestamp, 'scores': scores})

        # Get component history from streamer if cached
        component_history = getattr(backtest_streamer, 'component_history', {})
        trade_details = getattr(backtest_streamer.trade_executor, 'trade_details_history', {}) if backtest_streamer.trade_executor else {}
        portfolio = None  # Not needed when using cached data

    else:
        # FALLBACK: Run full backtest if no cached data available
        logger.info("📊 No cached data available - running full backtest for visualization")

        backtest_streamer.replace_monitor_config(best_individual.monitor_configuration)

        # Process indicators using old system for compatibility
        from optimization.calculators.indicator_processor_historical_new import IndicatorProcessorHistoricalNew

        indicator_processor = IndicatorProcessorHistoricalNew(best_individual.monitor_configuration)
        indicator_history, raw_indicator_history, bar_score_history_dict, component_history, _ = (
            indicator_processor.calculate_indicators(backtest_streamer.aggregators)
        )

        # Store the bar score history for later access
        backtest_streamer.bar_score_history_dict = bar_score_history_dict

        # Run the backtest to get trades
        portfolio = backtest_streamer.run()

        # Extract trade history and P&L from the fresh portfolio
        trade_history, triggers, pnl_history, bar_scores_history, trade_details = extract_trade_history_and_pnl_from_portfolio(
            portfolio, backtest_streamer
        )

    # Process indicators using old system for now (new system disabled)
    new_indicator_results = {}

    # Get threshold config
    threshold_config = {}
    if hasattr(best_individual, 'monitor_configuration'):
        monitor_config = best_individual.monitor_configuration
        threshold_config = {
            'enter_long': getattr(monitor_config, 'enter_long', []),
            'exit_long': getattr(monitor_config, 'exit_long', [])
        }

    # Format component data for charts (MACD, SMA components)
    component_data_formatted = {}
    if component_history:
        for comp_name, comp_values in component_history.items():
            # Convert to Highcharts format with timestamps
            comp_series = []
            for i, value in enumerate(comp_values):
                if i < len(tick_history) and value is not None:
                    timestamp = int(tick_history[i].timestamp.timestamp() * 1000)
                    comp_series.append([timestamp, float(value)])

            component_data_formatted[comp_name] = {
                'data': comp_series,
                'name': comp_name
            }

    # Add NEW indicator results to chart data (currently disabled)
    for indicator_name, values in new_indicator_results.items():
        comp_series = []
        for i, value in enumerate(values):
            if i < len(tick_history) and value is not None:
                timestamp = int(tick_history[i].timestamp.timestamp() * 1000)
                comp_series.append([timestamp, float(value)])

        component_data_formatted[f"new_{indicator_name}"] = {
            'data': comp_series,
            'name': f"New {indicator_name}"
        }

    return {
        'ticker': data_config['ticker'],
        'candlestick_data': candlestick_data,
        'triggers': triggers,
        'trade_history': trade_history,
        'trade_details': trade_details,  # Detailed trade info for popup (timestamp -> details dict)
        'pnl_history': pnl_history,
        'bar_scores_history': bar_scores_history,
        'threshold_config': threshold_config,
        'component_data': component_data_formatted,  # NEW indicators included
        'total_candles': len(candlestick_data),
        'total_trades': len(trade_history),
        'date_range': {
            'start': data_config['start_date'],
            'end': data_config['end_date']
        },
        'new_indicators_used': list(new_indicator_results.keys())
    }
