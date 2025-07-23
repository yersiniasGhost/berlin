import json
import numpy as np
import time
from pathlib import Path
import random
import argparse

from optimization.genetic_optimizer.apps.utils.mlf_optimizer_config import MlfOptimizerConfig


def display_final_results(fitness_calculator, best_individual):
    """Display detailed final results for the best individual"""
    print("\n" + "=" * 60)
    print("🏆 FINAL OPTIMIZATION RESULTS")
    print("=" * 60)

    # Set display mode for detailed output
    fitness_calculator.set_final_result(True)

    # Run final backtest on best individual
    portfolio = fitness_calculator.backtest_streamer.replace_monitor_config(best_individual.monitor_configuration)
    portfolio = fitness_calculator.backtest_streamer.run()

    # Display trading performance
    total_trades = portfolio.get_winning_trades_count() + portfolio.get_losing_trades_count()
    winning_trades = portfolio.get_winning_trades_count()
    losing_trades = portfolio.get_losing_trades_count()
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    total_profit = portfolio.get_total_percent_profits()
    total_loss = portfolio.get_total_percent_losses()
    net_pnl = total_profit - abs(total_loss)

    print(f"📊 TRADING PERFORMANCE:")
    print(f"   Total Trades: {total_trades}")
    print(f"   Winning Trades: {winning_trades}")
    print(f"   Losing Trades: {losing_trades}")
    print(f"   Win Rate: {win_rate:.1f}%")
    print(f"\n💰 PnL BREAKDOWN:")
    print(f"   Total Profit: +{total_profit:.3f}%")
    print(f"   Total Loss: {total_loss:.3f}%")
    print(f"   Net PnL: {net_pnl:.3f}%")

    # Display strategy details
    print(f"\n📋 BEST STRATEGY CONFIGURATION:")
    print(f"   Monitor Name: {best_individual.monitor_configuration.name}")

    # Show indicators
    print(f"   Indicators ({len(best_individual.monitor_configuration.indicators)}):")
    for indicator in best_individual.monitor_configuration.indicators:
        print(f"     • {indicator.name}: {indicator.function}")
        key_params = {k: v for k, v in indicator.parameters.items() if k in ['period', 'lookback', 'threshold']}
        if key_params:
            print(f"       {key_params}")

    # Show enter/exit conditions
    enter_conditions = getattr(best_individual.monitor_configuration, 'enter_long', [])
    exit_conditions = getattr(best_individual.monitor_configuration, 'exit_long', [])

    if enter_conditions:
        print(f"   Entry Conditions ({len(enter_conditions)}):")
        for condition in enter_conditions:
            print(f"     • {condition.get('name', 'Unknown')} >= {condition.get('threshold', 'N/A')}")

    if exit_conditions:
        print(f"   Exit Conditions ({len(exit_conditions)}):")
        for condition in exit_conditions:
            print(f"     • {condition.get('name', 'Unknown')} >= {condition.get('threshold', 'N/A')}")

    # Calculate some performance metrics
    if total_trades > 0:
        avg_profit_per_trade = total_profit / winning_trades if winning_trades > 0 else 0
        avg_loss_per_trade = abs(total_loss) / losing_trades if losing_trades > 0 else 0
        risk_reward_ratio = avg_profit_per_trade / avg_loss_per_trade if avg_loss_per_trade > 0 else float('inf')

        print(f"\n📈 PERFORMANCE METRICS:")
        print(f"   Avg Profit per Win: +{avg_profit_per_trade:.3f}%")
        print(f"   Avg Loss per Loss: -{avg_loss_per_trade:.3f}%")
        print(f"   Risk/Reward Ratio: 1:{risk_reward_ratio:.2f}")

    # Reset display mode
    fitness_calculator.set_final_result(False)

    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MTA Optimizer Application with Enhanced Results Display.')
    parser.add_argument('payload', type=str, nargs='+', help='JSON file of the optimization configuration')
    parser.add_argument('data_config', type=str, help='JSON file of the data configuration')

    parser.add_argument('-g', "--config", type=str, help="Specify the GA configuration file (if separate)", default="")
    parser.add_argument('-o', '--output', type=str, help="Specify output path (default: output).", default="output")
    parser.add_argument("-s", '--seed', type=int, help="Set the numpy random number seed.", default=6999)
    parser.add_argument("-v", '--visualize', action='store_true', default=False,
                        help='Pop up the graphs for run-time visualization.')

    args = parser.parse_args()

    # Set random seeds
    np.random.seed(69)
    random.seed(69)

    # Parse file paths
    input_path = Path('.') / args.payload[0]
    data_config_file = args.data_config

    output_path = Path('.') / args.output
    output_path.mkdir(exist_ok=True, parents=True)
    log_path = output_path / 'logs'
    log_path.mkdir(exist_ok=True)
    plots_path = output_path / 'plots'
    plots_path.mkdir(exist_ok=True)

    show_graphs = args.visualize

    ga_config = None
    if args.config:
        ga_config = Path('.') / args.config

    # Load test name from main config
    with open(input_path) as f:
        input_json = json.load(f)
        test_name = input_json.get('test_name', "NoNAME")

    tn = test_name.replace(' ', '-')
    tn = tn.replace('/', '-')

    # Create log files
    log_p = Path(log_path) / f'{tn}.csv'
    if log_p.exists():
        log_p.unlink()
    log_p = Path(log_path) / f'{tn}.iterations'
    if log_p.exists():
        log_p.unlink()

    # Load configuration and create optimizer
    with open(input_path) as f:
        config_data = json.load(f)

    io = MlfOptimizerConfig.from_json(config_data, data_config_file)
    genetic_algorithm = io.create_project()

    print(f"🚀 Starting optimization: {test_name}")
    print(f"   Generations: {genetic_algorithm.number_of_generations}")
    print(f"   Population Size: {genetic_algorithm.population_size}")
    print(f"   Data Config: {data_config_file}")

    # Run optimization
    s = time.time_ns()
    start = s
    skip = 1
    best_individual = None

    for stats in genetic_algorithm.run_ga_iterations(skip):
        e = time.time_ns()
        dt = (e - s) / 1e9
        print(dt)

        # Store best individual
        best_individual = stats[1].best_front[0].individual

        # Log progress
        objectives = [o.name for o in io.fitness_calculator.objectives]
        metrics = zip(objectives, stats[1].best_metric_iteration)
        metric_out = [f"{a}={b:.4f}" for a, b in metrics]

        eta = dt * (genetic_algorithm.number_of_generations - stats[0].iteration)
        # eta = (dt / (stats[0].iteration + 1)) * (genetic_algorithm.number_of_generations - stats[0].iteration)

        out_str = f"{test_name}, {stats[0].iteration}/{genetic_algorithm.number_of_generations}, " \
                  f"{dt:.2f}s, eta: {eta / 60:.2f}m, {metric_out}"

        print(out_str)

        # Write logs
        with open(log_path / f'{tn}.iterations', 'a') as f:
            f.write(f'{out_str}\n')

        s = e

    total_time = (time.time_ns() - start) / 1e9
    print(f"\n⏱️  Optimization completed in {total_time:.1f} seconds")

    # Display detailed final results
    if best_individual:
        display_final_results(io.fitness_calculator, best_individual)