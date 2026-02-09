"""
Search API Blueprint

Handles enhanced search across all content types.
Uses EnhancedSearchService for all business logic.
"""
from flask import Blueprint, request, jsonify
from typing import Optional
import logging

from services.search_service import EnhancedSearchService
from app.utils.api import json_success_response, json_error_response

logger = logging.getLogger(__name__)

# Blueprint definition
search_bp = Blueprint('search', __name__, url_prefix='/api/search')

# Initialize service
def get_search_service():
    """Get EnhancedSearchService instance"""
    return EnhancedSearchService()


@search_bp.route('', methods=['GET'])
def search():
    """
    Unified search endpoint

    Query parameters:
    - q: search query (required)
    - types: comma-separated list of content types (optional)
    - tags: comma-separated list of tags (optional)
    - date_from: start date (optional)
    - date_to: end date (optional)
    - min_quality: minimum quality score (optional)
    - favorited: only favorited (optional)
    - sort_by: sort field (relevance, date, quality) (optional)
    - page: page number (default: 1)
    - page_size: items per page (default: 20)
    """
    try:
        service = get_search_service()
        query = request.args.get('q', '').strip()

        if not query:
            return json_error_response('Query parameter is required', status_code=400)

        # Build search query object
        from services.search_service import SearchQuery, SortType

        search_query = SearchQuery(
            query=query,
            content_types=request.args.get('types', '').split(',') if request.args.get('types') else None,
            tags=request.args.get('tags', '').split(',') if request.args.get('tags') else None,
            date_from=request.args.get('date_from'),
            date_to=request.args.get('date_to'),
            min_quality=request.args.get('min_quality', type=float) if request.args.get('min_quality') else None,
            only_favorited=request.args.get('favorited', '').lower() == 'true',
            sort_by=SortType.RELEVANCE,
            page=request.args.get('page', 1, type=int),
            page_size=request.args.get('page_size', 20, type=int)
        )

        results = service.search(search_query)

        return jsonify({
            'success': True,
            'data': results.items,
            'pagination': results.pagination.to_dict(),
            'query': query
        })

    except Exception as e:
        logger.error(f"Error in search: {e}")
        return json_error_response(str(e), status_code=500)


@search_bp.route('/suggestions', methods=['GET'])
def get_search_suggestions():
    """Get search suggestions based on query"""
    try:
        service = get_search_service()
        query = request.args.get('q', '').strip().lower()

        if not query or len(query) < 2:
            return json_success_response([])

        suggestions = service.get_suggestions(query)

        return json_success_response(suggestions[:10])

    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        return json_error_response(str(e), status_code=500)


@search_bp.route('/facets', methods=['GET'])
def get_search_facets():
    """Get facet information for search"""
    try:
        service = get_search_service()
        query = request.args.get('q', '')

        facets = service.get_facets(query)

        return json_success_response({
            'content_types': facets.content_types,
            'tags': facets.tags,
            'source_types': facets.source_types,
            'date_range': {
                'min': facets.date_range_min,
                'max': facets.date_range_max
            },
            'total_results': facets.total_results
        })

    except Exception as e:
        logger.error(f"Error getting facets: {e}")
        return json_error_response(str(e), status_code=500)


@search_bp.route('/advanced', methods=['POST'])
def advanced_search():
    """
    Advanced search with complex filters

    Request body:
    {
        "query": "search text",
        "filters": {
            "content_types": ["article", "video"],
            "tags": ["python", "tutorial"],
            "date_range": {"from": "2024-01-01", "to": "2024-12-31"},
            "min_quality": 7.0,
            "favorited": true,
            "has_notes": true
        },
        "sort": {"field": "date", "order": "desc"},
        "page": 1,
        "page_size": 20
    }
    """
    try:
        service = get_search_service()
        data = request.get_json()

        if not data:
            return json_error_response('Request body is required', status_code=400)

        from services.search_service import SearchQuery, SortType

        search_query = SearchQuery(
            query=data.get('query', ''),
            content_types=data.get('filters', {}).get('content_types'),
            tags=data.get('filters', {}).get('tags'),
            date_from=data.get('filters', {}).get('date_range', {}).get('from'),
            date_to=data.get('filters', {}).get('date_range', {}).get('to'),
            min_quality=data.get('filters', {}).get('min_quality'),
            only_favorited=data.get('filters', {}).get('favorited', False),
            only_with_notes=data.get('filters', {}).get('has_notes', False),
            sort_by=SortType.DATE,
            page=data.get('page', 1),
            page_size=data.get('page_size', 20)
        )

        results = service.search(search_query)

        return jsonify({
            'success': True,
            'data': results.items,
            'pagination': results.pagination.to_dict()
        })

    except Exception as e:
        logger.error(f"Error in advanced search: {e}")
        return json_error_response(str(e), status_code=500)
