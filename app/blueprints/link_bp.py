"""
Link API Blueprint

Handles bidirectional linking between content items.
Uses LinkService for all business logic.
"""
from flask import Blueprint, request, jsonify
from typing import Optional
import logging

from services.link_service import LinkService, LinkType
from app.utils.api import json_success_response, json_error_response

logger = logging.getLogger(__name__)

# Blueprint definition
link_bp = Blueprint('link', __name__, url_prefix='/api/links')

# Initialize service
def get_link_service():
    """Get LinkService instance"""
    return LinkService()


@link_bp.route('', methods=['GET'])
def list_links():
    """List all links with filtering"""
    try:
        service = get_link_service()

        # Get filters
        source_id = request.args.get('source_id')
        target_id = request.args.get('target_id')
        link_type = request.args.get('link_type')
        limit = request.args.get('limit', 100, type=int)

        # Use get_all() method instead of list_links()
        links = service.get_all(
            link_type=link_type,
            limit=limit
        )

        return json_success_response(links)

    except Exception as e:
        logger.error(f"Error listing links: {e}")
        return json_error_response(str(e), status_code=500)


@link_bp.route('', methods=['POST'])
def create_link():
    """Create a new link"""
    try:
        service = get_link_service()
        data = request.get_json()

        if not data or 'source_id' not in data or 'target_id' not in data:
            return json_error_response('source_id and target_id are required', status_code=400)

        if data['source_id'] == data['target_id']:
            return json_error_response('Cannot link to self', status_code=400)

        link = service.create(
            source_id=data['source_id'],
            target_id=data['target_id'],
            source_type=data.get('source_type', 'content'),
            target_type=data.get('target_type', 'content'),
            link_type=data.get('link_type', LinkType.RELATED),
            context=data.get('context'),
            strength=data.get('strength', 1.0)
        )

        return json_success_response(link, status_code=201)

    except Exception as e:
        logger.error(f"Error creating link: {e}")
        return json_error_response(str(e), status_code=500)


@link_bp.route('/<link_id>', methods=['DELETE'])
def delete_link(link_id: str):
    """Delete a link"""
    try:
        service = get_link_service()
        success = service.delete(link_id)

        if not success:
            return json_error_response('Link not found', 'NOT_FOUND', status_code=404)

        return json_success_response({'deleted': link_id})

    except Exception as e:
        logger.error(f"Error deleting link: {e}")
        return json_error_response(str(e), status_code=500)


@link_bp.route('/contents/<content_id>/links', methods=['GET'])
def get_content_links(content_id: str):
    """Get outbound links from content"""
    try:
        service = get_link_service()

        links = service.get_links_from(content_id)

        return json_success_response(links)

    except Exception as e:
        logger.error(f"Error getting content links: {e}")
        return json_error_response(str(e), status_code=500)


@link_bp.route('/contents/<content_id>/backlinks', methods=['GET'])
def get_backlinks(content_id: str):
    """Get backlinks to content"""
    try:
        service = get_link_service()

        links = service.get_links_to(content_id)

        return json_success_response(links)

    except Exception as e:
        logger.error(f"Error getting backlinks: {e}")
        return json_error_response(str(e), status_code=500)


@link_bp.route('/contents/<content_id>/related', methods=['GET'])
def get_related_content(content_id: str):
    """Get related content suggestions"""
    try:
        service = get_link_service()
        limit = request.args.get('limit', 10, type=int)

        related = service.get_related(content_id, limit=limit)

        return json_success_response(related)

    except Exception as e:
        logger.error(f"Error getting related content: {e}")
        return json_error_response(str(e), status_code=500)


@link_bp.route('/suggestions', methods=['GET'])
def get_link_suggestions():
    """Get link suggestions based on context"""
    try:
        service = get_link_service()

        content_id = request.args.get('content_id')
        limit = request.args.get('limit', 10, type=int)

        if not content_id:
            return json_error_response('content_id is required', status_code=400)

        suggestions = service.suggest_links(content_id, limit=limit)

        return json_success_response(suggestions)

    except Exception as e:
        logger.error(f"Error getting link suggestions: {e}")
        return json_error_response(str(e), status_code=500)
