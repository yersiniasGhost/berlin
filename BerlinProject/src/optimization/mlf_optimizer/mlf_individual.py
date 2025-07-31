import copy
import random
from optimization.genetic_optimizer.abstractions.individual_base import IndividualBase
from models.monitor_configuration import MonitorConfiguration


def choose_weights(monitor_config: MonitorConfiguration):
    """Initialize random weights for bars and condition thresholds"""
    for bar_name, bar_config in monitor_config.bars.items():
        if 'indicators' in bar_config:
            for indicator_name in bar_config['indicators']:
                monitor_config.bars[bar_name]['indicators'][indicator_name] = random.randint(1, 100)

    # NEW: Randomize thresholds for enter_long array
    for enter_condition in monitor_config.enter_long:
        enter_condition['threshold'] = random.uniform(0.7, 0.9)

    # NEW: Randomize thresholds for exit_long array
    for exit_condition in monitor_config.exit_long:
        exit_condition['threshold'] = random.uniform(0.7, 0.9)


def choose_parameters(config: MonitorConfiguration):
    """Initialize random parameters for indicators"""
    for indicator in config.indicators:
        for name, range_info in indicator.ranges.items():
            new_value = None
            if range_info['t'] == 'int':
                new_value = random.randint(range_info['r'][0], range_info['r'][1])
            elif range_info['t'] == 'float':
                new_value = round(random.uniform(range_info['r'][0], range_info['r'][1]), 4)
            if new_value:
                indicator.parameters[name] = new_value


class MlfIndividual(IndividualBase):
    """Individual for genetic algorithm - uses only MonitorConfiguration"""

    def __init__(self, monitor_configuration: MonitorConfiguration, source: str = "NA"):
        super().__init__(source)
        self.monitor_configuration = monitor_configuration

    def __eq__(self, other):
        if not isinstance(other, MlfIndividual):
            return False
        return self.monitor_configuration == other.monitor_configuration

    @classmethod
    def create_itself(cls, monitor_config: MonitorConfiguration) -> "MlfIndividual":
        """Create a new individual with randomized weights and parameters"""
        new_config = copy.deepcopy(monitor_config)
        choose_weights(new_config)
        choose_parameters(new_config)
        return MlfIndividual(new_config, source="init")

    def copy_individual(self, source: str = "copy") -> "MlfIndividual":
        """Create a deep copy of this individual"""
        return MlfIndividual(
            monitor_configuration=copy.deepcopy(self.monitor_configuration),
            source=source
        )

    def __str__(self):
        return f"MlfIndividual: {self.monitor_configuration.name}"