import json
import numpy as np
import time
from pathlib import Path
import random
import argparse

from optimization.genetic_optimizer.apps.utils.mlf_optimizer_config import MlfOptimizerConfig
from optimization.mlf_optimizer import MlfIndividual

MAX_STALLED_METRIC = 200


def output_best_monitor(individual: MlfIndividual):
    print("BEST Result")
    print(individual)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MTA Optimizer Application.')
    parser.add_argument('payload', type=str, nargs='+', help='JSON file of the optimization configuration')
    
    # parser.add_argument('name', type=str, nargs='+', help="Base name of the output files.")
    parser.add_argument('-g', "--config", type=str, help="Specify the GA configuration file (if separate)", default="")
    parser.add_argument('-o', '--output', type=str, help="Specify output path (default: output).", default="output")
    parser.add_argument("-s", '--seed', type=int, help="Set the numpy random number seed.", default=996942)
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
    with open(log_path / f'{tn}.csv', 'w') as f:
        f.write(f"Random Seed: {args.seed}\n")

    io = MlfOptimizerConfig.from_file(input_path, ga_config)
    io.write_configuration(copy_payload)
    genetic_algorithm = io.create_project()

    s = time.time_ns()
    start = s
    skip = 5
    stalled_metric = 0
    last_metric = 0
    sum_dt = 0
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
        eta = (sum_dt / (stats[0].iteration+1)) * (genetic_algorithm.number_of_generations - stats[0].iteration)
        out_str = f"{test_name}, {stats[0].iteration}/{genetic_algorithm.number_of_generations}, {stalled_metric}/{max_stalled_metric}, " \
                  f"{dt:.2f}s, eta: {eta / 60:.2f}m, {metric_out}"
        s = e
        print(out_str)
        ot, sep = "", ""
        with open(log_path / f'{tn}.csv', 'a') as f:
            for m in stats[1].best_metric_iteration:
                ot += sep + f"{m:.4f}"
                sep = ", "
            f.write(f'{ot}\n')

        with open(log_path / f'{tn}.iterations', 'a') as f:
            f.write(f'{out_str}\n')
        best = stats[1].best_front[0]
        last_metric = metric_out

        if stats[0].iteration % 50 == 0:
            tn_iter = f"{tn}--{stats[0].iteration}"
            plot_combined_results(io, best.individual, plots_path, tn_iter, show_graphs, io.start_date, io.time_frame)


        if stalled_metric == MAX_STALLED_METRIC or stats[0].iteration == genetic_algorithm.number_of_generations - 1:
            # plot_optimized_curves(io, best.individual, plots_path, tn, show_graphs, io.start_date)
            # plot_tasks(best.individual, io, plots_path, tn, show_graphs, io.start_date, io.time_frame)

            output_task_spreadsheet(io, best.individual, plots_path, tn, io.start_date)
            plot_combined_results(io, best.individual, plots_path, tn, show_graphs, io.start_date, io.time_frame)
            break

    print(f"Run took {(time.time_ns() - start)/1e9} seconds")

