import copy
import random
from mlf_utils.log_manager import LogManager
from optimization.genetic_optimizer.abstractions.individual_base import IndividualBase
from models.monitor_configuration import MonitorConfiguration



def choose_weights(monitor_config: MonitorConfiguration):
    """Initialize random weights for bars, condition thresholds, and trend indicators"""
    for bar_name, bar_config in monitor_config.bars.items():
        # Randomize signal indicator weights
        if 'indicators' in bar_config:
            for indicator_name in bar_config['indicators']:
                w_range = bar_config.get('weight_ranges', {}).get(indicator_name, {})

                # Skip if marked as 'skip' (not being optimized) - keep existing weight value
                if w_range.get('t') == 'skip':
                    continue

                if not w_range:
                    raise ValueError(f"Invalid specification on bar indicator weight ranges for '{indicator_name}'")
                ranges = w_range.get('r')
                if not ranges:
                    raise ValueError(f"Invalid specification on bar indicator weight ranges for '{indicator_name}'")
                w_min = ranges[0]
                w_max = ranges[1]
                monitor_config.bars[bar_name]['indicators'][indicator_name] = random.uniform(w_min, w_max)

        # Randomize trend indicator weights
        if 'trend_indicators' in bar_config:
            trend_weight_ranges = bar_config.get('trend_weight_ranges', {})
            for trend_name, trend_config in bar_config['trend_indicators'].items():
                tw_range = trend_weight_ranges.get(trend_name, {})

                # Skip if marked as 'skip' (not being optimized)
                if tw_range.get('t') == 'skip':
                    continue

                # Skip if no range specified (not being optimized)
                if not tw_range or not tw_range.get('r'):
                    continue

                ranges = tw_range['r']
                new_weight = random.uniform(ranges[0], ranges[1])

                # Update weight in trend_indicators config
                if isinstance(trend_config, dict):
                    monitor_config.bars[bar_name]['trend_indicators'][trend_name]['weight'] = new_weight
                else:
                    # Simple weight format - convert to dict format
                    mode = 'soft'  # Default mode
                    monitor_config.bars[bar_name]['trend_indicators'][trend_name] = {
                        'weight': new_weight,
                        'mode': mode
                    }

        # Randomize trend threshold (gate threshold for this bar)
        tt_range = bar_config.get('trend_threshold_range')
        if tt_range:  # Only randomize if range exists (not None/skipped)
            monitor_config.bars[bar_name]['trend_threshold'] = random.uniform(tt_range[0], tt_range[1])

    # Randomize thresholds for enter_long array (skip if threshold_range is None)
    for enter_condition in monitor_config.enter_long:
        t_range = enter_condition.get('threshold_range')
        if t_range:  # Only randomize if range exists (not None/skipped)
            enter_condition['threshold'] = random.uniform(t_range[0], t_range[1])

    # Randomize thresholds for exit_long array (skip if threshold_range is None)
    for exit_condition in monitor_config.exit_long:
        t_range = exit_condition.get('threshold_range')
        if t_range:  # Only randomize if range exists (not None/skipped)
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