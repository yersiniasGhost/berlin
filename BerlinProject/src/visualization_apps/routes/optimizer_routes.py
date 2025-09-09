"""
Optimizer Visualization Routes
Handles genetic algorithm optimization with real-time WebSocket updates
"""

from flask import Blueprint, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import os
import sys
import json
import logging
import threading
import time
import csv
import math
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

# Add project path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, '..', '..'))

# Import necessary modules for optimizer visualization
from optimization.genetic_optimizer.apps.utils.mlf_optimizer_config import MlfOptimizerConfig
from optimization.calculators.yahoo_finance_historical import YahooFinanceHistorical
from portfolios.portfolio_tool import TradeReason
from optimization.genetic_optimizer.abstractions import IndividualBase
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
from optimization.genetic_optimizer.genetic_algorithm import crowd_sort

# Remove new indicator system imports that are causing backend conflicts
# from indicator_triggers.indicator_base import IndicatorRegistry
# from indicator_triggers.refactored_indicators import *  # Import to register indicators

logger = logging.getLogger('OptimizerVisualization')

# Create Blueprint
optimizer_bp = Blueprint('optimizer', __name__, url_prefix='/optimizer')

# Global optimization state
optimization_state = {
    'running': False,
    'paused': False,
    'thread': None,
    'ga_instance': None,
    'io_instance': None,
    'current_generation': 0,
    'total_generations': 0,
    'best_individuals_log': [],
    'last_best_individual': None,
    'test_name': None
}

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

def balance_fronts(front: List[IndividualStats]) -> List[IndividualStats]:
    ideal_point = np.min([ind.fitness_values for ind in front], axis=0)
    balanced_front = sorted(front, key=lambda ind: np.linalg.norm(ind.fitness_values - ideal_point))
    return balanced_front

def select_winning_population(number_of_elites: int, fronts: Dict[int, List]) -> [List[IndividualStats]]:
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
        
        logger.info(f"📊 Processing trade distribution data... P&L entries: {len(chart_data.get('pnl_history', []))}")
        if chart_data.get('pnl_history'):
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
        
        # 4. Performance Metrics Table Data (like old app table format)
        performance_metrics = []
        logger.info(f"📊 Processing performance metrics... Chart data available: {bool(chart_data)}")
        if best_individuals_log:
            current_generation = best_individuals_log[-1]['generation'] if best_individuals_log else 1
            
            # Try to calculate metrics from chart data if available
            if chart_data.get('pnl_history'):
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
                    
                    # Create performance data for the current generation (like old app does)
                    perf_data = {
                        'generation': current_generation,
                        'total_pnl': total_pnl,
                        'total_trades': total_trades,
                        'winning_trades': len(winning_trades),
                        'losing_trades': len(losing_trades),
                        'avg_win': avg_win,
                        'avg_loss': avg_loss
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
        
        # Combine all chart data (matching old app format)
        optimizer_charts = {
            'objective_evolution': objective_evolution,
            'winning_trades_distribution': winning_trades_distribution,
            'losing_trades_distribution': losing_trades_distribution,
            'elite_population_data': elite_population_data,
            'objective_names': objectives,
            'performance_metrics': performance_metrics,
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
        backtest_streamer = io.fitness_calculator.backtest_streamer
        
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
    """Generate chart data for the given best individual using NEW indicator system"""
    # Load candle data
    candlestick_data, data_config = load_raw_candle_data(data_config_path, io)

    # IMPORTANT: Run backtest for this specific individual to get trades and bar scores
    backtest_streamer = io.fitness_calculator.backtest_streamer
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

def run_genetic_algorithm_threaded_with_new_indicators(ga_config_path: str, data_config_path: str, socketio):
    """Run the genetic algorithm optimization with NEW indicator system"""
    global optimization_state

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
        optimization_state['test_name'] = test_name
        optimization_state['ga_config_path'] = ga_config_path

        # Process indicators using old system for now (new system disabled)
        processed_indicators = []
        # TODO: Re-enable new indicator system when fully integrated
        # if 'indicators' in config_data:
        #     registry = IndicatorRegistry()
        #     ... (new system code commented out)
        logger.info("Using old indicator system for compatibility")

        # Create optimizer config with processed indicators
        io = MlfOptimizerConfig.from_json(config_data, data_config_path)
        genetic_algorithm = io.create_project()

        # Store instances for state management
        optimization_state['ga_instance'] = genetic_algorithm
        optimization_state['io_instance'] = io
        optimization_state['total_generations'] = genetic_algorithm.number_of_generations
        optimization_state['current_generation'] = 0
        optimization_state['best_individuals_log'] = []
        optimization_state['processed_indicators'] = processed_indicators

        logger.info(f"   Test: {test_name}")
        logger.info(f"   Generations: {genetic_algorithm.number_of_generations}")
        logger.info(f"   Population Size: {genetic_algorithm.population_size}")
        logger.info(f"   Elitist Size: {genetic_algorithm.elitist_size}")
        logger.info(f"   New Indicators: {len(processed_indicators)}")

        # Store timestamp for later use
        optimization_timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        optimization_state['timestamp'] = optimization_timestamp

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
            # Check if stopped
            if not optimization_state['running']:
                logger.info("Optimization stopped by user")
                break

            # Wait while paused
            while optimization_state['paused'] and optimization_state['running']:
                time.sleep(0.1)

            # Check if stopped during pause
            if not optimization_state['running']:
                logger.info("Optimization stopped during pause")
                break

            # Fix generation numbering - stats returns 0-based, we want 1-based display
            current_gen = observer.iteration + 1  # Convert from 0-based to 1-based
            best_individual = statsobserver.best_front[0].individual
            metrics = statsobserver.best_metric_iteration

            elites = select_winning_population(genetic_algorithm.elitist_size, observer.fronts)            
            elite_objectives=[e.fitness_values for e in elites]
            optimization_state['current_generation'] = current_gen
            optimization_state['last_best_individual'] = best_individual
            optimization_state['elites'] = elites

            # Log best individual for this generation
            objectives = [o.name for o in io.fitness_calculator.objectives]
            fitness_log = {
                'generation': current_gen,
                'metrics': dict(zip(objectives, metrics))
            }
            optimization_state['best_individuals_log'].append(fitness_log)

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
                    optimization_state['best_individuals_log'], objectives
                )

                # Convert numpy arrays to regular Python lists for JSON serialization
                elite_objectives = [e.fitness_values.tolist() for e in elites]

                socketio.emit('generation_complete', {
                    'generation': current_gen,
                    'total_generations': genetic_algorithm.number_of_generations,
                    'fitness_metrics': dict(zip(objectives, metrics)),
                    'chart_data': optimizer_charts,
                    'best_individuals_log': optimization_state['best_individuals_log'],
                    'elite_objective_values': elite_objectives,
                    'objective_names': objectives,
                    'optimizer_charts': optimizer_charts  # Specifically for optimizer frontend
                })

            except Exception as e:
                logger.error(f"Error generating chart data: {e}")
                socketio.emit('optimization_error', {'error': str(e)})
                break

        # Optimization completed
        if optimization_state['running']:
            logger.info("⏱️  Optimization completed successfully with NEW indicator system")

            # Auto-saving disabled - user will manually save best elites via UI button
            logger.info("✅ Optimization completed - elites available for manual saving via UI")
            # try:
            #     results_info = save_optimization_results_with_new_indicators(
            #         optimization_state['best_individuals_log'],
            #         optimization_state['last_best_individual'],
            #         optimization_state.get('elites', []),
            #         ga_config_path,
            #         test_name,
            #         optimization_state.get('timestamp'),
            #         optimization_state.get('processed_indicators', [])
            #     )

            # Emit completion event without automatic saving
            socketio.emit('optimization_complete', {
                'total_generations': optimization_state['current_generation'],
                'best_individuals_log': optimization_state['best_individuals_log'],
                'manual_save_available': True
            })

    except Exception as e:
        logger.error(f"❌ Error in threaded optimization: {e}")
        import traceback
        traceback.print_exc()
        socketio.emit('optimization_error', {'error': str(e)})

    finally:
        # Reset state
        optimization_state['running'] = False
        optimization_state['paused'] = False
        optimization_state['thread'] = None

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
                            'function': getattr(indicator, 'function', 'unknown'),
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

# Additional routes following the same pattern...
# (start_optimization, pause_optimization, etc. as WebSocket events)

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

        # Store paths globally so WebSocket handler can access them
        global optimization_state
        optimization_state['ga_config_path_temp'] = ga_config_path
        optimization_state['data_config_path_temp'] = data_config_path

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
    global optimization_state
    try:
        optimization_state['running'] = False
        optimization_state['paused'] = False
        
        if optimization_state['thread'] and optimization_state['thread'].is_alive():
            optimization_state['thread'].join(timeout=2)
        
        logger.info("Optimization stopped via REST API")
        return jsonify({
            'success': True,
            'message': 'Optimization stopped',
            'generation': optimization_state.get('current_generation', 0)
        })
    except Exception as e:
        logger.error(f"Error stopping optimization: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@optimizer_bp.route('/api/pause_optimization', methods=['POST'])
def api_pause_optimization():
    """Pause the optimization via REST API"""
    global optimization_state
    try:
        if optimization_state.get('running', False):
            optimization_state['paused'] = True
            logger.info("Optimization paused via REST API")
            return jsonify({
                'success': True,
                'message': 'Optimization paused',
                'generation': optimization_state.get('current_generation', 0)
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
    global optimization_state
    try:
        if optimization_state.get('running', False) and optimization_state.get('paused', False):
            optimization_state['paused'] = False
            logger.info("Optimization resumed via REST API")
            return jsonify({
                'success': True,
                'message': 'Optimization resumed',
                'generation': optimization_state.get('current_generation', 0)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No optimization is currently paused'
            })
    except Exception as e:
        logger.error(f"Error resuming optimization: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@optimizer_bp.route('/api/get_progress')
def get_progress():
    """Get current optimization progress and chart data"""
    global optimization_state
    
    try:
        if not optimization_state.get('running', False):
            return jsonify({
                'success': True,
                'progress': {
                    'current_generation': 0,
                    'total_generations': 0,
                    'completed': False
                },
                'charts': {},
                'elites': []
            })
        
        # Get current progress
        progress = {
            'current_generation': optimization_state.get('current_generation', 0),
            'total_generations': optimization_state.get('total_generations', 0),
            'completed': not optimization_state.get('running', False)
        }
        
        # Generate chart data from logged data
        charts = {}
        
        # Objective evolution chart - separate line for each objective
        if optimization_state.get('best_individuals_log'):
            objective_evolution = {}
            
            # Get objective names from the first entry
            first_entry = optimization_state['best_individuals_log'][0] if optimization_state['best_individuals_log'] else {}
            objectives = list(first_entry.get('metrics', {}).keys())
            
            # Initialize data structure for each objective
            for obj_name in objectives:
                objective_evolution[obj_name] = []
            
            for entry in optimization_state['best_individuals_log']:
                generation = entry['generation']
                metrics = entry['metrics']
                
                # Add data point for each objective
                for obj_name in objectives:
                    if obj_name in metrics:
                        objective_evolution[obj_name].append([generation, metrics[obj_name]])
            
            charts['objective_evolution'] = objective_evolution
        
        # Elite population data
        elites_data = []
        if optimization_state.get('elites'):
            for i, elite in enumerate(optimization_state['elites'][:10]):  # Top 10 elites
                # Try to get actual performance metrics from the elite individual
                total_pnl = 0.0
                win_rate = 0.0
                total_trades = 0
                max_drawdown = 0.0
                
                # Extract metrics from fitness_values or individual stats
                if hasattr(elite, 'fitness_values') and elite.fitness_values is not None:
                    if len(elite.fitness_values) > 0:
                        total_pnl = float(elite.fitness_values[0])  # First objective usually total PnL
                    if len(elite.fitness_values) > 1:
                        win_rate = float(elite.fitness_values[1]) * 100  # Second objective might be win rate
                
                # Try to get more detailed stats if available
                if hasattr(elite, 'individual') and hasattr(elite.individual, 'stats'):
                    stats = elite.individual.stats
                    total_pnl = getattr(stats, 'total_pnl', total_pnl)
                    win_rate = getattr(stats, 'win_rate', win_rate)
                    total_trades = getattr(stats, 'total_trades', 0)
                    max_drawdown = getattr(stats, 'max_drawdown', 0.0)
                
                elif hasattr(elite, 'individual') and hasattr(elite.individual, 'portfolio'):
                    # Try to calculate from portfolio if available
                    portfolio = elite.individual.portfolio
                    if hasattr(portfolio, 'trade_history') and portfolio.trade_history:
                        total_trades = len(portfolio.trade_history)
                        # Simple P&L calculation
                        if hasattr(portfolio, 'total_pnl'):
                            total_pnl = portfolio.total_pnl
                
                elite_data = {
                    'fitness': total_pnl,
                    'total_trades': total_trades,
                    'win_rate': win_rate,
                    'total_pnl': total_pnl,
                    'max_drawdown': abs(max_drawdown)  # Ensure positive value for display
                }
                elites_data.append(elite_data)
        
        return jsonify({
            'success': True,
            'progress': progress,
            'charts': charts,
            'elites': elites_data
        })
        
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
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

@optimizer_bp.route('/api/export_best_elite')
def export_best_elite():
    """Export the best performing elite as a JSON configuration"""
    try:
        # Use stored elites from optimization state
        elites = optimization_state.get('elites', [])
        
        if not elites:
            return jsonify({'success': False, 'error': 'No elites available'})
        
        # Get the best elite (first in list, should be sorted by fitness)
        best_elite = elites[0]
        
        # Convert elite individual to configuration format with proper serialization
        elite_config = None
        
        def serialize_object(obj):
            """Convert objects to JSON-serializable format"""
            if hasattr(obj, '__dict__'):
                # Convert object to dict, handling nested objects
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
        
        # Try different methods to get the configuration
        if hasattr(best_elite, 'individual') and hasattr(best_elite.individual, 'monitor_configuration'):
            # Best case: elite has the full monitor configuration
            monitor_config = best_elite.individual.monitor_configuration
            elite_config = {
                'test_name': f'Best_Elite_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                'monitor': {
                    'name': getattr(monitor_config, 'name', 'Best Elite Strategy'),
                    'description': f'Best performing elite from optimization run',
                    'bars': serialize_object(getattr(monitor_config, 'bars', {})),
                    'enter_long': serialize_object(getattr(monitor_config, 'enter_long', [])),
                    'exit_long': serialize_object(getattr(monitor_config, 'exit_long', [])),
                    'trade_executor': serialize_object(getattr(monitor_config, 'trade_executor', {}))
                },
                'indicators': serialize_object(getattr(monitor_config, 'indicators', []))
            }
        elif hasattr(best_elite, 'individual') and hasattr(best_elite.individual, 'genotype'):
            # Fallback: use genotype data
            genotype = best_elite.individual.genotype
            elite_config = {
                'test_name': f'Best_Elite_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                'monitor': genotype if isinstance(genotype, dict) else {},
                'indicators': []
            }
        else:
            # Last resort: create a basic config with fitness info
            elite_config = {
                'test_name': f'Best_Elite_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                'monitor': {
                    'name': 'Best Elite Strategy',
                    'description': 'Elite solution from genetic algorithm optimization'
                },
                'indicators': [],
                'elite_fitness': best_elite.fitness_values.tolist() if hasattr(best_elite, 'fitness_values') else []
            }
            
        # Add performance stats if available
        if hasattr(best_elite, 'fitness_values'):
            elite_config['performance_stats'] = {
                'fitness_values': best_elite.fitness_values.tolist() if hasattr(best_elite.fitness_values, 'tolist') else list(best_elite.fitness_values)
            }
        
        logger.info(f"Exporting best elite configuration: {elite_config.get('test_name', 'Unknown')}")
        
        return jsonify({
            'success': True,
            'config': elite_config,
            'message': 'Best elite configuration exported successfully'
        })
        
    except Exception as e:
        logger.error(f"Error exporting best elite: {e}")
        return jsonify({'success': False, 'error': str(e)})

@optimizer_bp.route('/api/export_elites')
def export_elites():
    """Export multiple elite configurations based on GA hyperparameters"""
    try:
        # Use stored elites from optimization state
        elites = optimization_state.get('elites', [])
        
        if not elites:
            return jsonify({'success': False, 'error': 'No elites available'})
        
        # Get number of elites to save from GA hyperparameters, default to 5
        elites_to_save = 5
        try:
            if optimization_state.get('ga_instance') and hasattr(optimization_state['ga_instance'], 'elitist_size'):
                elites_to_save = optimization_state['ga_instance'].elitist_size
            else:
                # Try to get from current configs
                if window and hasattr(window, 'currentConfigs') and window.currentConfigs.get('ga_config'):
                    ga_config = window.currentConfigs['ga_config']
                    elites_to_save = ga_config.get('ga_hyperparameters', {}).get('elite_size', 5)
        except:
            pass  # Use default
        
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
        
        elite_configs = []
        
        for i in range(elites_to_export):
            elite = elites[i]
            
            # Convert elite individual to configuration format
            if hasattr(elite, 'individual') and hasattr(elite.individual, 'monitor_configuration'):
                monitor_config = elite.individual.monitor_configuration
                elite_config = {
                    'test_name': f'Elite_{i + 1}_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                    'monitor': {
                        'name': getattr(monitor_config, 'name', f'Elite #{i + 1} Strategy'),
                        'description': f'Elite #{i + 1} from optimization run',
                        'bars': serialize_object(getattr(monitor_config, 'bars', {})),
                        'enter_long': serialize_object(getattr(monitor_config, 'enter_long', [])),
                        'exit_long': serialize_object(getattr(monitor_config, 'exit_long', [])),
                        'trade_executor': serialize_object(getattr(monitor_config, 'trade_executor', {}))
                    },
                    'indicators': serialize_object(getattr(monitor_config, 'indicators', []))
                }
            elif hasattr(elite, 'individual') and hasattr(elite.individual, 'genotype'):
                genotype = elite.individual.genotype
                elite_config = {
                    'test_name': f'Elite_{i + 1}_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                    'monitor': serialize_object(genotype) if isinstance(genotype, dict) else {},
                    'indicators': []
                }
            else:
                # Last resort
                elite_config = {
                    'test_name': f'Elite_{i + 1}_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                    'monitor': {
                        'name': f'Elite #{i + 1} Strategy',
                        'description': f'Elite #{i + 1} solution from genetic algorithm optimization'
                    },
                    'indicators': [],
                    'elite_fitness': elite.fitness_values.tolist() if hasattr(elite, 'fitness_values') else []
                }
            
            # Add performance stats if available
            if hasattr(elite, 'fitness_values'):
                elite_config['performance_stats'] = {
                    'fitness_values': elite.fitness_values.tolist() if hasattr(elite.fitness_values, 'tolist') else list(elite.fitness_values)
                }
            
            elite_configs.append(elite_config)
        
        logger.info(f"Exporting {len(elite_configs)} elite configurations")
        
        return jsonify({
            'success': True,
            'elites': elite_configs,
            'count': len(elite_configs),
            'message': f'{len(elite_configs)} elite configurations exported successfully'
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
        elites = optimization_state.get('elites', [])
        
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

@optimizer_bp.route('/api/export_elite/<int:index>')
def export_elite(index):
    """Export a specific elite configuration"""
    try:
        elites = optimization_state.get('elites', [])
        
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

# The WebSocket handlers will need to be registered in the main app.py file
# since they need access to the socketio instance