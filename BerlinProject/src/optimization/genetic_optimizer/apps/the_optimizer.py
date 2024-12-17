import json
import numpy as np
import time
from pathlib import Path
import random
import argparse

from optimization.genetic_optimizer.apps.utils.mlf_optimizer_config import MlfOptimizerConfig
from optimization.mlf_optimizer.mlf_individual import MlfIndividual
from optimization.genetic_optimizer.abstractions.individual_stats import IndividualStats
import logging

# Set pymongo logger level to WARNING
logging.getLogger("pymongo").setLevel(logging.WARNING)

MAX_STALLED_METRIC = 200


def output_best_configuration(individual: MlfIndividual, output_path: Path):
    """Save the best monitor configuration using Pydantic serialization"""
    base_name = individual.monitor.name.replace(' ', '-').replace('/', '-')
    output_file = output_path / f"{base_name}_best.json"

    # Direct JSON serialization using Pydantic
    with open(output_file, "w") as f:
        f.write(individual.monitor_configuration.model_dump_json(
            indent=2,
            exclude_none=True  # Optional: excludes None values
        ))



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MTA Optimizer Application.')
    parser.add_argument('payload', type=str, nargs='+', help='JSON file of the optimization configuration')

    # parser.add_argument('name', type=str, nargs='+', help="Base name of the output files.")
    parser.add_argument('-g', "--config", type=str, help="Specify the GA configuration file (if separate)", default="")
    parser.add_argument('-o', '--output', type=str, help="Specify output path (default: output).", default="output")
    parser.add_argument("-s", '--seed', type=int, help="Set the numpy random number seed.", default=6999)
    parser.add_argument("-v", '--visualize', action='store_true', default=False,
                        help='Pop up the graphs for run-time visualization.')

    args = parser.parse_args()
    np.random.seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    input_path = Path('.') / args.payload[0]

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

    with open(input_path) as f:
        input_json = json.load(f)
        test_name = input_json.get('test_name', "NoNAME")
        max_stalled_metric = input_json.get('stalled_counter', MAX_STALLED_METRIC)

    tn = test_name.replace(' ', '-')
    tn = tn.replace('/', '-')
    copy_payload = output_path / f"{tn}_payload.json"
    # with open(log_path / f'{tn}.csv', 'w') as f:
    #     f.write(f"Random Seed: {args.seed}\n")

    log_p = Path(log_path) / f'{tn}.csv'
    if log_p.exists():
        log_p.unlink()
    log_p = Path(log_path) / f'{tn}.iterations'
    if log_p.exists():
        log_p.unlink()

    io = MlfOptimizerConfig.from_file(input_path, ga_config)
    # io.write_configuration(copy_payload)
    genetic_algorithm = io.create_project()

    s = time.time_ns()
    start = s
    skip = 1
    stalled_metric = 0
    last_metric = 0
    sum_dt = 0

    best_overall = None
    best_metric_value = float('-inf')

    for stats in genetic_algorithm.run_ga_iterations(skip):
        e = time.time_ns()
        dt = (e - s) / 1e9
        sum_dt += dt
        objectives = [o.name for o in io.fitness_calculator.objectives] + ['METRIC']
        metrics = zip(objectives, stats[1].best_metric_iteration)
        metric_out = [f"{a}={b:.4f}" for a, b in metrics]
        if last_metric == metric_out:
            stalled_metric += skip
        else:
            stalled_metric = 0
        eta = (sum_dt / (stats[0].iteration + 1)) * (genetic_algorithm.number_of_generations - stats[0].iteration)
        out_str = f"{test_name}, {stats[0].iteration}/{genetic_algorithm.number_of_generations}, {stalled_metric}/{max_stalled_metric}, " \
                  f"{dt:.2f}s, eta: {eta / 60:.2f}m, {metric_out}"
        s = e
        print("\n", out_str)
        ot, sep = "", ""
        with open(log_path / f'{tn}.csv', 'a') as f:
            for m in stats[1].best_metric_iteration:
                ot += sep + f"{m:.4f}"
                sep = ", "
            f.write(f'{ot}\n')

        with open(log_path / f'{tn}.iterations', 'a') as f:
            f.write(f'{out_str}\n')

        best = stats[1].best_front[0]
        current_metric = stats[1].best_metric_iteration[-1]  # Gets the final metric

        # Track best configuration
        if best_overall is None or current_metric > best_metric_value:
            best_overall = best
            best_metric_value = current_metric

        last_metric = metric_out

        # if stats[0].iteration % skip == 0:
        #     output_best_monitor(best, plots_path)

        io.fitness_calculator.set_final_result(True)
        io.fitness_calculator.calculate_fitness_functions(-9, [best.individual])
        io.fitness_calculator.set_final_result(False)
        io.fitness_calculator.reset_episode()
        output_best_configuration(best.individual, output_path)



    print(f"Run took {(time.time_ns() - start) / 1e9} seconds")
