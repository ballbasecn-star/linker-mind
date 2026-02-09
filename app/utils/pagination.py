"""
Pagination utilities
"""

from typing import Any, Dict, List, Tuple
from flask import request


class Pagination:
    """
    Pagination helper class.

    Args:
        total: Total number of items
        page: Current page number (1-indexed)
        page_size: Number of items per page
    """

    def __init__(self, total: int, page: int = 1, page_size: int = 20):
        self.total = total
        self.page = max(1, page)
        self.page_size = max(1, min(page_size, 100))  # Max 100 per page
        self.total_pages = (total + self.page_size - 1) // self.page_size if total > 0 else 0

    @property
    def has_next(self) -> bool:
        """Check if there is a next page."""
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        """Check if there is a previous page."""
        return self.page > 1

    @property
    def offset(self) -> int:
        """Get SQL offset for current page."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get SQL limit for current page."""
        return self.page_size

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            'total': self.total,
            'page': self.page,
            'page_size': self.page_size,
            'total_pages': self.total_pages,
            'has_next': self.has_next,
            'has_prev': self.has_prev,
        }

    def slice(self, items: List[Any]) -> List[Any]:
        """Slice a list according to pagination."""
        start = self.offset
        end = start + self.page_size
        return items[start:end]


def paginate_query(total: int, page: int = None, page_size: int = None) -> Pagination:
    """
    Create Pagination from request args or defaults.

    Args:
        total: Total number of items
        page: Current page (defaults to request.args.get('page'))
        page_size: Items per page (defaults to request.args.get('page_size'))

    Returns:
        Pagination object
    """
    if page is None:
        page = request.args.get('page', 1, type=int)

    if page_size is None:
        page_size = request.args.get('page_size', 20, type=int)

    return Pagination(total, page, page_size)


def get_pagination_params(default_page: int = 1, default_page_size: int = 20) -> Tuple[int, int]:
    """
    Get pagination parameters from request.

    Args:
        default_page: Default page number
        default_page_size: Default items per page

    Returns:
        Tuple of (page, page_size)
    """
    page = request.args.get('page', default_page, type=int)
    page_size = request.args.get('page_size', default_page_size, type=int)

    return max(1, page), max(1, min(page_size, 100))
