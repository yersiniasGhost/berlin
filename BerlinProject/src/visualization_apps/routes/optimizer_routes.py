"""
Optimizer Visualization Routes
Handles genetic algorithm optimization with real-time WebSocket updates
"""

from flask import Blueprint, render_template, request, jsonify
import os
import json
import logging
import time
import math
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from .optimization_state import OptimizationState

from optimization.genetic_optimizer.apps.utils.mlf_optimizer_config import MlfOptimizerConfig
from portfolios.portfolio_tool import TradeReason
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
from optimization.mlf_optimizer.mlf_individual_stats import MlfIndividualStats

# Remove new indicator system imports that are causing backend conflicts
# from indicator_triggers.indicator_base import IndicatorRegistry
# from indicator_triggers.refactored_indicators import *  # Import to register indicators

logger = logging.getLogger('OptimizerVisualization')

# Create Blueprint
optimizer_bp = Blueprint('optimizer', __name__, url_prefix='/optimizer')


def sanitize_nan_values(obj):
    """
    Recursively sanitize NaN values in a data structure for JSON compatibility.
    Converts NaN to None (null in JSON), and handles nested lists/dicts.
    """
    if isinstance(obj, dict):
        return {key: sanitize_nan_values(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_nan_values(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj):
            return None
        elif math.isinf(obj):
            return None
        else:
            return obj
    else:
        return obj


# Column metadata for custom display names and formatting
PERFORMANCE_TABLE_COLUMNS = {
    'generation': {'title': 'Gen', 'type': 'number'},
    'total_trades': {'title': 'Total Trades', 'type': 'number'},
    'winning_trades': {'title': 'Winning', 'type': 'number'},
    'losing_trades': {'title': 'Losing', 'type': 'number'},
    'total_pnl': {'title': 'Total P&L (%)', 'type': 'percentage'},
    'avg_win': {'title': 'Avg Win (%)', 'type': 'percentage'},
    'avg_loss': {'title': 'Avg Loss (%)', 'type': 'percentage'},
    'market_return': {'title': 'Market Return (%)', 'type': 'percentage'}
}


def get_table_columns_from_data(performance_metrics):
    """Auto-detect table columns from performance data"""
    if not performance_metrics:
        return []

    # Get all keys from the first data row
    sample_data = performance_metrics[0]
    columns = []

    for key in sample_data.keys():
        # Use custom metadata if available, otherwise create default
        column_info = PERFORMANCE_TABLE_COLUMNS.get(key, {
            'title': key.replace('_', ' ').title(),
            'type': 'number'  # default type
        })

        columns.append({
            'key': key,
            'title': column_info['title'],
            'type': column_info['type']
        })

    return columns


def balance_fronts(front: List[IndividualStats]) -> List[IndividualStats]:
    ideal_point = np.min([ind.fitness_values for ind in front], axis=0)
    balanced_front = sorted(front, key=lambda ind: np.linalg.norm(ind.fitness_values - ideal_point))
    return balanced_front


def select_winning_population(number_of_elites: int, fronts: Dict[int, List]) -> List[IndividualStats]:
    elitists: List[IndividualStats] = []
    for front in fronts.values():
        sorted_front = balance_fronts(front)
        for stat in sorted_front:
            if len(elitists) < number_of_elites:
                elitists.append(stat)
    return elitists


def generate_optimizer_chart_data(best_individual, elites, io, data_config_path, best_individuals_log, objectives):
    """Generate chart data specifically for optimizer visualization"""
    logger.info("🎯 Generating optimizer chart data...")
    
    try:
        # Get basic chart data from individual
        logger.info(f"🎯 Generating chart data for best individual in generation...")
        chart_data = generate_chart_data_for_individual_with_new_indicators(best_individual, io, data_config_path)
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
    """Load raw candlestick data from Yahoo Finance using the same data as trade execution"""
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
    """Extract trade history, triggers, P&L history, and bar scores from portfolio"""
    logger.info("💼 Extracting trade history and P&L from portfolio")

    trade_history = []
    triggers = []
    pnl_history = []
    bar_scores_history = []

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

    return trade_history, triggers, pnl_history, bar_scores_history


def generate_chart_data_for_individual_with_new_indicators(best_individual, io, data_config_path):
    """Generate chart data for the given the best individual using NEW indicator system"""
    # Load candle data
    candlestick_data, data_config = load_raw_candle_data(data_config_path, io)

    # IMPORTANT: Run backtest for this specific individual to get trades and bar scores
    backtest_streamer = io.fitness_calculator.selected_streamer
    backtest_streamer.replace_monitor_config(best_individual.monitor_configuration)

    # Process indicators using NEW SYSTEM for this individual
    monitor_config = best_individual.monitor_configuration
    tick_history = backtest_streamer.tick_history
    
    # Process indicators using old system for now (new system disabled)
    new_indicator_results = {}
    # TODO: Re-enable new indicator system when fully integrated
    # if hasattr(monitor_config, 'indicators') and monitor_config.indicators:
    #     registry = IndicatorRegistry()
    #     ... (new system code commented out)

    # Still use old system for compatibility
    from optimization.calculators.indicator_processor_historical_new import IndicatorProcessorHistoricalNew

    indicator_processor = IndicatorProcessorHistoricalNew(best_individual.monitor_configuration)
    indicator_history, raw_indicator_history, bar_score_history_dict, component_history = (
        indicator_processor.calculate_indicators(backtest_streamer.aggregators)
    )

    # Store the bar score history for later access
    backtest_streamer.bar_score_history_dict = bar_score_history_dict

    # Run the backtest to get trades
    portfolio = backtest_streamer.run()

    # Extract trade history and P&L from the fresh portfolio
    trade_history, triggers, pnl_history, bar_scores_history = extract_trade_history_and_pnl_from_portfolio(portfolio,
                                                                                                        backtest_streamer)

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


def run_genetic_algorithm_threaded_with_new_indicators(ga_config_path: str, data_config_path: str,
                                                       socketio, opt_state):
    """Run the genetic algorithm optimization with NEW indicator system"""

    try:
        logger.info("🚀 Starting threaded optimization with NEW indicator system")

        # Load configuration
        with open(ga_config_path) as f:
            config_data = json.load(f)

        # Load data configuration to verify ticker
        with open(data_config_path) as f:
            data_config = json.load(f)
        
        current_ticker = data_config.get('ticker', 'UNKNOWN')
        logger.info(f"🎯 Loading optimization for ticker: {current_ticker}")
        logger.info(f"   Data config path: {data_config_path}")
        logger.info(f"   Date range: {data_config.get('start_date')} to {data_config.get('end_date')}")

        test_name = config_data.get('test_name', config_data.get('monitor', {}).get('name', 'NoNAME'))
        opt_state.set('test_name', test_name)
        opt_state.set('ga_config_path', ga_config_path)

        # Process indicators using old system for now (new system disabled)
        processed_indicators = []
        # TODO: Re-enable new indicator system when fully integrated
        # if 'indicators' in config_data:
        #     registry = IndicatorRegistry()
        #     ... (new system code commented out)
        logger.info("Using NEW indicator system for compatibility")

        # Create optimizer config with processed indicators
        io = MlfOptimizerConfig.from_json(config_data, data_config_path)
        genetic_algorithm = io.create_project()

        # Store instances for state management using thread-safe methods
        opt_state.update({
            'ga_instance': genetic_algorithm,
            'io_instance': io,
            'total_generations': genetic_algorithm.number_of_generations,
            'current_generation': 0,
            'best_individuals_log': [],
            'processed_indicators': processed_indicators
        })

        logger.info(f"   Test: {test_name}")
        logger.info(f"   Generations: {genetic_algorithm.number_of_generations}")
        logger.info(f"   Population Size: {genetic_algorithm.population_size}")
        logger.info(f"   Elitist Size: {genetic_algorithm.elitist_size}")
        logger.info(f"   New Indicators: {len(processed_indicators)}")

        # Store timestamp for later use
        optimization_timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        opt_state.set('timestamp', optimization_timestamp)

        # Emit initial status
        socketio.emit('optimization_started', {
            'test_name': test_name,
            'total_generations': genetic_algorithm.number_of_generations,
            'population_size': genetic_algorithm.population_size,
            'timestamp': optimization_timestamp,
            'new_indicators_count': len(processed_indicators)
        })

        # Run optimization with generation-by-generation updates
        for observer, statsobserver in genetic_algorithm.run_ga_iterations(1):
            if not observer.success:
                print("NOT SUCCESSFUL... trying again with next epoch")
                continue

            # Fix generation numbering first - stats returns 0-based, we want 1-based display
            current_gen = observer.iteration + 1  # Convert from 0-based to 1-based

            # Check if stopped using thread-safe methods
            if not opt_state.is_running():
                logger.info(f"🛑 Optimization stopped by user at generation {current_gen}")
                socketio.emit('optimization_stopped', {
                    'generation': current_gen,
                    'total_generations': genetic_algorithm.number_of_generations
                })
                break

            # Wait while paused using thread-safe methods - pause after finishing current generation
            if opt_state.is_paused() and opt_state.is_running():
                logger.info(f"⏸️ Optimization paused after completing generation {current_gen}")
                while opt_state.is_paused() and opt_state.is_running():
                    time.sleep(0.1)

                if opt_state.is_running():  # If still running after unpause
                    logger.info(f"▶️ Optimization resumed at generation {current_gen}")
            metrics = statsobserver.best_metric_iteration

            elites = select_winning_population(genetic_algorithm.elitist_size, observer.fronts)
            best_individual = elites[0].individual

            opt_state.update({
                'current_generation': current_gen,
                'last_best_individual': best_individual,
                'elites': elites
            })

            # Log the best individual for this generation
            objectives = [o.name for o in io.fitness_calculator.objectives]
            fitness_log = {
                'generation': current_gen,
                'metrics': dict(zip(objectives, metrics))
            }
            current_log = opt_state.get('best_individuals_log', [])
            current_log.append(fitness_log)
            opt_state.set('best_individuals_log', current_log)

            # Log progress
            metric_out = [f"{obj}={metric:.4f}" for obj, metric in zip(objectives, metrics)]
            out_str = f"{test_name}, {current_gen}/{genetic_algorithm.number_of_generations}, {metric_out}"
            logger.info(out_str)

            # Get chart data for optimizer visualization
            try:
                # Get objective names dynamically
                objectives = [o.name for o in io.fitness_calculator.objectives]
                
                # Generate optimizer-specific chart data
                optimizer_charts = generate_optimizer_chart_data(
                    best_individual, elites, io, data_config_path, 
                    opt_state.get('best_individuals_log', []), objectives
                )

                # Convert numpy arrays to regular Python lists for JSON serialization
                elite_objectives = [e.fitness_values.tolist() for e in elites]

                socketio.emit('generation_complete', {
                    'generation': current_gen,
                    'total_generations': genetic_algorithm.number_of_generations,
                    'fitness_metrics': dict(zip(objectives, metrics)),
                    'chart_data': optimizer_charts,
                    'best_individuals_log': opt_state.get('best_individuals_log', []),
                    'elite_objective_values': elite_objectives,
                    'objective_names': objectives,
                    'progress': {
                        'current_generation': current_gen,
                        'total_generations': genetic_algorithm.number_of_generations,
                        'completed': False
                    },
                    'optimizer_charts': optimizer_charts  # Specifically for optimizer frontend
                })

            except Exception as e:
                logger.error(f"Error generating chart data: {e}")
                socketio.emit('optimization_error', {'error': str(e)})
                break

        # Optimization completed
        if opt_state.is_running():
            logger.info("⏱️  Optimization completed successfully with NEW indicator system")
            # Auto-saving disabled - user will manually save best elites via UI button
            logger.info("✅ Optimization completed - elites available for manual saving via UI")
            # Emit completion event without automatic saving
            socketio.emit('optimization_complete', {
                'total_generations': opt_state.get('current_generation'),
                'best_individuals_log': opt_state.get('best_individuals_log', []),
                'manual_save_available': True
            })

    except Exception as e:
        logger.error(f"❌ Error in threaded optimization: {e}")
        import traceback
        traceback.print_exc()
        socketio.emit('optimization_error', {'error': str(e)})

    finally:
        # Clean up temporary files if they exist
        try:
            ga_config_path_temp = opt_state.get('ga_config_path_temp')
            data_config_path_temp = opt_state.get('data_config_path_temp')

            if ga_config_path_temp and Path(ga_config_path_temp).exists():
                Path(ga_config_path_temp).unlink()

            if data_config_path_temp and Path(data_config_path_temp).exists():
                Path(data_config_path_temp).unlink()

        except Exception:
            pass

        # Reset optimization state
        opt_state.update({
            'running': False,
            'paused': False,
            'thread': None,
            'ga_config_path_temp': None,
            'data_config_path_temp': None
        })


def save_optimization_results_with_new_indicators(best_individuals_log, best_individual, elites, ga_config_path, test_name, timestamp=None, processed_indicators=None):
    """Save optimization results including NEW indicator information"""
    logger.info("💾 Saving optimization results with NEW indicator system...")

    if not timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    results_dir = Path('results') / f"{timestamp}_{test_name}"
    results_dir.mkdir(parents=True, exist_ok=True)

    results_info = {
        'results_dir': str(results_dir),
        'timestamp': timestamp,
        'files_created': []
    }

    try:
        # Save information about new indicators used
        if processed_indicators:
            indicators_info_file = results_dir / f"{timestamp}_{test_name}_new_indicators_used.json"
            
            indicators_info = {
                'count': len(processed_indicators),
                'indicators': []
            }
            
            for indicator in processed_indicators:
                indicators_info['indicators'].append({
                    'name': indicator.name,
                    'display_name': getattr(indicator, 'display_name', indicator.name),
                    'parameters': indicator.config.parameters,
                    'enabled': indicator.config.enabled
                })
            
            with open(indicators_info_file, 'w') as f:
                json.dump(indicators_info, f, indent=2)
            
            results_info['files_created'].append(str(indicators_info_file))
            logger.info(f"✅ Saved new indicators info: {indicators_info_file}")

        # Save other results following the same pattern as original
        # (elite monitors, objectives CSV, etc.)
        
        # Load GA config to get elites_to_save parameter
        elites_to_save = 5  # Default value
        try:
            with open(ga_config_path) as f:
                ga_config = json.load(f)
                elites_to_save = ga_config.get('ga_hyperparameters', {}).get('elites_to_save', 5)
        except Exception as e:
            logger.warning(f"Could not read elites_to_save from GA config: {e}")
        
        if elites and len(elites) >= 1 and elites_to_save >= 1:
            # Save elite monitors with NEW indicator information
            elites_to_process = elites[:elites_to_save]
            logger.info(f"💫 Saving top {len(elites_to_process)} elite monitors with NEW indicators...")
            
            for i, elite in enumerate(elites_to_process):
                if not hasattr(elite, 'individual') or not hasattr(elite.individual, 'monitor_configuration'):
                    logger.warning(f"Elite #{i+1} missing individual.monitor_configuration, skipping")
                    continue
                    
                elite_file = results_dir / f"{timestamp}_{test_name}_elite_{i+1}.json"
                elite_config = elite.individual.monitor_configuration
                
                # Extract and save elite configuration with NEW indicator format
                elite_trade_executor = {}
                if hasattr(elite_config, 'trade_executor'):
                    te = elite_config.trade_executor
                    elite_trade_executor = {
                        'default_position_size': getattr(te, 'default_position_size', 100.0),
                        'stop_loss_pct': getattr(te, 'stop_loss_pct', 0.01),
                        'take_profit_pct': getattr(te, 'take_profit_pct', 0.02),
                        'ignore_bear_signals': getattr(te, 'ignore_bear_signals', False),
                        'trailing_stop_loss': getattr(te, 'trailing_stop_loss', False),
                        'trailing_stop_distance_pct': getattr(te, 'trailing_stop_distance_pct', 0.01),
                        'trailing_stop_activation_pct': getattr(te, 'trailing_stop_activation_pct', 0.005)
                    }
                
                # Convert elite indicators to new format
                elite_indicators_list = []
                if hasattr(elite_config, 'indicators') and elite_config.indicators:
                    for indicator in elite_config.indicators:
                        indicator_dict = {
                            'name': getattr(indicator, 'name', 'unknown'),
                            'display_name': getattr(indicator, 'display_name', getattr(indicator, 'name', 'unknown')),
                            'type': getattr(indicator, 'type', 'unknown'),
                            'indicator_class': getattr(indicator, 'indicator_class', 'unknown'),
                            'agg_config': getattr(indicator, 'agg_config', '1m-normal'),
                            'calc_on_pip': getattr(indicator, 'calc_on_pip', False),
                            'parameters': dict(getattr(indicator, 'parameters', {})),
                            'enabled': getattr(indicator, 'enabled', True),
                            'new_system': True  # Mark as using new system
                        }
                        elite_indicators_list.append(indicator_dict)
                
                elite_dict = {
                    'monitor': {
                        'name': getattr(elite_config, 'name', f"Elite {i+1}"),
                        'description': getattr(elite_config, 'description', f"Elite monitor #{i+1} with NEW indicators"),
                        'trade_executor': elite_trade_executor,
                        'enter_long': getattr(elite_config, 'enter_long', []),
                        'exit_long': getattr(elite_config, 'exit_long', []),
                        'bars': getattr(elite_config, 'bars', {}),
                    },
                    'indicators': elite_indicators_list,
                    'system_version': 'new_indicator_system_v1.0',
                    'fitness_values': elite.fitness_values.tolist() if hasattr(elite, 'fitness_values') else []
                }
                
                try:
                    with open(elite_file, 'w') as f:
                        json.dump(elite_dict, f, indent=2)
                    
                    results_info['files_created'].append(str(elite_file))
                    logger.info(f"✅ Saved NEW elite #{i+1} config: {elite_file}")
                except Exception as save_error:
                    logger.error(f"❌ Failed to save elite #{i+1}: {save_error}")
                    continue

        logger.info(f"💾 Successfully saved optimization results with NEW indicator system")

    except Exception as e:
        logger.error(f"❌ Error saving results: {e}")
        raise

    return results_info

# ===== ROUTES =====


@optimizer_bp.route('/')
def optimizer_main():
    """Main optimizer visualization page"""
    return render_template('optimizer/main.html')


@optimizer_bp.route('/api/upload_file', methods=['POST'])
def upload_file():
    """Handle file uploads and save them temporarily"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})

        file = request.files['file']
        file_type = request.form.get('config_type', 'unknown')

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})

        if not file.filename.endswith('.json'):
            return jsonify({'success': False, 'error': 'Only JSON files are allowed'})

        # Create uploads directory
        uploads_dir = Path('uploads')
        uploads_dir.mkdir(exist_ok=True)

        # Save file with type prefix
        filename = f"{file_type}_{file.filename}"
        filepath = uploads_dir / filename

        file.save(filepath)

        return jsonify({
            'success': True,
            'filename': filename,
            'filepath': str(filepath.absolute()),
            'type': file_type
        })

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/load_examples')
def load_examples():
    """Load example configurations for form initialization"""
    try:
        examples = {}
        
        # Load example GA config
        example_ga_path = Path('inputs/dan_fuck_around1.json')
        if example_ga_path.exists():
            with open(example_ga_path) as f:
                examples['ga_config'] = json.load(f)
        else:
            # Provide default GA config structure with NEW indicators
            examples['ga_config'] = {
                "test_name": "New_Test",
                "monitor": {
                    "name": "New Strategy",
                    "description": "Description for new strategy",
                    "trade_executor": {
                        "default_position_size": 100.0,
                        "stop_loss_pct": 0.02,
                        "take_profit_pct": 0.04,
                        "ignore_bear_signals": False,
                        "trailing_stop_loss": True,
                        "trailing_stop_distance_pct": 0.01,
                        "trailing_stop_activation_pct": 0.005
                    },
                    "enter_long": [],
                    "exit_long": [],
                    "bars": {}
                },
                "indicators": [
                    {
                        "name": "sma_crossover",
                        "display_name": "SMA Crossover",
                        "parameters": {
                            "period": {"min": 10, "max": 50, "default": 20},
                            "crossover_value": {"min": 0.01, "max": 0.05, "default": 0.015},
                            "trend": {"choices": ["bullish", "bearish"], "default": "bullish"}
                        },
                        "enabled": True
                    }
                ],
                "objectives": [
                    {
                        "objective": "MaximizeProfit",
                        "weight": 1.0
                    }
                ],
                "ga_hyperparameters": {
                    "number_of_iterations": 100,
                    "population_size": 50,
                    "propagation_fraction": 0.4,
                    "elite_size": 12,
                    "chance_of_mutation": 0.05,
                    "chance_of_crossover": 0.03
                }
            }

        # Provide default data config
        examples['data_config'] = {
            "ticker": "NVDA",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }

        return jsonify({
            'success': True,
            'examples': examples
        })

    except Exception as e:
        logger.error(f"Error loading example configs: {e}")
        return jsonify({'success': False, 'error': str(e)})


# WebSocket events need to be registered with the main socketio instance
# This will be handled in the main app.py file


@optimizer_bp.route('/api/load_configs', methods=['POST'])
def load_configs():
    """Load and validate the uploaded configuration files"""
    try:
        data = request.get_json()
        logger.info(f"Received load_configs request with data: {data}")
        
        # The file upload component sends keys like 'ga_config' and 'data_config'
        ga_config_path = data.get('ga_config')
        data_config_path = data.get('data_config')

        if not ga_config_path or not data_config_path:
            available_keys = list(data.keys()) if data else []
            logger.error(f"Missing config files. Available keys: {available_keys}")
            return jsonify({'success': False, 'error': f'Both config files are required. Received keys: {available_keys}'})

        # Validate files exist
        if not Path(ga_config_path).exists():
            return jsonify({'success': False, 'error': f'GA config file not found: {ga_config_path}'})

        if not Path(data_config_path).exists():
            return jsonify({'success': False, 'error': f'Data config file not found: {data_config_path}'})

        # Load and validate GA config
        with open(ga_config_path) as f:
            ga_config = json.load(f)

        # Load and validate data config
        with open(data_config_path) as f:
            data_config = json.load(f)

        logger.info(f"Successfully loaded configs for optimizer visualization")
        return jsonify({
            'success': True,
            'ga_config': ga_config,  # Full config for editing
            'data_config': data_config  # Full config for editing
        })

    except Exception as e:
        logger.error(f"Error loading configs: {e}")
        return jsonify({'success': False, 'error': str(e)})

@optimizer_bp.route('/api/start_optimization', methods=['POST'])
def start_optimization():
    """HTTP endpoint to start optimization - creates temp files and triggers WebSocket"""
    try:
        # Check if optimization is already running
        if OptimizationState().is_running():
            return jsonify({
                'success': False, 
                'error': 'An optimization is already running. Please stop or pause the current optimization before starting a new one.'
            })
        
        data = request.get_json()
        logger.info(f"Received start_optimization request with data keys: {list(data.keys()) if data else 'None'}")
        
        # The frontend sends actual config objects, not file paths
        ga_config = data.get('ga_config')
        data_config = data.get('data_config')

        if not ga_config or not data_config:
            return jsonify({'success': False, 'error': 'Both config objects are required'})

        # Create temporary files for the configs since our optimization function expects file paths
        import tempfile
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='_ga_config.json', delete=False) as ga_file:
            json.dump(ga_config, ga_file, indent=2)
            ga_config_path = ga_file.name
            
        with tempfile.NamedTemporaryFile(mode='w', suffix='_data_config.json', delete=False) as data_file:
            json.dump(data_config, data_file, indent=2)
            data_config_path = data_file.name

        # Store paths and config data globally so WebSocket handler can access them
        OptimizationState().update({
            'ga_config_path_temp': ga_config_path,
            'data_config_path_temp': data_config_path,
            'ga_config_data': ga_config,
            'data_config_data': data_config
        })

        return jsonify({
            'success': True,
            'message': 'Configuration received. Use WebSocket to start optimization.',
            'ga_config_path': ga_config_path,
            'data_config_path': data_config_path
        })

    except Exception as e:
        logger.error(f"Error preparing optimization: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/stop_optimization', methods=['POST'])
def api_stop_optimization():
    """Stop the optimization via REST API"""
    try:
        from flask import current_app

        # Stop the optimization immediately
        OptimizationState().update({
            'running': False,
            'paused': False
        })

        # Try to gracefully stop the thread
        thread = OptimizationState().get('thread')
        if thread and thread.is_alive():
            thread.join(timeout=5)
            if thread.is_alive():
                logger.warning("Optimization thread did not terminate gracefully within timeout")

        logger.info("Optimization stopped via REST API")

        # Also emit WebSocket event for real-time UI updates
        try:
            socketio = current_app.extensions.get('socketio')
            if socketio:
                socketio.emit('optimization_stopped', {
                    'generation': OptimizationState().get('current_generation', 0),
                    'total_generations': OptimizationState().get('total_generations', 0)
                })
        except Exception as ws_error:
            logger.warning(f"Could not emit WebSocket event: {ws_error}")

        return jsonify({
            'success': True,
            'message': 'Optimization stopped',
            'generation': OptimizationState().get('current_generation', 0),
            'total_generations': OptimizationState().get('total_generations', 0)
        })
    except Exception as e:
        logger.error(f"Error stopping optimization: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@optimizer_bp.route('/api/save_config', methods=['POST'])
def save_config():
    """Save configuration changes back to files"""
    try:
        data = request.get_json()
        config_type = data.get('config_type')
        config_data = data.get('config_data')
        
        if not config_type or not config_data:
            return jsonify({'success': False, 'error': 'Missing config_type or config_data'})
        
        # Create saved_configs directory if it doesn't exist
        saved_configs_dir = Path('saved_configs')
        saved_configs_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{config_type}.json"
        filepath = saved_configs_dir / filename
        
        # Save the config
        with open(filepath, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        logger.info(f"Saved {config_type} configuration to {filepath}")
        
        return jsonify({
            'success': True,
            'message': f'Configuration saved successfully to {filename}',
            'filepath': str(filepath.absolute()),
            'filename': filename
        })
        
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/export_optimized_configs')
def export_optimized_configs():
    """Export complete optimization results package like the old system"""
    try:
        print("EXPORT", OptimizationState().get('elites'))
        elites = OptimizationState().get('elites', [])
        best_individuals_log = OptimizationState().get('best_individuals_log', [])
        ga_config_data = OptimizationState().get('ga_config_data', {})
        test_name = OptimizationState().get('test_name', 'optimization')
        
        if not elites:
            return jsonify({'success': False, 'error': 'No elite configurations available'})
        
        # Generate timestamp for folder name
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        
        # Get number of elites to save from GA hyperparameters (specifically "elites_to_save")
        elites_to_save = 5  # Default
        try:
            # First try from stored ga_config_data
            if ga_config_data and 'ga_hyperparameters' in ga_config_data:
                elites_to_save = ga_config_data.get('ga_hyperparameters', {}).get('elites_to_save', 5)
                logger.info(f"📊 Found elites_to_save in stored config: {elites_to_save}")
            else:
                # Try to read from the config paths used during optimization start
                ga_config_path = OptimizationState().get('ga_config_path')
                if ga_config_path and os.path.exists(ga_config_path):
                    with open(ga_config_path, 'r') as f:
                        ga_config = json.load(f)
                        elites_to_save = ga_config.get('ga_hyperparameters', {}).get('elites_to_save', 5)
                        logger.info(f"📊 Found elites_to_save in config file: {elites_to_save}")
                else:
                    logger.warning(f"📊 Could not find GA config, using default elites_to_save: {elites_to_save}")
            
        except Exception as e:
            logger.warning(f"Could not read elites_to_save from config, using default {elites_to_save}: {e}")
            pass
        
        # Limit to available elites
        elites_to_export = min(elites_to_save, len(elites))
        
        def serialize_object(obj):
            """Convert objects to JSON-serializable format"""
            if hasattr(obj, '__dict__'):
                result = {}
                for key, value in obj.__dict__.items():
                    if hasattr(value, '__dict__'):
                        result[key] = serialize_object(value)
                    elif isinstance(value, list):
                        result[key] = [serialize_object(item) if hasattr(item, '__dict__') else item for item in value]
                    elif isinstance(value, dict):
                        result[key] = {k: serialize_object(v) if hasattr(v, '__dict__') else v for k, v in value.items()}
                    else:
                        result[key] = value
                return result
            else:
                return obj
        
        # Prepare optimization results package
        optimization_package = {
            'folder_name': f"{timestamp}_{test_name}",
            'timestamp': timestamp,
            'test_name': test_name,
            'files': {}
        }
        
        # 1. Elite configurations (same format as old system)
        elite_files = {}
        for i in range(elites_to_export):
            elite = elites[i]
            
            if hasattr(elite, 'individual') and hasattr(elite.individual, 'monitor_configuration'):
                monitor_config = elite.individual.monitor_configuration
                
                # Extract trade executor config
                elite_trade_executor = {}
                if hasattr(monitor_config, 'trade_executor'):
                    te = monitor_config.trade_executor
                    elite_trade_executor = {
                        'default_position_size': getattr(te, 'default_position_size', 100.0),
                        'stop_loss_pct': getattr(te, 'stop_loss_pct', 0.01),
                        'take_profit_pct': getattr(te, 'take_profit_pct', 0.02),
                        'ignore_bear_signals': getattr(te, 'ignore_bear_signals', False),
                        'trailing_stop_loss': getattr(te, 'trailing_stop_loss', False),
                        'trailing_stop_distance_pct': getattr(te, 'trailing_stop_distance_pct', 0.01),
                        'trailing_stop_activation_pct': getattr(te, 'trailing_stop_activation_pct', 0.005)
                    }
                else:
                    elite_trade_executor = {
                        'default_position_size': 100.0,
                        'stop_loss_pct': 0.01,
                        'take_profit_pct': 0.02,
                        'ignore_bear_signals': False,
                        'trailing_stop_loss': False,
                        'trailing_stop_distance_pct': 0.01,
                        'trailing_stop_activation_pct': 0.005
                    }
                
                # Convert indicators to proper dict format
                elite_indicators_list = []
                if hasattr(monitor_config, 'indicators') and monitor_config.indicators:
                    for indicator in monitor_config.indicators:
                        indicator_dict = {
                            'name': indicator.name,
                            'type': indicator.type,
                            'indicator_class': indicator.indicator_class,
                            'agg_config': indicator.agg_config,
                            'calc_on_pip': getattr(indicator, 'calc_on_pip', False),
                            'parameters': dict(indicator.parameters) if hasattr(indicator, 'parameters') else {}
                        }
                        elite_indicators_list.append(indicator_dict)
                
                # Create elite config in the same format as old system
                elite_config = {
                    'monitor': {
                        'name': getattr(monitor_config, 'name', f"Elite {i+1}"),
                        'description': getattr(monitor_config, 'description', f"Elite monitor #{i+1}"),
                        'trade_executor': elite_trade_executor,
                        'enter_long': serialize_object(getattr(monitor_config, 'enter_long', [])),
                        'exit_long': serialize_object(getattr(monitor_config, 'exit_long', [])),
                        'bars': serialize_object(getattr(monitor_config, 'bars', {})),
                    },
                    'indicators': elite_indicators_list
                }
                
                elite_filename = f"{timestamp}_{test_name}_elite_{i+1}.json"
                elite_files[elite_filename] = elite_config
        
        # 2. Objectives evolution CSV
        objectives_csv = ""
        if best_individuals_log:
            # Get all unique objective names
            all_objectives = set()
            for entry in best_individuals_log:
                all_objectives.update(entry['metrics'].keys())
            
            # CSV header
            header = ['Generation'] + sorted(list(all_objectives))
            objectives_csv = ','.join(header) + '\n'
            
            # CSV data rows
            for entry in best_individuals_log:
                row = [str(entry['generation'])]
                for obj_name in sorted(list(all_objectives)):
                    row.append(str(entry['metrics'].get(obj_name, '')))
                objectives_csv += ','.join(row) + '\n'
        
        # 3. Original GA config with metadata
        ga_config_with_metadata = dict(ga_config_data)
        ga_config_with_metadata['optimization_metadata'] = {
            'timestamp': timestamp,
            'results_directory': f"{timestamp}_{test_name}",
            'elites_exported': elites_to_export,
            'total_generations': len(best_individuals_log) if best_individuals_log else 0
        }
        
        # 4. Summary report
        summary_text = f"""Genetic Algorithm Optimization Results
=====================================

Test Name: {test_name}
Timestamp: {timestamp}
Total Generations: {len(best_individuals_log) if best_individuals_log else 0}
Elites Saved: {elites_to_export}

"""
        
        if best_individuals_log:
            summary_text += "Final Best Metrics:\n"
            final_metrics = best_individuals_log[-1]['metrics']
            for metric_name, metric_value in final_metrics.items():
                summary_text += f"  {metric_name}: {metric_value}\n"
            summary_text += "\n"
        
        if elites:
            summary_text += "Elite Performance Summary:\n"
            for i in range(elites_to_export):
                elite = elites[i]
                if hasattr(elite, 'fitness_values'):
                    fitness_str = ", ".join([f"{val:.6f}" for val in elite.fitness_values])
                    summary_text += f"  Elite {i+1}: [{fitness_str}]\n"
            summary_text += "\n"
        
        summary_text += f"Files created:\n"
        for filename in elite_files.keys():
            summary_text += f"  - {filename}\n"
        summary_text += f"  - {timestamp}_{test_name}_objectives.csv\n"
        summary_text += f"  - {timestamp}_{test_name}_original_ga_config.json\n"
        summary_text += f"  - {timestamp}_{test_name}_summary.txt\n"
        
        # Package everything for frontend
        optimization_package['files'] = elite_files
        optimization_package['objectives_csv'] = objectives_csv
        optimization_package['objectives_filename'] = f"{timestamp}_{test_name}_objectives.csv"
        optimization_package['ga_config'] = ga_config_with_metadata
        optimization_package['ga_config_filename'] = f"{timestamp}_{test_name}_original_ga_config.json"
        optimization_package['summary'] = summary_text
        optimization_package['summary_filename'] = f"{timestamp}_{test_name}_summary.txt"
        optimization_package['elites_count'] = elites_to_export
        
        logger.info(f"✅ Prepared optimization package with {elites_to_export} elites")
        
        return jsonify({
            'success': True,
            'package': optimization_package,
            'message': f'Optimization package prepared with {elites_to_export} elite configurations'
        })
        
    except Exception as e:
        logger.error(f"Error exporting elites: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/get_elite/<int:index>')
def get_elite(index):
    """Get a specific elite by index"""
    try:
        elites = OptimizationState().get('elites', [])
        
        if not elites:
            return jsonify({'success': False, 'error': 'No elites available'})
        
        if index >= len(elites):
            return jsonify({'success': False, 'error': 'Elite index out of range'})
        
        elite = elites[index]
        
        # Convert to format suitable for replay visualization
        elite_data = {
            'index': index,
            'fitness': getattr(elite, 'fitness', 0),
            'config': elite.to_config() if hasattr(elite, 'to_config') else elite.genotype if hasattr(elite, 'genotype') else {}
        }
        
        return jsonify({
            'success': True,
            'elite': elite_data
        })
        
    except Exception as e:
        logger.error(f"Error getting elite {index}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@optimizer_bp.route('/api/pause_optimization', methods=['POST'])
def api_pause_optimization():
    """Pause the optimization via REST API"""
    try:
        from flask import current_app

        if OptimizationState().is_running():
            OptimizationState().set('paused', True)
            logger.info("Optimization paused via REST API - will finish current generation")

            # Also emit WebSocket event for real-time UI updates
            try:
                socketio = current_app.extensions.get('socketio')
                if socketio:
                    socketio.emit('optimization_paused', {
                        'generation': OptimizationState().get('current_generation', 0),
                        'total_generations': OptimizationState().get('total_generations', 0)
                    })
            except Exception as ws_error:
                logger.warning(f"Could not emit WebSocket event: {ws_error}")

            return jsonify({
                'success': True,
                'message': 'Optimization paused - will finish current generation',
                'generation': OptimizationState().get('current_generation', 0),
                'total_generations': OptimizationState().get('total_generations', 0)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No optimization is currently running'
            })
    except Exception as e:
        logger.error(f"Error pausing optimization: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@optimizer_bp.route('/api/resume_optimization', methods=['POST'])
def api_resume_optimization():
    """Resume the optimization via REST API"""
    try:
        from flask import current_app

        if OptimizationState().is_running() and OptimizationState().is_paused():
            OptimizationState().set('paused', False)
            logger.info("Optimization resumed via REST API")

            # Also emit WebSocket event for real-time UI updates
            try:
                socketio = current_app.extensions.get('socketio')
                if socketio:
                    socketio.emit('optimization_resumed', {
                        'generation': OptimizationState().get('current_generation', 0),
                        'total_generations': OptimizationState().get('total_generations', 0)
                    })
            except Exception as ws_error:
                logger.warning(f"Could not emit WebSocket event: {ws_error}")

            return jsonify({
                'success': True,
                'message': 'Optimization resumed',
                'generation': OptimizationState().get('current_generation', 0),
                'total_generations': OptimizationState().get('total_generations', 0)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No paused optimization found to resume'
            })
    except Exception as e:
        logger.error(f"Error resuming optimization: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@optimizer_bp.route('/api/export_elite/<int:index>')
def export_elite(index):
    """Export a specific elite configuration"""
    try:

        elites = OptimizationState().get('elites', [])
        
        if not elites:
            return jsonify({'success': False, 'error': 'No elites available'})
        
        if index >= len(elites):
            return jsonify({'success': False, 'error': 'Elite index out of range'})
        
        elite = elites[index]
        
        # Convert to configuration format
        if hasattr(elite, 'to_config'):
            elite_config = elite.to_config()
        else:
            elite_config = {
                'test_name': f'Elite_{index + 1}_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                'monitor': elite.genotype if hasattr(elite, 'genotype') else {},
                'elite_fitness': getattr(elite, 'fitness', 0)
            }
        
        return jsonify({
            'success': True,
            'config': elite_config
        })
        
    except Exception as e:
        logger.error(f"Error exporting elite {index}: {e}")
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/get_elites')
def get_elites():
    """Get list of elites with summary metrics for selection"""
    try:
        elites = OptimizationState().get('elites', [])

        if not elites:
            return jsonify({'success': False, 'error': 'No elites available'})

        # Build summary data for each elite
        elite_summaries = []
        for i, elite in enumerate(elites):
            # Extract key metrics
            total_pnl = None
            win_rate = None
            total_trades = None

            # IndividualStats stores metrics in additional_data dictionary
            if hasattr(elite, 'additional_data') and elite.additional_data:
                metrics = elite.additional_data

                # Try different metric key names that might be present
                total_pnl = metrics.get('total_pnl') or metrics.get('net_pnl') or metrics.get('pnl')
                winning_trades = metrics.get('winning_trades', 0)
                losing_trades = metrics.get('losing_trades', 0)
                total_trades = metrics.get('total_trades', 0)

                # Calculate win rate if we have trade counts
                if not total_trades and (winning_trades or losing_trades):
                    total_trades = winning_trades + losing_trades

                if total_trades > 0:
                    win_rate = (winning_trades / total_trades) * 100

            # Fallback: Check if metrics stored directly in elite attributes
            elif hasattr(elite, 'performance_metrics'):
                metrics = elite.performance_metrics
                total_pnl = metrics.get('total_pnl', None)
                winning_trades = metrics.get('winning_trades', 0)
                total_trades = metrics.get('total_trades', 0)

                if total_trades > 0:
                    win_rate = (winning_trades / total_trades) * 100

            elite_summaries.append({
                'index': i,
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'total_trades': total_trades
            })

        logger.info(f"✅ Retrieved {len(elite_summaries)} elites with metrics")
        return jsonify({
            'success': True,
            'elites': elite_summaries
        })

    except Exception as e:
        logger.error(f"❌ Error getting elites: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@optimizer_bp.route('/api/get_elite_config/<int:index>')
def get_elite_config(index):
    """Get full configuration for a specific elite"""
    try:
        elites = OptimizationState().get('elites', [])

        if not elites:
            return jsonify({'success': False, 'error': 'No elites available'})

        if index >= len(elites):
            return jsonify({'success': False, 'error': 'Elite index out of range'})

        elite = elites[index]

        # Extract monitor configuration from elite
        # IndividualStats has an 'individual' attribute which is an MlfIndividual
        # MlfIndividual has a 'monitor_configuration' attribute
        monitor_config = None

        if hasattr(elite, 'individual') and hasattr(elite.individual, 'monitor_configuration'):
            # MlfIndividual stores MonitorConfiguration (Pydantic BaseModel)
            monitor_config_obj = elite.individual.monitor_configuration

            # Pydantic models have model_dump() or dict() methods
            if hasattr(monitor_config_obj, 'model_dump'):
                # Pydantic v2
                monitor_config = monitor_config_obj.model_dump()
            elif hasattr(monitor_config_obj, 'dict'):
                # Pydantic v1
                monitor_config = monitor_config_obj.dict()
            else:
                # Fallback: Manual conversion
                logger.warning("Using manual conversion for MonitorConfiguration")
                monitor_config = {
                    'name': getattr(monitor_config_obj, 'name', ''),
                    'description': getattr(monitor_config_obj, 'description', ''),
                    'trade_executor': getattr(monitor_config_obj, 'trade_executor', {}),
                    'bars': getattr(monitor_config_obj, 'bars', {}),
                    'enter_long': getattr(monitor_config_obj, 'enter_long', []),
                    'exit_long': getattr(monitor_config_obj, 'exit_long', []),
                    'indicators': []
                }

                # Convert indicators if present
                if hasattr(monitor_config_obj, 'indicators'):
                    for ind in monitor_config_obj.indicators:
                        if hasattr(ind, 'model_dump'):
                            monitor_config['indicators'].append(ind.model_dump())
                        elif hasattr(ind, 'dict'):
                            monitor_config['indicators'].append(ind.dict())
                        else:
                            monitor_config['indicators'].append({
                                'name': getattr(ind, 'name', ''),
                                'indicator_class': getattr(ind, 'indicator_class', ''),
                                'agg_config': getattr(ind, 'agg_config', ''),
                                'parameters': getattr(ind, 'parameters', {}),
                                'ranges': getattr(ind, 'ranges', {})
                            })
        elif hasattr(elite, 'genotype'):
            monitor_config = elite.genotype
        elif hasattr(elite, 'to_config'):
            config = elite.to_config()
            monitor_config = config.get('monitor', {})

        if not monitor_config:
            logger.error(f"❌ Could not extract monitor configuration from elite {index}")
            return jsonify({'success': False, 'error': 'Could not extract monitor configuration'})

        # Log indicator data for debugging
        if 'indicators' in monitor_config and monitor_config['indicators']:
            logger.info(f"📊 Elite {index} has {len(monitor_config['indicators'])} indicators")
            for i, ind in enumerate(monitor_config['indicators']):
                logger.info(f"📊 Indicator {i}: name={ind.get('name')}, class={ind.get('indicator_class')}, agg={ind.get('agg_config')}")

        logger.info(f"✅ Successfully extracted monitor config for elite {index}")
        return jsonify({
            'success': True,
            'monitor_config': monitor_config
        })

    except Exception as e:
        logger.error(f"❌ Error getting elite config {index}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


# The WebSocket handlers will need to be registered in the main app.py file
# since they need access to the socketio instance
