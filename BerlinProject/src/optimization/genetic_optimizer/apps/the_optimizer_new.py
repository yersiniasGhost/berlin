# Example of how to run the_optimizer.py with your new setup

import json
import numpy as np
import time
from pathlib import Path
import random
import argparse

from optimization.genetic_optimizer.apps.utils.mlf_optimizer_config import MlfOptimizerConfig

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MTA Optimizer Application.')
    parser.add_argument('payload', type=str, nargs='+', help='JSON file of the optimization configuration')
    parser.add_argument('data_config', type=str,
                        help='JSON file of the data configuration')  # NEW: Add data config argument

    parser.add_argument('-g', "--config", type=str, help="Specify the GA configuration file (if separate)", default="")
    parser.add_argument('-o', '--output', type=str, help="Specify output path (default: output).", default="output")
    parser.add_argument("-s", '--seed', type=int, help="Set the numpy random number seed.", default=6999)
    parser.add_argument("-v", '--visualize', action='store_true', default=False,
                        help='Pop up the graphs for run-time visualization.')

    args = parser.parse_args()

    # Set random seeds
    np.random.seed(args.seed)
    random.seed(args.seed)

    # Parse file paths
    input_path = Path('.') / args.payload[0]
    data_config_file = args.data_config  # NEW: Get data config file path

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

    # FIXED: Load JSON manually and call from_json() instead of from_file()
    with open(input_path) as f:
        config_data = json.load(f)

    io = MlfOptimizerConfig.from_json(config_data, data_config_file)

    # Create and run genetic algorithm
    genetic_algorithm = io.create_project()

    # Run optimization
    s = time.time_ns()
    start = s
    skip = 1

    for stats in genetic_algorithm.run_ga_iterations(skip):
        e = time.time_ns()
        dt = (e - s) / 1e9

        # Log progress (same as before)
        objectives = [o.name for o in io.fitness_calculator.objectives]
        metrics = zip(objectives, stats[1].best_metric_iteration)
        metric_out = [f"{a}={b:.4f}" for a, b in metrics]

        eta = (dt / (stats[0].iteration + 1)) * (genetic_algorithm.number_of_generations - stats[0].iteration)
        out_str = f"{test_name}, {stats[0].iteration}/{genetic_algorithm.number_of_generations}, " \
                  f"{dt:.2f}s, eta: {eta / 60:.2f}m, {metric_out}"

        print(out_str)

        # Write logs
        with open(log_path / f'{tn}.iterations', 'a') as f:
            f.write(f'{out_str}\n')

        s = e

    print(f"Run took {(time.time_ns() - start) / 1e9} seconds")