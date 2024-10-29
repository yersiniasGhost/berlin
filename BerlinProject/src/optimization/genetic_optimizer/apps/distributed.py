import time
import argparse
from pathlib import Path
from subprocess import Popen, list2cmdline
import sys


def execute_commands(cmds, n_procs):
    def done(p):
        return p.poll() is not None

    def success(p):
        return p.returncode == 0

    max_task = n_procs
    processes = []
    cnt = 0
    while True:
        while cmds and len(processes) < max_task:
            task, log = cmds.pop()
            cnt += 1
            print(f"{cnt} / {len(processes)} :  {task}")
            with log.open('w') as f:
                processes.append(Popen(task, shell=True, stdout=f, stderr=f))

        for p in processes:
            if done(p):
                processes.remove(p)
                if not success(p):
                    print("Run failed:")
                    print(p.args)

        if not processes and not cmds:
            break
        else:
            time.sleep(2)


if __name__=="__main__":
    # Expect the following command line Arguments:
    # a) input path to payload
    # b) output path for results
    # any flags
    parser = argparse.ArgumentParser(description='Distribute Stage 2 Calculations')
    parser.add_argument('payload',  type=str, nargs='+',
                        help='Valid path to the input payloads')
    parser.add_argument('output', metavar='output', type=str, nargs='+',
                        help='Path to the output files')
    parser.add_argument('number_of_procs', metavar="Number of processes", type=int, nargs='+',
                        help="Provide number of processes to run")
    parser.add_argument('-o', '--overwrite', action='store_true', default=False,
                        help='Overwrite existing files if they exist')
    args = parser.parse_args()

    # ga_config = "/home/frich/devel/PINNACLE/GeneticOptimizer/src/apps/payloads/ga_config_short.json"
    ga_config = "/home/toadministrator/devel/GeneticOptimizer/src/apps/payloads/ga_config.json"
    payload = Path(args.payload[0])
    if not payload.exists():
        print(f"Cannot locate payload path: {payload}")
        exit(1)
    output_path = Path(args.output[0])
    output_path.mkdir(exist_ok=True, parents=True)
    log_path = output_path / 'logs'
    log_path.mkdir(exist_ok=True)

    stage2_ids = []
    for file in payload.glob('*.json'):
        stage2_ids.append(payload / file.name)

    print(f"\nFound {len(stage2_ids)} Components to process.")
    overwrite = "-o" if args.overwrite else ""
    number_of_procs = args.number_of_procs[0]
    print("Using processes: ", number_of_procs)
    cnt = 0
    total = len(stage2_ids)
    commands = []
    for payload_file in stage2_ids:
        log = log_path/f"log_{payload_file.stem}.txt"
        cmd = f"python -m apps.inspection_optimizer  {payload_file} -o {output_path} -g {ga_config} -s 42"
        commands.append((cmd, log))
    execute_commands(commands, number_of_procs)


