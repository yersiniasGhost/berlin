"""
Standardized Error Handling for Flask API Responses
Provides consistent error response formatting and custom exception classes.
"""

from typing import Dict, Any, List, Optional, Tuple
from flask import jsonify
from mlf_utils.log_manager import LogManager

logger = LogManager().get_logger("ErrorHandlers")


class APIError(Exception):
    """
    Base exception for API errors with structured error information.

    Provides consistent error handling across all API endpoints with
    proper HTTP status codes and error details.
    """

    def __init__(
        self,
        message: str,
        code: str = 'API_ERROR',
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize API error.

        Args:
            message: Human-readable error message
            code: Machine-readable error code (e.g., 'VALIDATION_ERROR')
            status_code: HTTP status code (default: 500)
            details: Additional error details dictionary
        """
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(APIError):
    """Exception for validation errors (HTTP 400)."""

    def __init__(self, message: str, validation_errors: Optional[List[str]] = None):
        """
        Initialize validation error.

        Args:
            message: Main error message
            validation_errors: List of specific validation error messages
        """
        super().__init__(
            message=message,
            code='VALIDATION_ERROR',
            status_code=400,
            details={'validation_errors': validation_errors or []}
        )


class NotFoundError(APIError):
    """Exception for resource not found errors (HTTP 404)."""

    def __init__(self, message: str, resource_type: Optional[str] = None):
        """
        Initialize not found error.

        Args:
            message: Error message
            resource_type: Type of resource that was not found
        """
        details = {}
        if resource_type:
            details['resource_type'] = resource_type

        super().__init__(
            message=message,
            code='NOT_FOUND',
            status_code=404,
            details=details
        )


class ConfigurationError(APIError):
    """Exception for configuration errors (HTTP 400)."""

    def __init__(self, message: str, config_errors: Optional[List[str]] = None):
        """
        Initialize configuration error.

        Args:
            message: Main error message
            config_errors: List of specific configuration issues
        """
        super().__init__(
            message=message,
            code='CONFIGURATION_ERROR',
            status_code=400,
            details={'config_errors': config_errors or []}
        )


class ProcessingError(APIError):
    """Exception for data processing errors (HTTP 500)."""

    def __init__(self, message: str, processing_stage: Optional[str] = None):
        """
        Initialize processing error.

        Args:
            message: Error message
            processing_stage: Stage where processing failed
        """
        details = {}
        if processing_stage:
            details['processing_stage'] = processing_stage

        super().__init__(
            message=message,
            code='PROCESSING_ERROR',
            status_code=500,
            details=details
        )


def create_error_response(error: Exception, log_error: bool = True) -> Tuple[Any, int]:
    """
    Create standardized JSON error response from exception.

    Args:
        error: Exception to convert to response
        log_error: Whether to log the error (default: True)

    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    if isinstance(error, APIError):
        # Structured API error with all details
        response = {
            'success': False,
            'error': {
                'message': error.message,
                'code': error.code,
                **error.details
            }
        }

        if log_error and error.status_code >= 500:
            logger.error(f"API Error ({error.code}): {error.message}", exc_info=True)
        elif log_error:
            logger.warning(f"API Error ({error.code}): {error.message}")

        return jsonify(response), error.status_code

    # Generic unexpected error
    error_message = str(error)
    response = {
        'success': False,
        'error': {
            'message': error_message,
            'code': 'INTERNAL_ERROR'
        }
    }

    if log_error:
        logger.error(f"Unexpected error: {error_message}", exc_info=True)

    return jsonify(response), 500


def create_success_response(
    data: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    status_code: int = 200
) -> Tuple[Any, int]:
    """
    Create standardized JSON success response.

    Args:
        data: Response data dictionary
        message: Optional success message
        status_code: HTTP status code (default: 200)

    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    response = {
        'success': True
    }

    if data is not None:
        response.update(data)

    if message:
        response['message'] = message

    return jsonify(response), status_code


def handle_validation_error(validation_errors: List[str]) -> Tuple[Any, int]:
    """
    Create validation error response from list of validation errors.

    Args:
        validation_errors: List of validation error messages

    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    error = ValidationError(
        message='Validation failed',
        validation_errors=validation_errors
    )
    return create_error_response(error)


def handle_not_found(resource: str, identifier: Optional[str] = None) -> Tuple[Any, int]:
    """
    Create not found error response.

    Args:
        resource: Type of resource that was not found
        identifier: Optional identifier of the resource

    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    if identifier:
        message = f'{resource} not found: {identifier}'
    else:
        message = f'{resource} not found'

    error = NotFoundError(message=message, resource_type=resource)
    return create_error_response(error)


def handle_missing_parameter(parameter_name: str) -> Tuple[Any, int]:
    """
    Create error response for missing required parameter.

    Args:
        parameter_name: Name of the missing parameter

    Returns:
        Tuple of (jsonify response, HTTP status code)
    """
    error = ValidationError(
        message=f'Missing required parameter: {parameter_name}',
        validation_errors=[f'{parameter_name} is required']
    )
    return create_error_response(error)
