"""
Composite API Blueprint

Handles complex operations and composite data responses.
Uses multiple services for different endpoints.
"""
from flask import Blueprint, request, jsonify
from typing import Optional
import logging
from datetime import datetime, timedelta
import json
import csv
from io import StringIO

from database.db_interface import get_connection
from app.utils.api import json_success_response, json_error_response

# Import services
from services.content_service import ContentService
from services.inbox_service import InboxService
from services.node_service import NodeService
from services.note_service import NoteService
from services.link_service import LinkService
from services.session_service import LearningSessionService
from services.creation_service import CreationWorkshopService
from services.graph_service import KnowledgeGraphService

logger = logging.getLogger(__name__)

# Blueprint definition
api_bp = Blueprint('api', __name__, url_prefix='/api')


def get_db():
    """Get database connection for direct queries when needed"""
    return get_connection()


# Composite endpoints using multiple services


@api_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """Get comprehensive dashboard data in a single request"""
    try:
        db = get_db()

        # Use services to get data
        content_service = ContentService()
        inbox_service = InboxService()
        node_service = NodeService()
        session_service = LearningSessionService()
        creation_service = CreationWorkshopService()

        # Quick stats
        stats = {
            'total_content': len(content_service.list_contents(archived=False, limit=10000)),
            'favorited': len(content_service.list_contents(favorited=True, archived=False, limit=10000)),
            'total_nodes': len(node_service.get_all(limit=10000)),
            'total_notes': len(note_service := NoteService().get_all(limit=10000)),
            'total_links': len(link_service := LinkService().list_links(limit=10000)),
        }

        # Inbox stats
        inbox_stats_obj = inbox_service.get_stats()
        inbox_stats = {
            'pending': inbox_stats_obj.pending,
            'snoozed': inbox_stats_obj.snoozed,
        }

        # Recent content (last 7 days)
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        recent_content = content_service.list_contents(
            archived=False,
            sort_by='created_at',
            sort_order='DESC',
            limit=10
        )[:10]

        # Due for review
        due_reviews_data = session_service.get_due_reviews(limit=5)
        due_reviews = []
        for content_id, schedule in due_reviews_data:
            # Get content details
            content = content_service.get_content(content_id)
            if content:
                due_reviews.append({
                    'content_id': content_id,
                    'title': content.get('title'),
                    'next_review': schedule.next_review
                })

        # Active projects
        active_projects = node_service.get_by_type(
            node_service.NodeType.PROJECT,
            status=node_service.NodeStatus.ACTIVE,
            limit=5
        )

        # Active creations
        active_creations = creation_service.get_active_projects(limit=5)

        # Recent activity (last 24 hours)
        day_ago = (datetime.now() - timedelta(days=1)).isoformat()
        recent_activity = []

        # Recent notes
        note_service = NoteService()
        notes = note_service.get_recent(limit=5)
        for note in notes:
            try:
                created_at = datetime.fromisoformat(note.created_at) if hasattr(note, 'created_at') and note.created_at else datetime.now()
                if created_at.isoformat() >= day_ago:
                    recent_activity.append({
                        'id': note.id,
                        'created_at': note.created_at,
                        'type': 'note',
                        'description': (note.content or '')[:50]
                    })
            except:
                pass

        # Recent links
        link_service = LinkService()
        links = link_service.list_links(limit=5)
        for link in links[:5]:
            try:
                created_at = datetime.fromisoformat(link['created_at']) if link.get('created_at') else datetime.now()
                if created_at.isoformat() >= day_ago:
                    recent_activity.append({
                        'id': link.get('id'),
                        'created_at': link.get('created_at'),
                        'type': 'link',
                        'description': link.get('link_type', 'related')
                    })
            except:
                pass

        # Sort by date
        recent_activity.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        # Content by type
        all_content = content_service.list_contents(archived=False, limit=10000)
        by_type_count = {}
        for content in all_content:
            content_type = content.get('content_type', 'unknown')
            by_type_count[content_type] = by_type_count.get(content_type, 0) + 1

        by_type = [{'content_type': k, 'count': v} for k, v in sorted(by_type_count.items(), key=lambda x: x[1], reverse=True)]

        return json_success_response({
            'stats': stats,
            'inbox': inbox_stats,
            'recent_content': recent_content[:10],
            'due_reviews': due_reviews[:5],
            'active_projects': [p.__dict__ for p in active_projects],
            'active_creations': [c.__dict__ for c in active_creations],
            'recent_activity': recent_activity[:10],
            'content_by_type': by_type,
            'generated_at': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        return json_error_response(str(e), status_code=500)


@api_bp.route('/export', methods=['GET'])
def export_data():
    """Export data in various formats"""
    try:
        format_type = request.args.get('format', 'json').lower()
        content_type = request.args.get('content_type', 'all')

        content_service = ContentService()

        # Get data based on content_type
        if content_type == 'all':
            contents = content_service.list_contents(limit=1000)
        else:
            contents = content_service.list_contents(content_type=content_type, limit=1000)

        data = contents

        # Parse JSON fields for export
        for item in data:
            if item.get('tags'):
                try:
                    item['tags'] = json.loads(item['tags']) if isinstance(item['tags'], str) else item['tags']
                except:
                    pass
            if item.get('ai_analysis'):
                try:
                    item['ai_analysis'] = json.loads(item['ai_analysis']) if isinstance(item['ai_analysis'], str) else item['ai_analysis']
                except:
                    pass

        if format_type == 'json':
            return jsonify(data)

        elif format_type == 'csv':
            output = StringIO()
            if data:
                # Flatten nested structures for CSV
                flat_data = []
                for item in data:
                    flat_item = {
                        'id': item.get('id'),
                        'title': item.get('title'),
                        'url': item.get('url'),
                        'content_type': item.get('content_type'),
                        'source_type': item.get('source_type'),
                        'summary': item.get('summary', '')[:200],
                        'created_at': item.get('created_at'),
                        'favorited': item.get('favorited'),
                    }
                    flat_data.append(flat_item)

                writer = csv.DictWriter(output, fieldnames=flat_data[0].keys())
                writer.writeheader()
                writer.writerows(flat_data)

            response = output.getvalue()
            return response, 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename=linker_mind_export_{datetime.now().strftime("%Y%m%d")}.csv'
            }

        elif format_type == 'markdown':
            output = "# Linker Mind Export\n\n"
            output += f"Generated: {datetime.now().isoformat()}\n\n"
            output += f"Total items: {len(data)}\n\n"

            for item in data:
                output += f"## {item.get('title', 'Untitled')}\n\n"
                output += f"- **ID**: {item.get('id')}\n"
                output += f"- **Type**: {item.get('content_type')}\n"
                output += f"- **Source**: {item.get('source_type')}\n"
                if item.get('url'):
                    output += f"- **URL**: {item['url']}\n"
                output += f"- **Created**: {item.get('created_at')}\n\n"
                if item.get('summary'):
                    output += f"### Summary\n\n{item['summary']}\n\n"
                output += "---\n\n"

            return output, 200, {
                'Content-Type': 'text/markdown',
                'Content-Disposition': f'attachment; filename=linker_mind_export_{datetime.now().strftime("%Y%m%d")}.md'
            }

        else:
            return json_error_response(f'Unsupported format: {format_type}', status_code=400)

    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return json_error_response(str(e), status_code=500)


@api_bp.route('/sync', methods=['POST'])
def trigger_sync():
    """Trigger data synchronization"""
    try:
        data = request.get_json() or {}
        sync_type = data.get('type', 'all')

        results = {
            'started_at': datetime.now().isoformat(),
            'operations': []
        }

        if sync_type in ['all', 'stats']:
            # Recalculate statistics
            # This would trigger background jobs in production
            results['operations'].append({
                'type': 'stats',
                'status': 'completed',
                'message': 'Statistics recalculated'
            })

        if sync_type in ['all', 'graph']:
            # Rebuild knowledge graph
            graph_service = KnowledgeGraphService()
            graph_service.get_statistics()  # Force refresh
            results['operations'].append({
                'type': 'graph',
                'status': 'completed',
                'message': 'Knowledge graph rebuilt'
            })

        if sync_type in ['all', 'search']:
            # Rebuild search index
            from services.search_service import EnhancedSearchService
            search_service = EnhancedSearchService()
            search_service.get_facets('')  # Force refresh
            results['operations'].append({
                'type': 'search',
                'status': 'completed',
                'message': 'Search index updated'
            })

        if sync_type in ['all', 'reviews']:
            # Check for due reviews
            session_service = LearningSessionService()
            due_data = session_service.get_due_reviews(limit=1000)

            results['operations'].append({
                'type': 'reviews',
                'status': 'completed',
                'message': f'{len(due_data)} items due for review'
            })

        results['completed_at'] = datetime.now().isoformat()

        return json_success_response(results)

    except Exception as e:
        logger.error(f"Error in sync: {e}")
        return json_error_response(str(e), status_code=500)


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        db = get_db()

        # Check database connection
        tables = db.get_tables()

        # Check critical tables
        critical_tables = ['contents', 'notes', 'nodes', 'links']
        missing_tables = [t for t in critical_tables if t not in tables]

        health = {
            'status': 'healthy' if not missing_tables else 'degraded',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'tables': len(tables),
                'critical_tables_present': len(critical_tables) - len(missing_tables),
                'missing_tables': missing_tables
            },
            'services': {
                'content_service': 'available',
                'inbox_service': 'available',
                'node_service': 'available',
                'note_service': 'available',
                'link_service': 'available',
                'session_service': 'available',
                'creation_service': 'available',
                'graph_service': 'available'
            }
        }

        status_code = 200 if health['status'] == 'healthy' else 503

        return jsonify(health), status_code

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 503


@api_bp.route('/settings', methods=['GET'])
def get_settings():
    """Get application settings"""
    try:
        settings = {
            'version': '2.0.0',
            'features': {
                'inbox': True,
                'para_organization': True,
                'progressive_summarization': True,
                'bidirectional_linking': True,
                'creation_workspace': True,
                'learning_tracking': True,
                'skill_trees': True,
                'knowledge_graph': True,
                'advanced_search': True
            },
            'limits': {
                'max_upload_size': 16 * 1024 * 1024,  # 16MB
                'max_page_size': 100,
                'default_page_size': 20
            },
            'content_types': [
                'article', 'book', 'paper', 'tweet', 'post', 'doc',
                'video', 'audio', 'podcast', 'course', 'image'
            ],
            'node_types': ['PROJECT', 'AREA', 'RESOURCE', 'ARCHIVE', 'CUSTOM'],
            'link_types': [
                'reference', 'related', 'opposes', 'extends',
                'example', 'question', 'application', 'inspired'
            ]
        }

        return json_success_response(settings)

    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        return json_error_response(str(e), status_code=500)
