"""
Note API Blueprint

Handles notes and progressive summarization.
Uses NoteService for all business logic.
"""
from flask import Blueprint, request, jsonify, render_template
from typing import Optional
import logging

from services.note_service import NoteService, NoteType, SummaryLayer
from app.utils.api import json_success_response, json_error_response
from app.utils.pagination import get_pagination_params, Pagination

logger = logging.getLogger(__name__)

# Blueprint definition
note_bp = Blueprint('note', __name__, url_prefix='/api/notes')

# Initialize service (will use unified database interface)
def get_note_service():
    """Get NoteService instance"""
    return NoteService()


# API endpoints


@note_bp.route('', methods=['GET'])
def list_notes():
    """List all notes with filtering"""
    try:
        service = get_note_service()
        page, page_size = get_pagination_params()

        # Get filters
        content_id = request.args.get('content_id')
        node_id = request.args.get('node_id')
        note_type = request.args.get('note_type')
        summary_layer = request.args.get('summary_layer')

        # Calculate offset
        offset = (page - 1) * page_size

        # Get notes from service
        notes = service.list_notes(
            content_id=content_id,
            node_id=node_id,
            note_type=note_type,
            summary_layer=int(summary_layer) if summary_layer else None,
            limit=page_size,
            offset=offset
        )

        # Get total count (simplified - should be optimized in service)
        all_notes = service.list_notes(
            content_id=content_id,
            node_id=node_id,
            note_type=note_type,
            summary_layer=int(summary_layer) if summary_layer else None,
            limit=10000  # Large number to get total
        )
        total = len(all_notes)

        pagination = Pagination(total, page, page_size)

        return jsonify({
            'success': True,
            'data': notes,
            'pagination': pagination.to_dict()
        })

    except Exception as e:
        logger.error(f"Error listing notes: {e}")
        return json_error_response(str(e), status_code=500)


@note_bp.route('', methods=['POST'])
def create_note():
    """Create a new note"""
    try:
        service = get_note_service()
        data = request.get_json()

        if not data or not data.get('content'):
            return json_error_response('content is required', status_code=400)

        note = service.create_note(
            content=data['content'],
            content_id=data.get('content_id'),
            node_id=data.get('node_id'),
            note_type=data.get('note_type', NoteType.LEARNING),
            summary_layer=data.get('summary_layer', 0),
            highlights=data.get('highlights')
        )

        return json_success_response(note, status_code=201)

    except Exception as e:
        logger.error(f"Error creating note: {e}")
        return json_error_response(str(e), status_code=500)


@note_bp.route('/<note_id>', methods=['GET'])
def get_note(note_id: str):
    """Get a note by ID"""
    try:
        service = get_note_service()
        note = service.get_note(note_id)

        if not note:
            return json_error_response('Note not found', 'NOT_FOUND', status_code=404)

        return json_success_response(note)

    except Exception as e:
        logger.error(f"Error getting note: {e}")
        return json_error_response(str(e), status_code=500)


@note_bp.route('/<note_id>', methods=['PUT'])
def update_note(note_id: str):
    """Update a note"""
    try:
        service = get_note_service()
        data = request.get_json()

        if not data:
            return json_error_response('No data provided', status_code=400)

        note = service.update_note(
            note_id=note_id,
            content=data.get('content'),
            note_type=data.get('note_type'),
            summary_layer=data.get('summary_layer'),
            highlights=data.get('highlights')
        )

        if not note:
            return json_error_response('Note not found', 'NOT_FOUND', status_code=404)

        return json_success_response(note)

    except Exception as e:
        logger.error(f"Error updating note: {e}")
        return json_error_response(str(e), status_code=500)


@note_bp.route('/<note_id>', methods=['DELETE'])
def delete_note(note_id: str):
    """Delete a note"""
    try:
        service = get_note_service()
        success = service.delete_note(note_id)

        if not success:
            return json_error_response('Note not found', 'NOT_FOUND', status_code=404)

        return json_success_response({'deleted': note_id})

    except Exception as e:
        logger.error(f"Error deleting note: {e}")
        return json_error_response(str(e), status_code=500)


@note_bp.route('/contents/<content_id>/summary', methods=['GET'])
def get_content_summary(content_id: str):
    """Get progressive summary for content"""
    try:
        service = get_note_service()
        summary = service.get_content_summary(content_id)

        return json_success_response(summary)

    except Exception as e:
        logger.error(f"Error getting content summary: {e}")
        return json_error_response(str(e), status_code=500)


@note_bp.route('/contents/<content_id>/highlights', methods=['POST'])
def add_highlight(content_id: str):
    """Add highlight (Layer 1)"""
    try:
        service = get_note_service()
        data = request.get_json()

        if not data or not data.get('text'):
            return json_error_response('text is required', status_code=400)

        note = service.add_highlight(
            content_id=content_id,
            text=data['text'],
            color=data.get('color', 'yellow')
        )

        return json_success_response(note, status_code=201)

    except Exception as e:
        logger.error(f"Error adding highlight: {e}")
        return json_error_response(str(e), status_code=500)


@note_bp.route('/contents/<content_id>/bolded', methods=['POST'])
def add_bolded(content_id: str):
    """Add bolded text (Layer 2)"""
    try:
        service = get_note_service()
        data = request.get_json()

        if not data or not data.get('text'):
            return json_error_response('text is required', status_code=400)

        note = service.add_bolded(
            content_id=content_id,
            text=data['text']
        )

        return json_success_response(note, status_code=201)

    except Exception as e:
        logger.error(f"Error adding bolded: {e}")
        return json_error_response(str(e), status_code=500)


@note_bp.route('/contents/<content_id>/supernote', methods=['POST'])
def add_supernote(content_id: str):
    """Add supernote (Layer 3)"""
    try:
        service = get_note_service()
        data = request.get_json()

        if not data or not data.get('text'):
            return json_error_response('text is required', status_code=400)

        note = service.add_supernote(
            content_id=content_id,
            text=data['text']
        )

        return json_success_response(note, status_code=201)

    except Exception as e:
        logger.error(f"Error adding supernote: {e}")
        return json_error_response(str(e), status_code=500)


@note_bp.route('/contents/<content_id>/own-words', methods=['POST'])
def add_own_words(content_id: str):
    """Add own words summary (Layer 4)"""
    try:
        service = get_note_service()
        data = request.get_json()

        if not data or not data.get('text'):
            return json_error_response('text is required', status_code=400)

        note = service.add_own_words(
            content_id=content_id,
            text=data['text']
        )

        return json_success_response(note, status_code=201)

    except Exception as e:
        logger.error(f"Error adding own words: {e}")
        return json_error_response(str(e), status_code=500)


@note_bp.route('/contents/<content_id>/insight', methods=['POST'])
def add_insight(content_id: str):
    """Add insight (Layer 5)"""
    try:
        service = get_note_service()
        data = request.get_json()

        if not data or not data.get('text'):
            return json_error_response('text is required', status_code=400)

        note = service.add_insight(
            content_id=content_id,
            text=data['text']
        )

        return json_success_response(note, status_code=201)

    except Exception as e:
        logger.error(f"Error adding insight: {e}")
        return json_error_response(str(e), status_code=500)


@note_bp.route('/stats', methods=['GET'])
def get_note_stats():
    """Get note statistics"""
    try:
        service = get_note_service()
        stats = service.get_stats()

        return json_success_response(stats)

    except Exception as e:
        logger.error(f"Error getting note stats: {e}")
        return json_error_response(str(e), status_code=500)
