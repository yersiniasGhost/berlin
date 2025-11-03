"""
Parameter constraint validation utilities for monitor configurations.

This module provides functions to validate and constrain parameter values
based on their defined ranges from indicator specifications.
"""

from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
import logging

from models.indicator_definition import IndicatorDefinition
from indicator_triggers.indicator_base import IndicatorRegistry, ParameterSpec, ParameterType

logger = logging.getLogger(__name__)


@dataclass
class ParameterConstraintResult:
    """Result of parameter constraint validation"""
    parameter_name: str
    indicator_name: str
    original_value: Any
    constrained_value: Any
    was_constrained: bool
    constraint_type: str  # 'min', 'max', or 'none'
    limit_value: Any = None


def constrain_parameter_to_spec(
    param_name: str,
    param_value: Any,
    param_spec: ParameterSpec,
    indicator_name: str
) -> ParameterConstraintResult:
    """
    Constrain a parameter value to its specification limits.

    Args:
        param_name: Name of the parameter
        param_value: Current value of the parameter
        param_spec: Parameter specification with min/max limits
        indicator_name: Name of the indicator (for logging)

    Returns:
        ParameterConstraintResult with original and constrained values
    """
    constrained_value = param_value
    was_constrained = False
    constraint_type = 'none'
    limit_value = None

    # Only constrain numeric types
    if param_spec.parameter_type in (ParameterType.INTEGER, ParameterType.FLOAT):
        # Check minimum constraint
        if param_spec.min_value is not None and param_value < param_spec.min_value:
            constrained_value = param_spec.min_value
            was_constrained = True
            constraint_type = 'min'
            limit_value = param_spec.min_value

        # Check maximum constraint
        elif param_spec.max_value is not None and param_value > param_spec.max_value:
            constrained_value = param_spec.max_value
            was_constrained = True
            constraint_type = 'max'
            limit_value = param_spec.max_value

    return ParameterConstraintResult(
        parameter_name=param_name,
        indicator_name=indicator_name,
        original_value=param_value,
        constrained_value=constrained_value,
        was_constrained=was_constrained,
        constraint_type=constraint_type,
        limit_value=limit_value
    )


def validate_and_constrain_indicator_parameters(
    indicator_def: IndicatorDefinition
) -> Tuple[Dict[str, Any], List[ParameterConstraintResult]]:
    """
    Validate and constrain all parameters of an indicator to their specification limits.

    This function:
    1. Retrieves the indicator's parameter specifications
    2. Compares current parameter values against min/max limits
    3. Constrains any values that violate limits
    4. Returns constrained parameters and a list of constraints applied

    Args:
        indicator_def: The indicator definition to validate

    Returns:
        Tuple of:
        - Dictionary of constrained parameters
        - List of ParameterConstraintResult objects for parameters that were constrained
    """
    registry = IndicatorRegistry()
    constraint_results = []

    # Get indicator class and parameter specs
    try:
        indicator_class = registry.get_indicator_class(indicator_def.indicator_class)
        param_specs = {spec.name: spec for spec in indicator_class.get_parameter_specs()}
    except (ValueError, AttributeError) as e:
        logger.warning(f"Could not load parameter specs for indicator '{indicator_def.indicator_class}': {e}")
        # If we can't get specs, return original parameters unchanged
        return indicator_def.parameters or {}, []

    # Start with original parameters
    constrained_params = dict(indicator_def.parameters) if indicator_def.parameters else {}

    # Validate and constrain each parameter
    for param_name, param_value in constrained_params.items():
        if param_name not in param_specs:
            logger.warning(f"Parameter '{param_name}' not found in specs for indicator '{indicator_def.name}'")
            continue

        param_spec = param_specs[param_name]
        result = constrain_parameter_to_spec(
            param_name=param_name,
            param_value=param_value,
            param_spec=param_spec,
            indicator_name=indicator_def.name
        )

        # Update parameter if it was constrained
        if result.was_constrained:
            constrained_params[param_name] = result.constrained_value
            constraint_results.append(result)
            logger.debug(
                f"Constrained parameter '{param_name}' in indicator '{indicator_def.name}': "
                f"{result.original_value} → {result.constrained_value} (limit: {result.limit_value})"
            )

    return constrained_params, constraint_results


def validate_and_constrain_monitor_config_parameters(
    indicators: List[IndicatorDefinition]
) -> Tuple[List[IndicatorDefinition], List[ParameterConstraintResult]]:
    """
    Validate and constrain parameters for all indicators in a monitor configuration.

    This is the main entry point for parameter constraint validation when loading
    a monitor configuration in the optimizer.

    Args:
        indicators: List of indicator definitions from monitor config

    Returns:
        Tuple of:
        - List of indicator definitions with constrained parameters
        - List of all ParameterConstraintResult objects (for warning messages)
    """
    all_constraint_results = []
    constrained_indicators = []

    for indicator_def in indicators:
        # Validate and constrain this indicator's parameters
        constrained_params, constraint_results = validate_and_constrain_indicator_parameters(
            indicator_def
        )

        # Create new indicator definition with constrained parameters
        constrained_indicator = IndicatorDefinition(
            name=indicator_def.name,
            type=indicator_def.type,
            indicator_class=indicator_def.indicator_class,
            parameters=constrained_params,
            ranges=indicator_def.ranges,
            description=indicator_def.description,
            agg_config=indicator_def.agg_config,
            calc_on_pip=indicator_def.calc_on_pip
        )

        constrained_indicators.append(constrained_indicator)
        all_constraint_results.extend(constraint_results)

    return constrained_indicators, all_constraint_results


def format_constraint_warning_message(
    constraint_results: List[ParameterConstraintResult]
) -> str:
    """
    Format a user-friendly warning message about constrained parameters.

    Args:
        constraint_results: List of parameters that were constrained

    Returns:
        Formatted warning message string
    """
    if not constraint_results:
        return ""

    # Group by indicator
    by_indicator: Dict[str, List[ParameterConstraintResult]] = {}
    for result in constraint_results:
        if result.indicator_name not in by_indicator:
            by_indicator[result.indicator_name] = []
        by_indicator[result.indicator_name].append(result)

    # Build message
    total_constrained = len(constraint_results)
    lines = [
        f"⚠️  Parameter Constraint Warning: {total_constrained} parameter(s) were constrained to their defined limits:",
        ""
    ]

    for indicator_name, results in by_indicator.items():
        lines.append(f"  Indicator '{indicator_name}':")
        for result in results:
            constraint_desc = f"{result.constraint_type}imum" if result.constraint_type in ('min', 'max') else ''
            lines.append(
                f"    • {result.parameter_name}: {result.original_value} → {result.constrained_value} "
                f"({constraint_desc} limit: {result.limit_value})"
            )
        lines.append("")

    return "\n".join(lines)
