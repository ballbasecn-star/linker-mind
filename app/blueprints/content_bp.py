"""
Content API Blueprint

Handles content CRUD operations, search, and metadata.
Uses ContentService for all business logic.
"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from typing import Optional, Any
import logging
from datetime import datetime

from services.content_service import ContentService
from app.utils.api import json_success_response, json_error_response
from app.utils.pagination import get_pagination_params, Pagination

logger = logging.getLogger(__name__)

# Blueprint definition
content_bp = Blueprint('content', __name__)

# Initialize service
def get_content_service():
    """Get ContentService instance"""
    return ContentService()


# Page routes


@content_bp.route('/')
def index():
    """Home page / Dashboard"""
    try:
        service = get_content_service()

        # Get dashboard statistics
        stats = service.get_stats()

        # Get recent content
        items = service.get_recent(limit=10)

        # Calculate additional stats for display
        with_images = sum(1 for item in items if item.get('media', {}).get('images'))
        with_screenshots = sum(1 for item in items if item.get('media', {}).get('screenshots'))

        # Enhance stats with display counts
        enhanced_stats = {
            'total': stats.get('total', len(items)),
            'with_images': with_images,
            'with_screenshots': with_screenshots,
        }

        return render_template('index.html',
                            stats=enhanced_stats,
                            items=items)
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return render_template('index.html',
                            stats={'total': 0, 'with_images': 0, 'with_screenshots': 0},
                            items=[])


@content_bp.route('/dashboard')
def dashboard():
    """Legacy dashboard route - redirects to index"""
    return redirect('/')


@content_bp.route('/content/<content_id>')
def content_detail(content_id: str):
    """Content detail page"""
    try:
        service = get_content_service()
        content = service.get_content(content_id)

        if not content:
            return render_template('error.html', error='Content not found'), 404

        # Get notes for this content
        from database.db_interface import get_connection
        db = get_connection()
        notes = db.fetchall("""
            SELECT * FROM notes
            WHERE content_id = ?
            ORDER BY created_at DESC
        """, (content_id,))

        # Get links from this content
        outbound_links = db.fetchall("""
            SELECT * FROM links
            WHERE source_id = ?
            ORDER BY created_at DESC
            LIMIT 20
        """, (content_id,))

        # Get backlinks to this content
        backlinks = db.fetchall("""
            SELECT * FROM links
            WHERE target_id = ?
            ORDER BY created_at DESC
            LIMIT 20
        """, (content_id,))

        # Get associated nodes
        nodes = db.fetchall("""
            SELECT n.* FROM nodes n
            JOIN node_contents nc ON n.id = nc.node_id
            WHERE nc.content_id = ?
            ORDER BY n.node_type, n.name
        """, (content_id,))

        return render_template('detail.html',
                            item=content,
                            notes=[dict(row) for row in notes],
                            outbound_links=[dict(row) for row in outbound_links],
                            backlinks=[dict(row) for row in backlinks],
                            associated_nodes=[dict(row) for row in nodes])
    except Exception as e:
        logger.error(f"Error loading content detail: {e}")
        return f"<h1>Error</h1><p>{str(e)}</p>", 500


# API endpoints


@content_bp.route('/api/process', methods=['POST'])
def process_url():
    """Process a URL and save to database"""
    try:
        service = get_content_service()
        data = request.get_json()
        url = data.get('url')
        enable_ai = data.get('enable_ai', True)
        deep_analysis = data.get('deep_analysis', False)  # Enable deep video analysis

        if not url:
            return json_error_response('URL is required', status_code=400)

        content = service.create_from_url(url, enable_ai=enable_ai, deep_analysis=deep_analysis)

        if not content:
            return json_error_response('Failed to process URL', status_code=500)

        return json_success_response({
            'id': content['id'],
            'title': content['title'],
            'summary': content['summary'],
            'source_type': content['source_type'],
            'content_type': content['content_type'],
            'message': 'Content processed successfully',
            'deep_analysis_enabled': deep_analysis
        }, status_code=201)

    except Exception as e:
        logger.error(f"Error processing URL: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents', methods=['GET'])
def list_contents():
    """List all contents with pagination and filtering"""
    try:
        service = get_content_service()
        page, page_size = get_pagination_params(default_page_size=50)

        # Get filter parameters
        content_type = request.args.get('content_type')
        source_type = request.args.get('source_type')
        tag = request.args.get('tag')
        favorited = request.args.get('favorited')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'DESC')

        # Parse booleans
        favorited_bool = favorited and favorited.lower() == 'true'

        # Get contents
        contents = service.list_contents(
            content_type=content_type,
            source_type=source_type,
            tag=tag,
            favorited=favorited_bool,
            archived=False,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=page_size,
            offset=(page - 1) * page_size
        )

        # Get total count (simplified)
        all_contents = service.list_contents(
            content_type=content_type,
            source_type=source_type,
            tag=tag,
            favorited=favorited_bool,
            archived=False
        )
        total = len(all_contents)

        pagination = Pagination(total, page, page_size)

        return jsonify({
            'success': True,
            'data': contents,
            'pagination': pagination.to_dict()
        })

    except Exception as e:
        logger.error(f"Error listing contents: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents', methods=['POST'])
def create_content():
    """Create new content manually"""
    try:
        service = get_content_service()
        data = request.get_json()

        if not data:
            return json_error_response('No data provided', status_code=400)

        content = service.create(
            source_type=data.get('source_type', 'manual'),
            content_type=data.get('content_type', 'note'),
            url=data.get('url'),
            title=data.get('title', ''),
            raw_content=data.get('content', ''),
            summary=data.get('summary', ''),
            tags=data.get('tags')
        )

        return json_success_response(content, status_code=201)

    except Exception as e:
        logger.error(f"Error creating content: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents/<content_id>', methods=['GET'])
def get_content(content_id: str):
    """Get content by ID"""
    try:
        service = get_content_service()
        content = service.get_content(content_id)

        if not content:
            return json_error_response('Content not found', 'NOT_FOUND', status_code=404)

        return json_success_response(content)

    except Exception as e:
        logger.error(f"Error getting content: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents/<content_id>', methods=['PUT'])
def update_content(content_id: str):
    """Update content"""
    try:
        service = get_content_service()
        data = request.get_json()

        if not data:
            return json_error_response('No data provided', status_code=400)

        content = service.update(
            content_id=content_id,
            title=data.get('title'),
            summary=data.get('summary'),
            raw_content=data.get('content'),
            tags=data.get('tags'),
            favorited=data.get('favorited'),
            archived=data.get('archived'),
            reading_progress=data.get('reading_progress')
        )

        if not content:
            return json_error_response('Content not found', 'NOT_FOUND', status_code=404)

        return json_success_response(content)

    except Exception as e:
        logger.error(f"Error updating content: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents/<content_id>', methods=['DELETE'])
def delete_content(content_id: str):
    """Delete content"""
    try:
        service = get_content_service()
        success = service.delete(content_id)

        if not success:
            return json_error_response('Content not found', 'NOT_FOUND', status_code=404)

        return json_success_response({'deleted': content_id})

    except Exception as e:
        logger.error(f"Error deleting content: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents/<content_id>/favorite', methods=['POST'])
def toggle_favorite(content_id: str):
    """Toggle content favorite status"""
    try:
        service = get_content_service()
        content = service.toggle_favorite(content_id)

        if not content:
            return json_error_response('Content not found', 'NOT_FOUND', status_code=404)

        return json_success_response({
            'favorited': content.get('favorited', False),
            'message': 'Favorite status toggled'
        })

    except Exception as e:
        logger.error(f"Error toggling favorite: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents/<content_id>/archive', methods=['POST'])
def toggle_archive(content_id: str):
    """Toggle content archive status"""
    try:
        service = get_content_service()
        content = service.toggle_archive(content_id)

        if not content:
            return json_error_response('Content not found', 'NOT_FOUND', status_code=404)

        return json_success_response({
            'archived': content.get('archived', False),
            'message': 'Archive status toggled'
        })

    except Exception as e:
        logger.error(f"Error toggling archive: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents/<content_id>/reading-progress', methods=['PUT'])
def update_reading_progress(content_id: str):
    """Update reading progress"""
    try:
        service = get_content_service()
        data = request.get_json() or {}

        progress = data.get('progress', 0)
        if not isinstance(progress, (int, float)):
            return json_error_response('progress must be a number', status_code=400)

        content = service.update_reading_progress(content_id, int(progress))

        if not content:
            return json_error_response('Content not found', 'NOT_FOUND', status_code=404)

        return json_success_response({
            'reading_progress': content.get('reading_progress', 0),
            'message': 'Reading progress updated'
        })

    except Exception as e:
        logger.error(f"Error updating reading progress: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/search')
def search_contents():
    """Search contents"""
    try:
        service = get_content_service()
        query = request.args.get('q', '').strip()

        if not query:
            return json_error_response('Query parameter is required', status_code=400)

        # Get filters
        content_types = request.args.get('types')
        tags = request.args.get('tags')
        limit = request.args.get('limit', 20, type=int)

        # Parse filters
        type_list = content_types.split(',') if content_types else None
        tag_list = tags.split(',') if tags else None

        results = service.search(
            query=query,
            content_types=type_list,
            tags=tag_list,
            limit=limit
        )

        return json_success_response({
            'query': query,
            'results': results,
            'count': len(results)
        })

    except Exception as e:
        logger.error(f"Error searching contents: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents/batch', methods=['POST'])
def batch_operation():
    """Batch operation on multiple contents"""
    try:
        service = get_content_service()
        data = request.get_json()

        if not data or 'content_ids' not in data or 'operation' not in data:
            return json_error_response('content_ids and operation are required', status_code=400)

        content_ids = data['content_ids']
        operation = data['operation']

        if not isinstance(content_ids, list) or not content_ids:
            return json_error_response('content_ids must be a non-empty list', status_code=400)

        results = {
            'success': [],
            'failed': [],
            'operation': operation
        }

        for content_id in content_ids:
            try:
                if operation == 'delete':
                    if service.delete(content_id):
                        results['success'].append(content_id)
                    else:
                        results['failed'].append(content_id)
                elif operation == 'archive':
                    content = service.toggle_archive(content_id)
                    if content:
                        results['success'].append(content_id)
                    else:
                        results['failed'].append(content_id)
                elif operation == 'favorite':
                    content = service.toggle_favorite(content_id)
                    if content:
                        results['success'].append(content_id)
                    else:
                        results['failed'].append(content_id)
                else:
                    results['failed'].append(content_id)
            except Exception as e:
                logger.error(f"Error in batch operation for {content_id}: {e}")
                results['failed'].append(content_id)

        return json_success_response(results)

    except Exception as e:
        logger.error(f"Error in batch operation: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents/<content_id>/notes', methods=['GET'])
def get_content_notes(content_id: str):
    """Get all notes for a specific content"""
    try:
        from database.db_interface import get_connection
        db = get_connection()

        notes = db.fetchall("""
            SELECT * FROM notes
            WHERE content_id = ?
            ORDER BY created_at DESC
            LIMIT 100
        """, (content_id,))

        # Convert Row objects to dicts
        notes_list = [dict(row) for row in notes]

        return json_success_response(notes_list)

    except Exception as e:
        logger.error(f"Error getting notes: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents/<content_id>/notes', methods=['POST'])
def create_content_note(content_id: str):
    """Create a new note for content"""
    try:
        from database.db_interface import get_connection
        import uuid

        db = get_connection()
        data = request.get_json()

        if not data or not data.get('content'):
            return json_error_response('Note content is required', status_code=400)

        note_id = f"note_{uuid.uuid4().hex[:16]}"
        note_type = data.get('note_type', 'note')
        note_content = data.get('content')

        db.execute("""
            INSERT INTO notes (id, content_id, note_type, content, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (note_id, content_id, note_type, note_content, datetime.now(), datetime.now()))

        # Return the created note
        note = db.fetchone("""
            SELECT * FROM notes WHERE id = ?
        """, (note_id,))

        return json_success_response(dict(note), status_code=201)

    except Exception as e:
        logger.error(f"Error creating note: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/notes/<note_id>', methods=['DELETE'])
def delete_note(note_id: str):
    """Delete a note"""
    try:
        from database.db_interface import get_connection
        db = get_connection()

        db.execute("DELETE FROM notes WHERE id = ?", (note_id,))

        return json_success_response({'deleted': note_id})

    except Exception as e:
        logger.error(f"Error deleting note: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents/<content_id>/nodes', methods=['GET'])
def get_content_nodes(content_id: str):
    """Get all nodes associated with a content"""
    try:
        from database.db_interface import get_connection
        db = get_connection()

        nodes = db.fetchall("""
            SELECT n.* FROM nodes n
            JOIN node_contents nc ON n.id = nc.node_id
            WHERE nc.content_id = ?
            ORDER BY n.node_type, n.name
        """, (content_id,))

        nodes_list = [dict(row) for row in nodes]

        return json_success_response(nodes_list)

    except Exception as e:
        logger.error(f"Error getting content nodes: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents/<content_id>/nodes', methods=['POST'])
def add_content_to_node(content_id: str):
    """Add content to a node (project/area/resource)"""
    try:
        from database.db_interface import get_connection
        db = get_connection()
        data = request.get_json()

        if not data or 'node_id' not in data:
            return json_error_response('node_id is required', status_code=400)

        node_id = data['node_id']

        # Check if association already exists
        existing = db.fetchone("""
            SELECT * FROM node_contents
            WHERE node_id = ? AND content_id = ?
        """, (node_id, content_id))

        if existing:
            return json_success_response({'message': 'Already associated'})

        # Create association
        db.execute("""
            INSERT INTO node_contents (node_id, content_id, added_at)
            VALUES (?, ?, ?)
        """, (node_id, content_id, datetime.now()))

        return json_success_response({'added': True, 'node_id': node_id})

    except Exception as e:
        logger.error(f"Error adding content to node: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents/<content_id>/nodes/<node_id>', methods=['DELETE'])
def remove_content_from_node(content_id: str, node_id: str):
    """Remove content from a node"""
    try:
        from database.db_interface import get_connection
        db = get_connection()

        db.execute("""
            DELETE FROM node_contents
            WHERE node_id = ? AND content_id = ?
        """, (node_id, content_id))

        return json_success_response({'removed': True})

    except Exception as e:
        logger.error(f"Error removing content from node: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/stats')
def get_stats():
    """Get content statistics"""
    try:
        service = get_content_service()
        stats = service.get_stats()

        return json_success_response(stats)

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return json_error_response(str(e), status_code=500)


@content_bp.route('/api/contents/count', methods=['GET'])
def get_contents_count():
    """Get total count of contents"""
    try:
        service = get_content_service()
        
        # Get filters (optional)
        content_type = request.args.get('content_type')
        source_type = request.args.get('source_type')
        tag = request.args.get('tag')
        favorited = request.args.get('favorited')
        
        # Parse boolean
        favorited_bool = False
        if favorited and favorited.lower() == 'true':
            favorited_bool = True
        
        # Get all contents with filters
        contents = service.list_contents(
            content_type=content_type,
            source_type=source_type,
            tag=tag,
            favorited=favorited_bool,
            archived=False,
            sort_by='created_at',
            sort_order='DESC',
            limit=10000  # High limit to get count
        )
        
        return json_success_response(len(contents))
    except Exception as e:
        logger.error(f"Error getting contents count: {e}")
        return json_error_response(str(e), status_code=500)
