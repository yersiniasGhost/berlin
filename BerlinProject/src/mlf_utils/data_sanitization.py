"""
Data Sanitization Utilities
Provides utilities for sanitizing data structures for JSON serialization.
Handles NaN, Inf, and other non-JSON-compliant values.
"""

import math
from typing import Any, Union, Dict, List


def sanitize_nan_values(obj: Any) -> Any:
    """
    Recursively sanitize NaN and Inf values in a data structure for JSON compatibility.

    Converts NaN and Inf to None (null in JSON), and handles nested lists/dicts.
    This is essential for Flask jsonify() to work correctly with numerical data
    that may contain invalid floating point values.

    Args:
        obj: Data structure to sanitize (dict, list, float, or other types)

    Returns:
        Sanitized data structure with NaN/Inf values replaced by None

    Examples:
        >>> sanitize_nan_values({'a': float('nan'), 'b': 1.0})
        {'a': None, 'b': 1.0}

        >>> sanitize_nan_values([1.0, float('inf'), 2.0])
        [1.0, None, 2.0]

        >>> sanitize_nan_values({'nested': {'value': float('nan')}})
        {'nested': {'value': None}}
    """
    if isinstance(obj, dict):
        return {key: sanitize_nan_values(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_nan_values(item) for item in obj]
    elif isinstance(obj, float):
        # Check for NaN or Inf and convert to None
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    else:
        return obj


def sanitize_for_json(data: Any) -> Any:
    """
    Alias for sanitize_nan_values for clarity in JSON serialization contexts.

    Args:
        data: Data to sanitize for JSON serialization

    Returns:
        JSON-safe data structure
    """
    return sanitize_nan_values(data)
