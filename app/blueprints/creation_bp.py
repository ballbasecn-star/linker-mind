"""
Creation API Blueprint

Handles creative projects and AI-assisted creation.
Uses CreationWorkshopService for all business logic.
"""
from flask import Blueprint, request, jsonify, render_template
from typing import Optional
import logging
from datetime import datetime

from services.creation_service import CreationWorkshopService, CreationType, CreationStatus
from app.utils.api import json_success_response, json_error_response
from database.db_interface import get_connection
from database import json_list, json_dict

logger = logging.getLogger(__name__)

# Blueprint definition
creation_bp = Blueprint('creation', __name__)


def get_creation_service():
    """Get CreationWorkshopService instance"""
    return CreationWorkshopService()


# Page routes


@creation_bp.route('/creations')
def creations_page():
    """Creation projects list page"""
    try:
        service = get_creation_service()
        projects = service.get_active_projects(limit=50)

        return render_template('creations.html',
                            projects=[p.__dict__ for p in projects])
    except Exception as e:
        logger.error(f"Error loading creations page: {e}")
        return render_template('creations.html', projects=[])


@creation_bp.route('/creations/<project_id>')
def creation_detail_page(project_id: str):
    """Creation workspace page"""
    try:
        service = get_creation_service()
        project = service.get_by_id(project_id)

        if not project:
            return render_template('error.html', error='Creation not found'), 404

        # Get source materials
        db = get_connection()
        materials = db.fetchall("""
            SELECT c.*
            FROM creation_sources cs
            JOIN contents c ON cs.content_id = c.id
            WHERE cs.project_id = ?
            ORDER BY cs.added_at DESC
        """, (project_id,))

        # Get outline sections
        outline = project.outline or []

        return render_template('creation_workshop.html',
                            project=project.__dict__,
                            materials=[dict(row) for row in materials],
                            sections=outline)
    except Exception as e:
        logger.error(f"Error loading creation detail: {e}")
        return render_template('error.html', error=str(e)), 500


# API endpoints


@creation_bp.route('/api/creations', methods=['GET'])
def list_creations():
    """List creation projects"""
    try:
        service = get_creation_service()

        # Get filters
        status = request.args.get('status')
        project_type = request.args.get('project_type')

        projects = []

        if project_type:
            try:
                type_enum = CreationType[project_type.upper()]
                if status:
                    status_enum = CreationStatus[status.upper()]
                    projects = service.get_by_type(type_enum, status=status_enum)
                else:
                    projects = service.get_by_type(type_enum)
            except KeyError:
                return json_error_response(f'Invalid type or status: {project_type}, {status}', status_code=400)
        elif status:
            try:
                status_enum = CreationStatus[status.upper()]
                projects = service.get_by_status(status_enum)
            except KeyError:
                return json_error_response(f'Invalid status: {status}', status_code=400)
        else:
            projects = service.get_active_projects(limit=100)

        return json_success_response([p.__dict__ for p in projects])

    except Exception as e:
        logger.error(f"Error listing creations: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations', methods=['POST'])
def create_creation():
    """Create a new creation project"""
    try:
        service = get_creation_service()
        data = request.get_json()

        if not data or not data.get('title'):
            return json_error_response('title is required', status_code=400)

        project_type_str = data.get('project_type', 'ARTICLE').upper()
        try:
            project_type = CreationType[project_type_str]
        except KeyError:
            return json_error_response(f'Invalid project_type: {project_type_str}', status_code=400)

        project = service.create(
            project_type=project_type,
            title=data['title'],
            brief=data.get('brief'),
            target_date=data.get('target_date'),
            word_count_goal=data.get('word_count_goal')
        )

        return json_success_response(project.__dict__, status_code=201)

    except Exception as e:
        logger.error(f"Error creating creation: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>', methods=['GET'])
def get_creation(project_id: str):
    """Get creation project by ID"""
    try:
        service = get_creation_service()
        project = service.get_by_id(project_id)

        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        return json_success_response(project.__dict__)

    except Exception as e:
        logger.error(f"Error getting creation: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>', methods=['PUT'])
def update_creation(project_id: str):
    """Update creation project"""
    try:
        service = get_creation_service()
        data = request.get_json()

        if not data:
            return json_error_response('No data provided', status_code=400)

        # Parse status if provided
        status = None
        if 'status' in data:
            try:
                status = CreationStatus[data['status'].upper()]
            except KeyError:
                return json_error_response(f'Invalid status: {data["status"]}', status_code=400)

        project = service.update(
            project_id=project_id,
            title=data.get('title'),
            brief=data.get('brief'),
            status=status,
            draft_content=data.get('draft_content'),
            progress=data.get('progress'),
            target_date=data.get('target_date'),
            word_count_goal=data.get('word_count_goal'),
            word_count_actual=data.get('word_count_actual')
        )

        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        return json_success_response(project.__dict__)

    except Exception as e:
        logger.error(f"Error updating creation: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>', methods=['DELETE'])
def delete_creation(project_id: str):
    """Delete creation project"""
    try:
        service = get_creation_service()
        success = service.delete(project_id)

        if not success:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        return json_success_response({'deleted': project_id})

    except Exception as e:
        logger.error(f"Error deleting creation: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/materials', methods=['POST'])
def add_material(project_id: str):
    """Add source material to creation"""
    try:
        service = get_creation_service()
        data = request.get_json()

        if not data or 'content_id' not in data:
            return json_error_response('content_id is required', status_code=400)

        success = service.add_source_material(
            project_id=project_id,
            content_id=data['content_id']
        )

        if not success:
            return json_error_response('Creation not found or material already added', status_code=404)

        return json_success_response({'added': True})

    except Exception as e:
        logger.error(f"Error adding material: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/outline', methods=['POST'])
def generate_outline(project_id: str):
    """Generate AI outline for creation"""
    try:
        service = get_creation_service()
        data = request.get_json() or {}

        project = service.get_by_id(project_id)
        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        # Get source materials
        db = get_connection()
        materials = db.fetchall("""
            SELECT c.* FROM contents c
            WHERE c.id IN (
                SELECT value FROM json_each(
                    (SELECT source_materials FROM creation_projects WHERE id = ?)
                )
            )
            LIMIT 20
        """, (project_id,))

        # Simple outline generation based on materials
        outline = []

        # Group materials by topic
        topics = {}
        for material in materials:
            m = dict(material)
            ai_data = m.get('ai_analysis')
            if ai_data:
                try:
                    import json
                    ai = json.loads(ai_data) if isinstance(ai_data, str) else ai_data
                    for topic in ai.get('topics', []):
                        if topic not in topics:
                            topics[topic] = []
                        topics[topic].append(m)
                except:
                    pass

        # Create outline sections
        section_order = 1
        for topic, items in topics.items():
            outline.append({
                'id': f'section_{section_order}',
                'title': topic,
                'content': f'Section about {topic} based on {len(items)} source(s)',
                'order_index': section_order,
                'expanded': False
            })
            section_order += 1

        # Add intro and conclusion
        outline = [
            {
                'id': 'section_intro',
                'title': 'Introduction',
                'content': 'Introduce the topic and provide context',
                'order_index': 0,
                'expanded': False
            }
        ] + outline + [
            {
                'id': 'section_conclusion',
                'title': 'Conclusion',
                'content': 'Summarize key points and provide final thoughts',
                'order_index': section_order,
                'expanded': False
            }
        ]

        # Update project with outline
        project.outline = outline
        service.update(project_id, status=CreationStatus.OUTLINING)

        return json_success_response(outline)

    except Exception as e:
        logger.error(f"Error generating outline: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/outline', methods=['PUT'])
def update_outline(project_id: str):
    """Update creation outline"""
    try:
        service = get_creation_service()
        data = request.get_json()

        if not data or 'outline' not in data:
            return json_error_response('outline is required', status_code=400)

        project = service.get_by_id(project_id)
        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        # Update each section
        for section_data in data['outline']:
            section_id = section_data.get('id')
            if section_id:
                service.update_outline_section(
                    project_id=project_id,
                    section_id=section_id,
                    title=section_data.get('title'),
                    content=section_data.get('content'),
                    status=section_data.get('status')
                )

        return json_success_response({'updated': True})

    except Exception as e:
        logger.error(f"Error updating outline: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/sections/<section_id>', methods=['POST'])
def expand_section(project_id: str, section_id: str):
    """Expand a section with AI-generated content"""
    try:
        service = get_creation_service()
        data = request.get_json() or {}

        project = service.get_by_id(project_id)
        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        # Find section
        section = None
        for s in project.outline:
            if s.get('id') == section_id:
                section = s
                break

        if not section:
            return json_error_response('Section not found', 'NOT_FOUND', status_code=404)

        # Simple expansion based on related content
        expanded_content = section.get('content', '')

        # Get related content for this section
        db = get_connection()
        materials = db.fetchall("""
            SELECT c.* FROM contents c
            WHERE c.id IN (
                SELECT value FROM json_each(
                    (SELECT source_materials FROM creation_projects WHERE id = ?)
                )
            )
            LIMIT 10
        """, (project_id,))

        # Add key points from materials
        key_points = []
        for material in materials[:5]:
            m = dict(material)
            summary = m.get('summary', '')
            if summary:
                key_points.append(f"- From '{m.get('title', 'Untitled')}': {summary[:100]}...")

        if key_points:
            expanded_content += "\n\n**Key Points:**\n" + "\n".join(key_points)

        # Update section
        service.update_outline_section(
            project_id=project_id,
            section_id=section_id,
            content=expanded_content
        )

        service.update(project_id, status=CreationStatus.DRAFTING)

        return json_success_response({
            'section_id': section_id,
            'content': expanded_content
        })

    except Exception as e:
        logger.error(f"Error expanding section: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/draft', methods=['PUT'])
def save_draft(project_id: str):
    """Save draft content"""
    try:
        service = get_creation_service()
        data = request.get_json()

        if not data or 'content' not in data:
            return json_error_response('content is required', status_code=400)

        project = service.update(
            project_id=project_id,
            draft_content=data['content'],
            status=CreationStatus.EDITING
        )

        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        return json_success_response({'saved': True})

    except Exception as e:
        logger.error(f"Error saving draft: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/publish', methods=['POST'])
def publish_creation(project_id: str):
    """Publish creation"""
    try:
        service = get_creation_service()
        data = request.get_json() or {}

        url = data.get('url')
        if not url:
            return json_error_response('url is required', status_code=400)

        success = service.publish(project_id, url)

        if not success:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        return json_success_response({
            'published': True,
            'url': url
        })

    except Exception as e:
        logger.error(f"Error publishing creation: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/citations', methods=['GET'])
def get_citations(project_id: str):
    """Get citation list for creation"""
    try:
        service = get_creation_service()
        format_type = request.args.get('format', 'academic')

        citations = service.get_citation_list(project_id, format_type=format_type)

        return json_success_response(citations)

    except Exception as e:
        logger.error(f"Error getting citations: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/gaps', methods=['GET'])
def find_gaps(project_id: str):
    """Find content gaps in creation"""
    try:
        service = get_creation_service()
        project = service.get_by_id(project_id)

        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        # Analyze gaps
        gaps = []

        # Check for common missing elements
        has_examples = False
        has_data = False
        has_quotes = False

        db = get_connection()
        materials = db.fetchall("""
            SELECT c.* FROM contents c
            WHERE c.id IN (
                SELECT value FROM json_each(
                    (SELECT source_materials FROM creation_projects WHERE id = ?)
                )
            )
        """, (project_id,))

        for material in materials:
            m = dict(material)
            content_type = m.get('content_type', '')
            if 'example' in content_type.lower():
                has_examples = True
            if 'data' in content_type.lower():
                has_data = True
            if m.get('ai_analysis'):
                try:
                    import json
                    ai = json.loads(m['ai_analysis']) if isinstance(m['ai_analysis'], str) else m['ai_analysis']
                    if ai.get('quotes'):
                        has_quotes = True
                except:
                    pass

        if not has_examples:
            gaps.append({
                'type': 'examples',
                'suggestion': 'Add concrete examples to illustrate key points',
                'priority': 'medium'
            })

        if not has_data:
            gaps.append({
                'type': 'data',
                'suggestion': 'Include data, statistics, or research to support claims',
                'priority': 'high'
            })

        if not has_quotes:
            gaps.append({
                'type': 'quotes',
                'suggestion': 'Add quotes from experts or original sources',
                'priority': 'low'
            })

        # Check source count
        source_count = len(project.source_materials) if project.source_materials else 0
        if source_count < 3:
            gaps.append({
                'type': 'sources',
                'suggestion': f'Add more sources (currently {source_count}, aim for at least 5-10)',
                'priority': 'high'
            })

        return json_success_response(gaps)

    except Exception as e:
        logger.error(f"Error finding gaps: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creation/projects', methods=['GET'])
def list_projects_alias():
    """Alias for /api/creations - list creation projects"""
    return list_creations()
