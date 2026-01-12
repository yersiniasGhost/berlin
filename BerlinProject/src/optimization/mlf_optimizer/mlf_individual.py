import copy
import random
from mlf_utils.log_manager import LogManager
from optimization.genetic_optimizer.abstractions.individual_base import IndividualBase
from models.monitor_configuration import MonitorConfiguration



def choose_weights(monitor_config: MonitorConfiguration):
    """Initialize random weights for bars and condition thresholds"""
    for bar_name, bar_config in monitor_config.bars.items():
        if 'indicators' in bar_config:
            for indicator_name in bar_config['indicators']:
                w_range = bar_config.get('weight_ranges', {}).get(indicator_name, {})
                if not w_range:
                    raise ValueError("Invalid specification on bar indicator weight ranges")
                ranges = w_range.get('r')
                if not ranges:
                    raise ValueError("Invalid specification on bar indicator weight ranges")
                w_min = ranges[0]
                w_max = ranges[1]
                monitor_config.bars[bar_name]['indicators'][indicator_name] = random.uniform(w_min, w_max)

    # NEW: Randomize thresholds for enter_long array
    for enter_condition in monitor_config.enter_long:
        t_range = enter_condition.get('threshold_range')
        enter_condition['threshold'] = random.uniform(t_range[0], t_range[1])

    # NEW: Randomize thresholds for exit_long array
    for exit_condition in monitor_config.exit_long:
        t_range = exit_condition.get('threshold_range')
        exit_condition['threshold'] = random.uniform(t_range[0], t_range[1])


def choose_parameters(config: MonitorConfiguration):
    """Initialize random parameters for indicators"""
    logger = LogManager().get_logger('MlfIndividual')

    for indicator in config.indicators:
        logger.debug(f"🔍 Indicator '{indicator.name}': Initial parameters = {indicator.parameters}")
        logger.debug(f"🔍 Indicator '{indicator.name}': Ranges = {indicator.ranges}")

        # Check if ranges dict is empty or None
        if not indicator.ranges:
            logger.warning(f"⚠️  Indicator '{indicator.name}' has NO ranges defined - parameters won't be randomized!")
            continue

        for name, range_info in indicator.ranges.items():
            old_value = indicator.parameters.get(name, 'NOT_SET')
            new_value = None
            if range_info['t'] == 'int':
                new_value = random.randint(range_info['r'][0], range_info['r'][1])
            elif range_info['t'] == 'float':
                new_value = round(random.uniform(range_info['r'][0], range_info['r'][1]), 4)
            if new_value is not None:
                indicator.parameters[name] = new_value
                logger.debug(f"  ✅ {name}: {old_value} → {new_value} (range: {range_info['r']})")
            else:
                logger.warning(f"  ⚠️  {name}: Could not generate value for type '{range_info.get('t', 'UNKNOWN')}'")

        logger.debug(f"🎯 Indicator '{indicator.name}': Final parameters = {indicator.parameters}")


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