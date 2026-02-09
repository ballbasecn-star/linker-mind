"""
Inbox API Blueprint

Handles quick capture workflow (CODE: Capture, Organize, Distill, Express).
Uses InboxService for all business logic.
"""
from flask import Blueprint, request, jsonify, render_template
from typing import Optional
import logging

from services.inbox_service import InboxService, InboxStatus, ProcessAction
from app.utils.api import json_success_response, json_error_response

logger = logging.getLogger(__name__)

# Blueprint definition
inbox_bp = Blueprint('inbox', __name__)

# Get database connection
def get_inbox_service():
    """Get InboxService instance with current db connection"""
    return InboxService()


# Page routes


@inbox_bp.route('/inbox')
def inbox_page():
    """Inbox page"""
    try:
        # Get unprocessed items (with error handling for missing tables)
        try:
            unprocessed = get_inbox_service().get_unprocessed(include_snoozed=False, limit=50)
        except Exception as e:
            logger.warning(f"Inbox table may not exist: {e}")
            unprocessed = []

        # Get stats
        try:
            stats = get_inbox_service().get_stats()
        except Exception as e:
            logger.warning(f"Could not get inbox stats: {e}")
            stats = {'pending': 0, 'snoozed': 0, 'processed': 0}

        # Get snoozed items
        try:
            snoozed = get_inbox_service().get_by_status(InboxStatus.SNOOZED, limit=20)
        except:
            snoozed = []

        # Get processed items
        try:
            processed = get_inbox_service().get_by_status(InboxStatus.PROCESSED, limit=20)
        except:
            processed = []

        return render_template('inbox.html',
                            unprocessed=unprocessed,
                            snoozed=snoozed,
                            processed=processed,
                            stats=stats)
    except Exception as e:
        logger.error(f"Error loading inbox page: {e}")
        return render_template('index.html')


# API endpoints


@inbox_bp.route('/api/inbox', methods=['GET'])
def list_inbox():
    """List inbox items"""
    try:
        service = get_inbox_service()

        status = request.args.get('status', 'pending').lower()
        include_snoozed = request.args.get('include_snoozed', 'false').lower() == 'true'
        limit = request.args.get('limit', 50, type=int)

        if status == 'pending':
            items = service.get_unprocessed(include_snoozed=include_snoozed, limit=limit)
        elif status == 'snoozed':
            items = service.get_by_status(InboxStatus.SNOOZED, limit=limit)
        elif status == 'processed':
            items = service.get_by_status(InboxStatus.PROCESSED, limit=limit)
        elif status == 'overdue':
            items = service.get_overdue(limit=limit)
        elif status == 'queue':
            items = service.get_processing_queue(limit=limit)
        else:
            # All items
            items = service.get_all(limit=limit)

        return json_success_response([item.__dict__ for item in items])

    except Exception as e:
        logger.error(f"Error listing inbox: {e}")
        return json_error_response(str(e), status_code=500)


@inbox_bp.route('/api/inbox', methods=['POST'])
def add_to_inbox():
    """Add item to inbox"""
    try:
        service = get_inbox_service()
        data = request.get_json()

        if not data or not data.get('raw_input'):
            return json_error_response('raw_input is required', status_code=400)

        item = service.add(
            raw_input=data['raw_input'],
            source_type=data.get('source_type'),
            title=data.get('title'),
            url=data.get('url'),
            quick_tags=data.get('quick_tags'),
            priority=data.get('priority', 0),
            due_date=data.get('due_date')
        )

        return json_success_response(item.__dict__, status_code=201)

    except Exception as e:
        logger.error(f"Error adding to inbox: {e}")
        return json_error_response(str(e), status_code=500)


@inbox_bp.route('/api/inbox/<item_id>', methods=['GET'])
def get_inbox_item(item_id: str):
    """Get inbox item by ID"""
    try:
        service = get_inbox_service()
        item = service.get_by_id(item_id)

        if not item:
            return json_error_response('Item not found', 'NOT_FOUND', status_code=404)

        return json_success_response(item.__dict__)

    except Exception as e:
        logger.error(f"Error getting inbox item: {e}")
        return json_error_response(str(e), status_code=500)


@inbox_bp.route('/api/inbox/<item_id>', methods=['PUT'])
def update_inbox_item(item_id: str):
    """Update inbox item"""
    try:
        service = get_inbox_service()
        data = request.get_json()

        if not data:
            return json_error_response('No data provided', status_code=400)

        # Update tags if provided
        if 'quick_tags' in data:
            service.update_tags(item_id, data['quick_tags'])

        # Update priority if provided
        if 'priority' in data:
            service.update_priority(item_id, data['priority'])

        # Get updated item
        item = service.get_by_id(item_id)

        if not item:
            return json_error_response('Item not found', 'NOT_FOUND', status_code=404)

        return json_success_response(item.__dict__)

    except Exception as e:
        logger.error(f"Error updating inbox item: {e}")
        return json_error_response(str(e), status_code=500)


@inbox_bp.route('/api/inbox/<item_id>', methods=['DELETE'])
def delete_inbox_item(item_id: str):
    """Delete inbox item"""
    try:
        service = get_inbox_service()
        success = service.process(item_id, ProcessAction.DELETE)

        if not success:
            return json_error_response('Item not found or could not be deleted', 'NOT_FOUND', status_code=404)

        return json_success_response({'deleted': item_id})

    except Exception as e:
        logger.error(f"Error deleting inbox item: {e}")
        return json_error_response(str(e), status_code=500)


@inbox_bp.route('/api/inbox/<item_id>/process', methods=['PUT'])
def process_inbox_item(item_id: str):
    """Process an inbox item"""
    try:
        service = get_inbox_service()
        data = request.get_json() or {}

        action_str = data.get('action', 'process').lower()
        content_id = data.get('content_id')
        snooze_until = data.get('snooze_until')

        # Map action string to enum
        action_map = {
            'process': ProcessAction.PROCESS,
            'delete': ProcessAction.DELETE,
            'snooze': ProcessAction.SNOOZE,
            'archive': ProcessAction.ARCHIVE
        }

        action = action_map.get(action_str, ProcessAction.PROCESS)

        success = service.process(
            item_id,
            action,
            content_id=content_id,
            snooze_until=snooze_until
        )

        if not success:
            return json_error_response('Item not found or could not be processed', 'NOT_FOUND', status_code=404)

        return json_success_response({
            'processed': item_id,
            'action': action_str
        })

    except Exception as e:
        logger.error(f"Error processing inbox item: {e}")
        return json_error_response(str(e), status_code=500)


@inbox_bp.route('/api/inbox/stats', methods=['GET'])
def get_inbox_stats():
    """Get inbox statistics"""
    try:
        service = get_inbox_service()
        stats = service.get_stats()

        return json_success_response({
            'total': stats.total,
            'pending': stats.pending,
            'processed': stats.processed,
            'snoozed': stats.snoozed,
            'overdue': stats.overdue,
            'by_source_type': stats.by_source_type,
            'by_priority': stats.by_priority
        })

    except Exception as e:
        logger.error(f"Error getting inbox stats: {e}")
        return json_error_response(str(e), status_code=500)


@inbox_bp.route('/api/inbox/process-batch', methods=['POST'])
def batch_process():
    """Process multiple inbox items"""
    try:
        service = get_inbox_service()
        data = request.get_json()

        if not data or 'item_ids' not in data or 'action' not in data:
            return json_error_response('item_ids and action are required', status_code=400)

        item_ids = data['item_ids']
        action_str = data['action'].lower()
        content_id = data.get('content_id')
        snooze_until = data.get('snooze_until')

        if not isinstance(item_ids, list) or not item_ids:
            return json_error_response('item_ids must be a non-empty list', status_code=400)

        # Map action string to enum
        action_map = {
            'process': ProcessAction.PROCESS,
            'delete': ProcessAction.DELETE,
            'snooze': ProcessAction.SNOOZE,
            'archive': ProcessAction.ARCHIVE
        }

        action = action_map.get(action_str)
        if not action:
            return json_error_response(f'Invalid action: {action_str}', status_code=400)

        success_count, fail_count = service.bulk_process(
            item_ids,
            action,
            content_id=content_id,
            snooze_until=snooze_until
        )

        return json_success_response({
            'success': success_count,
            'failed': fail_count,
            'action': action_str
        })

    except Exception as e:
        logger.error(f"Error in batch process: {e}")
        return json_error_response(str(e), status_code=500)


@inbox_bp.route('/api/inbox/unsnooze', methods=['POST'])
def unsnooze_items():
    """Unsnooze all due items"""
    try:
        service = get_inbox_service()
        count = service.unsnooze_due_items()

        return json_success_response({
            'unsnoozed': count
        })

    except Exception as e:
        logger.error(f"Error unsnoozing items: {e}")
        return json_error_response(str(e), status_code=500)


@inbox_bp.route('/api/inbox/cleanup', methods=['POST'])
def cleanup_inbox():
    """Clean up old processed items"""
    try:
        service = get_inbox_service()
        data = request.get_json() or {}
        days = data.get('days', 30)

        count = service.cleanup_old_items(days=days)

        return json_success_response({
            'deleted': count,
            'days': days
        })

    except Exception as e:
        logger.error(f"Error cleaning up inbox: {e}")
        return json_error_response(str(e), status_code=500)
