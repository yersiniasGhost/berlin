"""
Validation utilities for MonitorConfiguration using existing indicator validation infrastructure.
Leverages BaseIndicator._validate_parameters() and IndicatorRegistry.
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field

from models.indicator_definition import IndicatorDefinition
from models.monitor_configuration import MonitorConfiguration, TradeExecutorConfig
from indicator_triggers.indicator_base import IndicatorRegistry, IndicatorConfiguration, BaseIndicator


# Validation constants
VALID_TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '1d']
VALID_AGGREGATOR_TYPES = ['normal', 'heiken']


@dataclass
class ValidationError:
    """Represents a validation error"""
    field: str
    message: str
    value: Any = None


@dataclass
class ValidationWarning:
    """Represents a validation warning (non-blocking)"""
    field: str
    message: str
    value: Any = None


@dataclass
class ValidationResult:
    """Complete validation result with errors and warnings"""
    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, field: str, message: str, value: Any = None):
        """Add validation error"""
        self.errors.append(ValidationError(field, message, value))
        self.valid = False

    def add_warning(self, field: str, message: str, value: Any = None):
        """Add validation warning"""
        self.warnings.append(ValidationWarning(field, message, value))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'valid': self.valid,
            'errors': [
                {'field': e.field, 'message': e.message, 'value': e.value}
                for e in self.errors
            ],
            'warnings': [
                {'field': w.field, 'message': w.message, 'value': w.value}
                for w in self.warnings
            ],
            'details': self.details
        }


def validate_indicator_definition(
    indicator_def: IndicatorDefinition,
    index: int
) -> ValidationResult:
    """
    Validate an IndicatorDefinition using the BaseIndicator validation system.

    This leverages:
    - IndicatorRegistry to get the indicator class
    - BaseIndicator.get_parameter_specs() to get parameter specifications
    - BaseIndicator._validate_parameters() to validate parameter values
    """
    result = ValidationResult(valid=True)
    result.details = {
        'name': indicator_def.name,
        'type': indicator_def.type,
        'indicator_class': indicator_def.indicator_class,
        'index': index
    }

    # 1. Check if indicator_class is registered
    registry = IndicatorRegistry()
    try:
        indicator_class = registry.get_indicator_class(indicator_def.indicator_class)
    except ValueError as e:
        result.add_error(
            f'indicators[{index}].indicator_class',
            f"Unknown indicator class '{indicator_def.indicator_class}'. Must be registered in IndicatorRegistry.",
            indicator_def.indicator_class
        )
        return result

    # 2. Validate agg_config format if present
    if indicator_def.agg_config:
        parts = indicator_def.agg_config.split('-')
        if len(parts) != 2:
            result.add_error(
                f'indicators[{index}].agg_config',
                f"Invalid agg_config format '{indicator_def.agg_config}'. Must be 'timeframe-type' (e.g., '1m-normal')",
                indicator_def.agg_config
            )
        else:
            timeframe, agg_type = parts
            if timeframe not in VALID_TIMEFRAMES:
                result.add_error(
                    f'indicators[{index}].agg_config',
                    f"Invalid timeframe '{timeframe}'. Must be one of: {', '.join(VALID_TIMEFRAMES)}",
                    timeframe
                )
            if agg_type not in VALID_AGGREGATOR_TYPES:
                result.add_error(
                    f'indicators[{index}].agg_config',
                    f"Invalid aggregator type '{agg_type}'. Must be one of: {', '.join(VALID_AGGREGATOR_TYPES)}",
                    agg_type
                )

    # 3. Validate parameters using BaseIndicator's validation system
    if indicator_def.parameters:
        try:
            # Create IndicatorConfiguration for validation
            indicator_config = IndicatorConfiguration(
                indicator_name=indicator_class.name(),
                display_name=indicator_def.name,
                parameters=indicator_def.parameters,
                enabled=True
            )

            # Create indicator instance - this will call _validate_parameters() internally
            temp_indicator = indicator_class(config=indicator_config)

            # If we got here, parameters are valid
            result.details['parameters_validated'] = True
            result.details['parameter_count'] = len(indicator_def.parameters)

        except ValueError as e:
            # BaseIndicator._validate_parameters() raised an error
            result.add_error(
                f'indicators[{index}].parameters',
                f"Parameter validation failed: {str(e)}",
                indicator_def.parameters
            )
        except Exception as e:
            result.add_error(
                f'indicators[{index}].parameters',
                f"Unexpected error during parameter validation: {str(e)}",
                indicator_def.parameters
            )
    else:
        # No parameters provided - check if indicator requires any
        param_specs = indicator_class.get_parameter_specs()
        if param_specs:
            result.add_warning(
                f'indicators[{index}].parameters',
                f"No parameters provided. Indicator '{indicator_def.indicator_class}' has {len(param_specs)} configurable parameters. Default values will be used.",
                None
            )

    return result


def validate_trade_executor_config(
    trade_executor: TradeExecutorConfig
) -> ValidationResult:
    """Validate TradeExecutorConfig with comprehensive business logic checks"""
    result = ValidationResult(valid=True)
    result.details = {
        'default_position_size': trade_executor.default_position_size,
        'stop_loss_pct': trade_executor.stop_loss_pct,
        'take_profit_pct': trade_executor.take_profit_pct,
        'trailing_stop_loss': trade_executor.trailing_stop_loss
    }

    # 1. Position size validation
    if trade_executor.default_position_size <= 0:
        result.add_error(
            'trade_executor.default_position_size',
            f"Position size must be > 0, got {trade_executor.default_position_size}",
            trade_executor.default_position_size
        )

    # 2. Stop loss validation
    if not (0.0001 <= trade_executor.stop_loss_pct <= 1.0):
        result.add_error(
            'trade_executor.stop_loss_pct',
            f"Stop loss percentage must be between 0.01% (0.0001) and 100% (1.0), got {trade_executor.stop_loss_pct}",
            trade_executor.stop_loss_pct
        )

    # 3. Take profit validation
    if not (0.0001 <= trade_executor.take_profit_pct <= 1.0):
        result.add_error(
            'trade_executor.take_profit_pct',
            f"Take profit percentage must be between 0.01% (0.0001) and 100% (1.0), got {trade_executor.take_profit_pct}",
            trade_executor.take_profit_pct
        )

    # 4. Risk/reward ratio check (warning)
    if trade_executor.stop_loss_pct > 0 and trade_executor.take_profit_pct > 0:
        risk_reward_ratio = trade_executor.take_profit_pct / trade_executor.stop_loss_pct
        if risk_reward_ratio < 1.5:
            result.add_warning(
                'trade_executor',
                f"Low risk/reward ratio: {risk_reward_ratio:.2f}x. Take profit ({trade_executor.take_profit_pct:.2%}) should ideally be at least 1.5x stop loss ({trade_executor.stop_loss_pct:.2%})",
                risk_reward_ratio
            )

    # 5. Trailing stop validation if enabled
    if trade_executor.trailing_stop_loss:
        if trade_executor.trailing_stop_distance_pct <= 0:
            result.add_error(
                'trade_executor.trailing_stop_distance_pct',
                f"Trailing stop distance must be > 0 when trailing stop is enabled, got {trade_executor.trailing_stop_distance_pct}",
                trade_executor.trailing_stop_distance_pct
            )

        if trade_executor.trailing_stop_activation_pct < 0:
            result.add_error(
                'trade_executor.trailing_stop_activation_pct',
                f"Trailing stop activation must be >= 0, got {trade_executor.trailing_stop_activation_pct}",
                trade_executor.trailing_stop_activation_pct
            )

        # Logical check: activation should be less than take profit
        if trade_executor.trailing_stop_activation_pct >= trade_executor.take_profit_pct:
            result.add_warning(
                'trade_executor.trailing_stop_activation_pct',
                f"Trailing stop activation ({trade_executor.trailing_stop_activation_pct:.2%}) is >= take profit ({trade_executor.take_profit_pct:.2%}). Trailing stop may never activate.",
                trade_executor.trailing_stop_activation_pct
            )

    return result


def validate_entry_exit_conditions(
    monitor_config: MonitorConfiguration
) -> ValidationResult:
    """Validate entry and exit condition arrays"""
    result = ValidationResult(valid=True)

    # 1. Check that at least one entry condition exists
    if not monitor_config.enter_long or len(monitor_config.enter_long) == 0:
        result.add_error(
            'enter_long',
            "At least one entry condition (enter_long) must be defined",
            None
        )
    else:
        result.details['entry_conditions_count'] = len(monitor_config.enter_long)

        # Validate each entry condition structure
        for i, condition in enumerate(monitor_config.enter_long):
            if not isinstance(condition, dict):
                result.add_error(
                    f'enter_long[{i}]',
                    f"Entry condition must be a dictionary, got {type(condition)}",
                    condition
                )
            # TODO: Add more specific condition validation based on your condition structure

    # 2. Check that at least one exit condition exists
    if not monitor_config.exit_long or len(monitor_config.exit_long) == 0:
        result.add_error(
            'exit_long',
            "At least one exit condition (exit_long) must be defined",
            None
        )
    else:
        result.details['exit_conditions_count'] = len(monitor_config.exit_long)

        # Validate each exit condition structure
        for i, condition in enumerate(monitor_config.exit_long):
            if not isinstance(condition, dict):
                result.add_error(
                    f'exit_long[{i}]',
                    f"Exit condition must be a dictionary, got {type(condition)}",
                    condition
                )
            # TODO: Add more specific condition validation

    return result


def validate_bars_configuration(
    monitor_config: MonitorConfiguration
) -> ValidationResult:
    """Validate bars configuration and cross-references"""
    result = ValidationResult(valid=True)

    if monitor_config.bars:
        result.details['bars_count'] = len(monitor_config.bars)

        # Get all indicator names for validation
        indicator_names = [ind.name for ind in monitor_config.indicators]

        # Validate each bar definition
        for bar_name, bar_config in monitor_config.bars.items():
            if not isinstance(bar_config, dict):
                result.add_error(
                    f'bars.{bar_name}',
                    f"Bar configuration must be a dictionary, got {type(bar_config)}",
                    bar_config
                )
                continue

            # TODO: Add validation for indicator references in bars
            # Check that referenced indicators exist
            # This depends on your bar configuration structure
    else:
        result.details['bars_count'] = 0
        result.add_warning(
            'bars',
            "No bars configuration defined. Bars may be required for conditions to reference.",
            None
        )

    return result


def validate_monitor_configuration_comprehensive(
    monitor_config: MonitorConfiguration
) -> ValidationResult:
    """
    Comprehensive validation of entire MonitorConfiguration.
    This is the main entry point for validation.
    """
    result = ValidationResult(valid=True)
    result.details = {
        'name': monitor_config.name,
        'description': monitor_config.description
    }

    # 1. Validate indicators
    if not monitor_config.indicators or len(monitor_config.indicators) == 0:
        result.add_error(
            'indicators',
            "At least one indicator must be defined",
            None
        )
    else:
        indicators_results = []
        indicator_names = []

        for i, indicator in enumerate(monitor_config.indicators):
            ind_result = validate_indicator_definition(indicator, i)
            indicators_results.append(ind_result.to_dict())

            # Collect errors and warnings
            result.errors.extend(ind_result.errors)
            result.warnings.extend(ind_result.warnings)
            if not ind_result.valid:
                result.valid = False

            # Check for duplicate names
            if indicator.name in indicator_names:
                result.add_error(
                    f'indicators[{i}].name',
                    f"Duplicate indicator name '{indicator.name}'. Each indicator must have a unique name.",
                    indicator.name
                )
            indicator_names.append(indicator.name)

        result.details['indicators'] = {
            'count': len(monitor_config.indicators),
            'names': indicator_names,
            'validation_results': indicators_results
        }

    # 2. Validate trade executor
    te_result = validate_trade_executor_config(monitor_config.trade_executor)
    result.errors.extend(te_result.errors)
    result.warnings.extend(te_result.warnings)
    if not te_result.valid:
        result.valid = False
    result.details['trade_executor'] = te_result.details

    # 3. Validate entry/exit conditions
    conditions_result = validate_entry_exit_conditions(monitor_config)
    result.errors.extend(conditions_result.errors)
    result.warnings.extend(conditions_result.warnings)
    if not conditions_result.valid:
        result.valid = False
    result.details['conditions'] = conditions_result.details

    # 4. Validate bars configuration
    bars_result = validate_bars_configuration(monitor_config)
    result.errors.extend(bars_result.errors)
    result.warnings.extend(bars_result.warnings)
    if not bars_result.valid:
        result.valid = False
    result.details['bars'] = bars_result.details

    return result
