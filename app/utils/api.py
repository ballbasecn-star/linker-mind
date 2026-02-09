"""
API response utilities
"""

from typing import Any, Dict, List, Optional
from flask import jsonify


def success_response(data: Any = None, meta: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Create a standard success response.

    Args:
        data: Response data
        meta: Optional metadata

    Returns:
        Dictionary with success=True and data
    """
    response = {'success': True}

    if data is not None:
        response['data'] = data

    if meta:
        response['meta'] = meta

    return response


def error_response(message: str, error: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a standard error response.

    Args:
        message: Human-readable error message
        error: Optional error code/type

    Returns:
        Dictionary with success=False and error details
    """
    response = {
        'success': False,
        'error': error or 'Error',
        'message': message
    }

    return response


def json_success_response(data: Any = None, meta: Optional[Dict] = None, status_code: int = 200):
    """
    Create a JSON success response for Flask routes.

    Args:
        data: Response data
        meta: Optional metadata
        status_code: HTTP status code

    Returns:
        Flask JSON response
    """
    return jsonify(success_response(data, meta)), status_code


def json_error_response(message: str, error: Optional[str] = None, status_code: int = 400):
    """
    Create a JSON error response for Flask routes.

    Args:
        message: Human-readable error message
        error: Optional error code/type
        status_code: HTTP status code

    Returns:
        Flask JSON response
    """
    return jsonify(error_response(message, error)), status_code


def paginated_response(items: List[Any], pagination: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a paginated response.

    Args:
        items: List of items for current page
        pagination: Pagination metadata

    Returns:
        Dictionary with items and pagination info
    """
    return {
        'success': True,
        'data': items,
        'pagination': pagination
    }
