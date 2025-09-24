import random
from dataclasses import dataclass
from typing import List, Dict

from optimization.genetic_optimizer.abstractions.problem_domain import ProblemDomain, IndividualBase
from .mlf_individual import MlfIndividual
from models.monitor_configuration import MonitorConfiguration
from models.monitor_model import Monitor


def get_random_int(delta: int):
    r = 0
    while r == 0:
        r = random.randint(-delta, delta)
    return r


@dataclass
class MlfProblem(ProblemDomain):
    monitor_configuration: MonitorConfiguration

    # monitor: Monitor

    def optimizer_results(self, best_individual: IndividualBase, metrics: List[float]):
        pass

    def create_initial_population(self, population_size: int) -> List[MlfIndividual]:
        individuals = []
        for i in range(population_size):
            # FIXED: Only pass monitor_configuration
            individuals.append(MlfIndividual.create_itself(self.monitor_configuration))
        return individuals

    def post_iteration_cleanup(self, iteration: str):
        pass

    def elitist_offspring(self, elite: MlfIndividual) -> MlfIndividual:
        ...

    def check_population(self, population: List[MlfIndividual]) -> bool:
        ...

    def cross_over_function(self, mom: MlfIndividual, dad: MlfIndividual, chance: float) -> List[MlfIndividual]:

        swap_cnt = 0

        while swap_cnt == 0:
            # This is used for crossing over the weights within the bars ("macd1m" :1.0)
            for bar_name in mom.monitor_configuration.bars.keys():
                moms_ind = mom.monitor_configuration.bars[bar_name]['indicators']  # e.g., {"macd1m": 1.5, "sma5m": 2.0}
                dads_ind = dad.monitor_configuration.bars[bar_name]['indicators']
                for indicator_name in moms_ind.keys():
                    if moms_ind[indicator_name] == dads_ind[indicator_name]:
                        continue
                    if random.random() < chance:
                        swap_cnt += 1
                        moms_ind[indicator_name], dads_ind[indicator_name] = dads_ind[indicator_name], moms_ind[
                            indicator_name]

            # indexing each name / threshold then switching values for them. FOR ENTER AND EXIT LONG THRESHOLDS
            for idx, enter_condition in enumerate(mom.monitor_configuration.enter_long):
                dad_enter_condition = dad.monitor_configuration.enter_long[idx]

                if enter_condition['threshold'] != dad_enter_condition['threshold']:
                    if random.random() < chance:
                        swap_cnt += 1
                        enter_condition['threshold'], dad_enter_condition['threshold'] = dad_enter_condition[
                            'threshold'], enter_condition['threshold']

            for idx, exit_condition in enumerate(mom.monitor_configuration.exit_long):
                dad_exit_condition = dad.monitor_configuration.exit_long[idx]

                if exit_condition['threshold'] != dad_exit_condition['threshold']:
                    if random.random() < chance:
                        swap_cnt += 1
                        exit_condition['threshold'], dad_exit_condition['threshold'] = dad_exit_condition['threshold'], \
                            exit_condition['threshold']

            # for crossover of indicator parameters.
            for idx, indicator in enumerate(mom.monitor_configuration.indicators):
                for key in indicator.parameters:
                    if random.random() < chance:
                        swap_cnt += 1
                        dad_indicator = dad.monitor_configuration.indicators[idx]
                        indicator.parameters[key], dad_indicator.parameters[key] = dad_indicator.parameters[key], \
                            indicator.parameters[key]

        return [mom, dad]

    # def mutation_function_old(self, individual: MlfIndividual, mutate_probability: float, iteration: int):
    #     cnt = 0
    #     percent_change = 0.2
    #     while cnt == 0:
    #         for indicator in individual.monitor_configuration.indicators:
    #             for name, range in indicator.ranges.items():
    #                 if range['t'] != 'skip':
    #                     if random.random() < mutate_probability:
    #                         cnt += 1
    #                         low, high = range['r']
    #                         delta = percent_change * (high - low)
    #                         value = indicator.parameters[name]
    #                         new_value = 0
    #                         if range['t'] == "int":
    #                             delta = int(delta)
    #                             new_value = value + get_random_int(delta)
    #                         elif range['t'] == 'float':
    #                             new_value = value + random.uniform(-delta, delta)
    #                         new_value = max(low, min(new_value, high))
    #                         indicator.parameters[name] = new_value
    #
    #         if random.random() < mutate_probability:
    #             cnt += 1
    #             delta = percent_change * (0.9 - 0.5)
    #             new_threshold = max(0.5, min(individual.monitor.threshold + random.uniform(-delta, delta), 0.9))
    #             individual.monitor.threshold = new_threshold
    #
    #         if random.random() < mutate_probability:
    #             cnt += 1
    #             delta = percent_change * (0.9 - 0.5)
    #             new_threshold = max(0.5, min(individual.monitor.bear_threshold + random.uniform(-delta, delta), 0.9))
    #             individual.monitor.bear_threshold = new_threshold
    #
    #         for name, trigger in individual.monitor.triggers.items():
    #             if random.random() < mutate_probability:
    #                 cnt += 1
    #                 individual.monitor.triggers[name] = max(1.0, trigger + get_random_int(15))
    #
    #         for name, trigger in individual.monitor.bear_triggers.items():
    #             if random.random() < mutate_probability:
    #                 cnt += 1
    #                 individual.monitor.bear_triggers[name] = max(1.0, trigger + get_random_int(15))
    #     individual.source += f", mutated: {cnt}, idx: {iteration}"

    def mutation_function(self, individual: MlfIndividual, mutate_probability: float, iteration: int):
        cnt = 0
        percent_change = 0.2

        while cnt == 0:
            # 1. Mutate bar indicator weights
            for bar_name in individual.monitor_configuration.bars.keys():
                bar_config = individual.monitor_configuration.bars[bar_name]
                for indicator_name in bar_config['indicators'].keys():
                    if random.random() < mutate_probability:
                        cnt += 1

                        current_weight = bar_config['indicators'][indicator_name]
                        delta = 0.15  #  percent_change * (10.0 - 0.1)  # Weight range is 0.1 to 3.0
                        new_weight = current_weight + random.uniform(-delta, delta)
                        new_weight = max(0.01, min(new_weight, 1.0))

                        bar_config['indicators'][indicator_name] = new_weight

            # 2. Mutate enter_long thresholds
            for enter_condition in individual.monitor_configuration.enter_long:
                if random.random() < mutate_probability:
                    cnt += 1

                    current_threshold = enter_condition['threshold']
                    delta = 0.1  #   percent_change * (1.0 - 0.0)  # Threshold range is 0.1 to 0.9
                    new_threshold = current_threshold + random.uniform(-delta, delta)
                    # new_threshold = max(0.0, min(new_threshold, 1.0))
                    new_threshold = max(0.4, min(new_threshold, 1.0))

                    enter_condition['threshold'] = new_threshold

            # 3. Mutate exit_long thresholds
            for exit_condition in individual.monitor_configuration.exit_long:
                if random.random() < mutate_probability:
                    cnt += 1

                    current_threshold = exit_condition['threshold']
                    delta = percent_change * (0.9 - 0.1)  # Threshold range is 0.1 to 0.9
                    new_threshold = current_threshold + random.uniform(-delta, delta)
                    new_threshold = max(0.5, min(new_threshold, 0.9))

                    exit_condition['threshold'] = new_threshold

            # 4. Mutate indicator parameters
            for indicator in individual.monitor_configuration.indicators:
                for name, range in indicator.ranges.items():
                    if range['t'] != 'skip':
                        if random.random() < mutate_probability:
                            cnt += 1
                            low, high = range['r']
                            delta = percent_change * (high - low)
                            value = indicator.parameters[name]
                            new_value = 0
                            if range['t'] == "int":
                                delta = int(delta)
                                new_value = value + get_random_int(delta)
                            elif range['t'] == 'float':
                                new_value = value + random.uniform(-delta, delta)
                            new_value = max(low, min(new_value, high))
                            indicator.parameters[name] = new_value
        individual.source += f", mutated: {cnt}, idx: {iteration}"
