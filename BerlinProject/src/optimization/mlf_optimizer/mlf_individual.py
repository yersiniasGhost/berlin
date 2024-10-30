import copy
import random
from optimization.genetic_optimizer.abstractions.individual_base import IndividualBase
from models.monitor_configuration import MonitorConfiguration
from models.monitor_model import Monitor


def choose_weights(monitor: Monitor):
    monitor.triggers = {key: random.randint(1, 100) for key in monitor.triggers}


def choose_parameters(config: MonitorConfiguration):
    for indicator in config.indicators:
        for name, range in indicator.ranges.items():
            new_value = None
            if range['t'] == 'int':
                new_value = random.randint(range['r'][0], range['r'][1])
            elif range['t'] == 'float':
                new_value = round(random.uniform(range['r'][0], range['r'][1]), 4)
            if new_value:
                indicator.parameters[name] = new_value


# The definition of the optimization individual
class MlfIndividual(IndividualBase):

    def __init__(self, monitor_configuration: MonitorConfiguration,  monitor: Monitor ):
        self.monitor = monitor
        self.monitor_configuration = monitor_configuration


    @classmethod
    def create_itself(cls, monitor: Monitor,  monitor_configuration: MonitorConfiguration) -> "MlfIndividual":
        new_monitor = copy.deepcopy(monitor)
        choose_weights(new_monitor)
        new_config = copy.deepcopy(monitor_configuration)
        choose_parameters(new_config)
        return MlfIndividual(new_config, monitor=new_monitor)


    '''
    Iterate through the Indicator definitions and apply mutations to their 
    '''
    def mutate_function(self, mutate_probability: float):
        pass

    def copy_individual(self) -> "MlfIndividual":
        return MlfIndividual(monitor=self.monitor, monitor_configuration=self.monitor_configuration )

    def __str__(self):
        out = f"MlfIndividual: {self.monitor}"
        return out

