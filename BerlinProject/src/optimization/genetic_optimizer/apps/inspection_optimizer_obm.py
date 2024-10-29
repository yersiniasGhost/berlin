import json
import numpy as np
import time
from pathlib import Path
import random
import argparse

from utils import output_task_spreadsheet
from GeneticOptimizer.obm_optimizer.visualization import plot_combined_results
from GeneticOptimizer.obm_optimizer.json_parser.payload_parser import InspectionOptimizer
from GeneticOptimizer.obm_optimizer.obm_individual import OBMIndividual

MAX_STALLED_METRIC = 200

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Inspection Optimizer Application.')
    parser.add_argument('payload', type=str, nargs='+',
                        help='Relative path to the input payloads')
    # parser.add_argument('name', type=str, nargs='+', help="Base name of the output files.")
    parser.add_argument('-n', "--name", type=str, help="Override the payload file's test name", default="")
    parser.add_argument('-g', "--config", type=str, help="Specify the GA configuration file (if separate)", default="")
    parser.add_argument('-o', '--output', type=str, help="Specify output path (default: output).", default="output")
    parser.add_argument("-s", '--seed', type=int, help="Set the numpy random number seed.", default=996942)
    parser.add_argument("-v", '--visualize', action='store_true', default=False,
                        help='Pop up the graphs for run-time visualization.')
    parser.add_argument("-d", '--debug', type=int, default=-1,
                        help='Visualize every N steps.')

    args = parser.parse_args()
    np.random.seed(args.seed)
    random.seed(args.seed)
    input_path = Path('.') / args.payload[0]
    cmd_test_name = args.name
    output_path = Path('.') / args.output
    output_path.mkdir(exist_ok=True, parents=True)
    log_path = output_path / 'logs'
    log_path.mkdir(exist_ok=True)
    plots_path = output_path / 'plots'
    plots_path.mkdir(exist_ok=True)
    debug_visuals = args.debug
    show_graphs = args.visualize

    if not input_path.exists():
        print(f"Cannot locate payload path: {input_path}")
        exit(1)

    with open(input_path) as f:
        input_json = json.load(f)
        test_name = input_json.get('test_name', "NoNAME")
        if cmd_test_name != "":
            test_name = cmd_test_name
        max_stalled_metric = input_json.get('stalled_counter', MAX_STALLED_METRIC)

    tn = test_name.replace(' ', '-')
    tn = tn.replace('/', '-')
    copy_payload = output_path / f"{tn}_payload.json"
    ga_config = None
    if args.config:
        ga_config = Path('.') / args.config

    with open(log_path / f'{tn}.csv', 'w') as f:
        f.write(f"Random Seed: {args.seed}\n")

    io = InspectionOptimizer.from_file(input_path, ga_config)
    io.write_configuration(copy_payload)
    genetic_algorithm, problem_domain = io.create_project()
    # plot_pof_curves(io, plots_path, test_name)
    initial_individual: OBMIndividual = genetic_algorithm.problem_domain.create_initial_population(1)[0]
    # plot_tasks(initial_individual, io, plots_path, f"{test_name}_init_individual", show_graphs, io.start_date, io.time_frame)

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
        # print(stats[0].fronts[0][0].individual)
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

        if debug_visuals > 0 and stats[0].iteration % debug_visuals == 0:
            tn_iter = f"{tn}--{stats[0].iteration}"
            plot_combined_results(io, best.individual, plots_path, tn_iter, show_graphs, io.start_date, io.time_frame)

        # if stalled_metric>0 and stalled_metric % 50 == 0:  #   MAX_STALLED_METRIC / 2:
        #     problem_domain.scale_scope_parameter()
        #     print(f"Changing PD scope: {problem_domain.total_iterations}")

        if stalled_metric == MAX_STALLED_METRIC or stats[0].iteration == genetic_algorithm.number_of_generations - 1:
            # plot_optimized_curves(io, best.individual, plots_path, tn, show_graphs, io.start_date)
            # plot_tasks(best.individual, io, plots_path, tn, show_graphs, io.start_date, io.time_frame)
            output_task_spreadsheet(io, best.individual, plots_path, tn, io.start_date)
            plot_combined_results(io, best.individual, plots_path, tn, show_graphs, io.start_date, io.time_frame)
            break

    print(f"Run took {(time.time_ns() - start)/1e9} seconds")

