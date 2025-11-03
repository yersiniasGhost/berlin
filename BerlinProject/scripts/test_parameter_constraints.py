#!/usr/bin/env python3
"""
Test script for parameter constraint validation.

This script tests the parameter constraint validation functionality by:
1. Creating sample indicator definitions with parameter violations
2. Running constraint validation
3. Displaying the results
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from models.indicator_definition import IndicatorDefinition
from models.validation.parameter_constraints import (
    validate_and_constrain_monitor_config_parameters,
    format_constraint_warning_message
)


def test_parameter_constraints():
    """Test parameter constraint validation with various scenarios"""

    print("=" * 80)
    print("Parameter Constraint Validation Test")
    print("=" * 80)
    print()

    # Test Case 1: SMA with period exceeding maximum
    print("Test Case 1: SMA with period > max (500)")
    print("-" * 80)

    indicators_case1 = [
        IndicatorDefinition(
            name="sma_test_1",
            type="indicator",
            indicator_class="SMAIndicator",
            parameters={
                "period": 600,  # Exceeds typical max of 500
                "source": "close"
            },
            agg_config="1m-normal"
        )
    ]

    constrained_indicators_1, results_1 = validate_and_constrain_monitor_config_parameters(indicators_case1)

    if results_1:
        print(format_constraint_warning_message(results_1))
        print(f"Original period: {indicators_case1[0].parameters['period']}")
        print(f"Constrained period: {constrained_indicators_1[0].parameters['period']}")
    else:
        print("No constraints applied (indicator specs not found or no violations)")

    print()

    # Test Case 2: Multiple parameters with violations
    print("Test Case 2: RSI with period below minimum")
    print("-" * 80)

    indicators_case2 = [
        IndicatorDefinition(
            name="rsi_test_1",
            type="indicator",
            indicator_class="RSIIndicator",
            parameters={
                "period": 1,  # Below typical min of 2
                "overbought": 70,
                "oversold": 30
            },
            agg_config="5m-normal"
        )
    ]

    constrained_indicators_2, results_2 = validate_and_constrain_monitor_config_parameters(indicators_case2)

    if results_2:
        print(format_constraint_warning_message(results_2))
        print(f"Original period: {indicators_case2[0].parameters['period']}")
        print(f"Constrained period: {constrained_indicators_2[0].parameters['period']}")
    else:
        print("No constraints applied (indicator specs not found or no violations)")

    print()

    # Test Case 3: Multiple indicators with mixed violations
    print("Test Case 3: Multiple indicators with various violations")
    print("-" * 80)

    indicators_case3 = [
        IndicatorDefinition(
            name="sma_fast",
            type="indicator",
            indicator_class="SMAIndicator",
            parameters={
                "period": -5,  # Below minimum
                "source": "close"
            },
            agg_config="1m-normal"
        ),
        IndicatorDefinition(
            name="sma_slow",
            type="indicator",
            indicator_class="SMAIndicator",
            parameters={
                "period": 1000,  # Above maximum
                "source": "close"
            },
            agg_config="1m-normal"
        ),
        IndicatorDefinition(
            name="valid_sma",
            type="indicator",
            indicator_class="SMAIndicator",
            parameters={
                "period": 50,  # Valid value
                "source": "close"
            },
            agg_config="1m-normal"
        )
    ]

    constrained_indicators_3, results_3 = validate_and_constrain_monitor_config_parameters(indicators_case3)

    if results_3:
        print(format_constraint_warning_message(results_3))
        for i, (orig, constrained) in enumerate(zip(indicators_case3, constrained_indicators_3)):
            print(f"\nIndicator {i+1} ({orig.name}):")
            print(f"  Original period: {orig.parameters['period']}")
            print(f"  Constrained period: {constrained.parameters['period']}")
    else:
        print("No constraints applied (indicator specs not found or no violations)")

    print()
    print("=" * 80)
    print("Test Complete")
    print("=" * 80)


if __name__ == "__main__":
    test_parameter_constraints()
