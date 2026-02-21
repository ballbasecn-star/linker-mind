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


@creation_bp.route('/creations/new')
def new_creation_page():
    """New creation project page"""
    return render_template('creation_workshop.html',
                         project={'id': None, 'title': '', 'status': 'research'},
                         materials=[],
                         sections=[])


@creation_bp.route('/creations/<project_id>')
def creation_detail_page(project_id: str):
    """Creation workspace page"""
    try:
        service = get_creation_service()
        project = service.get_by_id(project_id)

        if not project:
            return render_template('error.html', error='Creation not found'), 404

        # Get source materials from project's source_materials JSON field
        db = get_connection()
        materials = []
        if project.source_materials:
            placeholders = ','.join(['?' for _ in project.source_materials])
            materials = db.fetchall(f"""
                SELECT c.*
                FROM contents c
                WHERE c.id IN ({placeholders})
            """, tuple(project.source_materials))

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


# ============== AI Writing Workflow Endpoints ==============

@creation_bp.route('/api/creations/from-material', methods=['POST'])
def create_from_material():
    """Create a new creation project from source materials"""
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

        # Create project
        project = service.create(
            project_type=project_type,
            title=data['title'],
            brief=data.get('brief'),
            target_date=data.get('target_date'),
            word_count_goal=data.get('word_count_goal')
        )

        # Add source materials if provided
        material_ids = data.get('material_ids', [])
        for content_id in material_ids:
            service.add_source_material(project.id, content_id)

        # Generate initial outline if materials added
        if material_ids:
            service.update(project.id, status=CreationStatus.OUTLINING)

        return json_success_response(project.__dict__, status_code=201)

    except Exception as e:
        logger.error(f"Error creating from material: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/generate-draft', methods=['POST'])
def generate_draft(project_id: str):
    """Generate draft from source materials"""
    try:
        from services.creation_assistant import AICreationAssistantService

        assistant = AICreationAssistantService()
        data = request.get_json() or {}

        target_words = data.get('target_words', 1000)

        result = assistant.generate_draft(project_id, target_words)

        if not result:
            return json_error_response('Failed to generate draft', status_code=500)

        if result.get('error'):
            return json_error_response(result['error'], status_code=400)

        # Update project status
        service = get_creation_service()
        service.update(project_id, status=CreationStatus.DRAFTING)

        return json_success_response(result)

    except Exception as e:
        logger.error(f"Error generating draft: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/improve-structure', methods=['POST'])
def improve_structure(project_id: str):
    """Get A/B structural improvement suggestions"""
    try:
        from services.creation_assistant import AICreationAssistantService

        assistant = AICreationAssistantService()
        data = request.get_json() or {}

        draft_content = data.get('draft_content', '')
        if not draft_content:
            return json_error_response('draft_content is required', status_code=400)

        result = assistant.suggest_structural_improvements(project_id, draft_content)

        if not result:
            return json_error_response('Failed to generate suggestions', status_code=500)

        return json_success_response(result)

    except Exception as e:
        logger.error(f"Error improving structure: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/generate-titles', methods=['POST'])
def generate_titles(project_id: str):
    """Generate title suggestions"""
    try:
        from services.creation_assistant import AICreationAssistantService

        assistant = AICreationAssistantService()
        data = request.get_json() or {}

        content = data.get('content', '')
        if not content:
            return json_error_response('content is required', status_code=400)

        num_titles = data.get('num_titles', 5)

        result = assistant.generate_titles(project_id, content, num_titles)

        if not result:
            return json_error_response('Failed to generate titles', status_code=500)

        return json_success_response({'titles': result})

    except Exception as e:
        logger.error(f"Error generating titles: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/platform-format', methods=['POST'])
def platform_format(project_id: str):
    """Convert content to platform-specific format"""
    try:
        from services.creation_assistant import AICreationAssistantService

        assistant = AICreationAssistantService()
        data = request.get_json() or {}

        content = data.get('content', '')
        if not content:
            return json_error_response('content is required', status_code=400)

        platform = data.get('platform', 'x')

        result = assistant.convert_to_platform_format(project_id, content, platform)

        if not result:
            return json_error_response('Failed to convert format', status_code=500)

        return json_success_response(result)

    except Exception as e:
        logger.error(f"Error converting format: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/workflow', methods=['GET'])
def get_workflow(project_id: str):
    """Get AI writing workflow for a project"""
    try:
        from services.creation_service import get_workflow_for_type

        service = get_creation_service()
        project = service.get_by_id(project_id)

        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        workflow = get_workflow_for_type(project.project_type)

        # Map workflow steps to project progress
        current_status = project.status
        current_step = 0

        for i, step in enumerate(workflow):
            if step['status'].value == current_status:
                current_step = i
                break
            elif step['status'].value in [s.value for s in [
                CreationStatus.RESEARCH, CreationStatus.OUTLINING
            ]] and current_status in [s.value for s in [
                CreationStatus.RESEARCH, CreationStatus.OUTLINING
            ]]:
                current_step = 0
            elif step['status'].value in [s.value for s in [
                CreationStatus.DRAFTING, CreationStatus.EDITING
            ]] and current_status in [s.value for s in [
                CreationStatus.DRAFTING, CreationStatus.EDITING
            ]]:
                current_step = 1
            elif step['status'].value == CreationStatus.REVIEWING and current_status == CreationStatus.REVIEWING.value:
                current_step = 2
            elif step['status'].value == CreationStatus.FINALIZING and current_status == CreationStatus.FINALIZING.value:
                current_step = 3
            elif step['status'].value == CreationStatus.PUBLISHED and current_status == CreationStatus.PUBLISHED.value:
                current_step = 4

        # Convert workflow to JSON-serializable format
        workflow_json = []
        for step in workflow:
            workflow_json.append({
                'step': step['step'],
                'status': step['status'].value,  # Convert enum to string
                'description': step['description']
            })

        return json_success_response({
            'workflow': workflow_json,
            'current_step': current_step,
            'current_status': current_status
        })

    except Exception as e:
        logger.error(f"Error getting workflow: {e}")
        return json_error_response(str(e), status_code=500)


# ============== Image Generation API Endpoints ==============

@creation_bp.route('/api/creations/<project_id>/analyze-images', methods=['POST'])
def analyze_images(project_id: str):
    """Analyze content and identify sections needing images"""
    try:
        data = request.get_json() or {}
        content = data.get('content')

        service = get_creation_service()
        project = service.get_by_id(project_id)

        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        assistant = AICreationAssistantService()
        suggestions = assistant.analyze_content_for_images(project_id, content)

        if suggestions is None:
            return json_error_response('Failed to analyze content', status_code=500)

        return json_success_response({
            'suggestions': suggestions,
            'total_sections': len(suggestions),
            'sections_needing_images': sum(1 for s in suggestions if s.get('needs_image'))
        })

    except Exception as e:
        logger.error(f"Error analyzing images: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/generate-cover', methods=['POST'])
def generate_cover(project_id: str):
    """Generate cover images for the article"""
    try:
        data = request.get_json() or {}
        title = data.get('title')
        description = data.get('description')
        num_images = data.get('num_images', 3)
        style = data.get('style', 'modern')

        service = get_creation_service()
        project = service.get_by_id(project_id)

        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        assistant = AICreationAssistantService()
        images = assistant.generate_cover_image(
            project_id=project_id,
            title=title,
            description=description,
            num_images=num_images,
            style=style
        )

        if images is None:
            return json_error_response('Failed to generate cover images', status_code=500)

        return json_success_response({
            'images': images,
            'type': 'cover'
        })

    except Exception as e:
        logger.error(f"Error generating cover: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/generate-section-images', methods=['POST'])
def generate_section_images(project_id: str):
    """Generate images for a specific section"""
    try:
        data = request.get_json() or {}
        section_index = data.get('section_index', 0)
        section_title = data.get('section_title', '')
        section_content = data.get('section_content', '')
        num_images = data.get('num_images', 2)

        service = get_creation_service()
        project = service.get_by_id(project_id)

        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        assistant = AICreationAssistantService()
        images = assistant.generate_section_images(
            project_id=project_id,
            section_index=section_index,
            section_title=section_title,
            section_content=section_content,
            num_images=num_images
        )

        if images is None:
            return json_error_response('Failed to generate section images', status_code=500)

        return json_success_response({
            'images': images,
            'type': 'section',
            'section_index': section_index,
            'section_title': section_title
        })

    except Exception as e:
        logger.error(f"Error generating section images: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/suggest-images', methods=['GET'])
def suggest_library_images(project_id: str):
    """Suggest images from content library"""
    try:
        keywords = request.args.get('keywords', '').split(',')
        keywords = [k.strip() for k in keywords if k.strip()]
        limit = int(request.args.get('limit', 10))

        service = get_creation_service()
        project = service.get_by_id(project_id)

        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        assistant = AICreationAssistantService()
        suggestions = assistant.suggest_from_library(
            project_id=project_id,
            keywords=keywords if keywords else None,
            limit=limit
        )

        return json_success_response({
            'suggestions': suggestions,
            'total': len(suggestions)
        })

    except Exception as e:
        logger.error(f"Error suggesting images: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/generate-social-image', methods=['POST'])
def generate_social_image(project_id: str):
    """Generate images for social media platforms"""
    try:
        data = request.get_json() or {}
        content = data.get('content', '')
        platform = data.get('platform', 'x')
        num_images = data.get('num_images', 3)

        if not content:
            return json_error_response('Content is required', status_code=400)

        assistant = AICreationAssistantService()
        images = assistant.generate_social_image(
            content=content,
            platform=platform,
            num_images=num_images
        )

        return json_success_response({
            'images': images,
            'platform': platform,
            'type': 'social'
        })

    except Exception as e:
        logger.error(f"Error generating social image: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/save-images', methods=['POST'])
def save_project_images(project_id: str):
    """Save generated/selected images to project"""
    try:
        data = request.get_json() or {}
        images = data.get('images', [])
        image_type = data.get('type', 'section')
        section_index = data.get('section_index')

        if not images:
            return json_error_response('No images to save', status_code=400)

        service = get_creation_service()
        project = service.get_by_id(project_id)

        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        assistant = AICreationAssistantService()
        success = assistant.save_project_images(
            project_id=project_id,
            images=images,
            image_type=image_type,
            section_index=section_index
        )

        if not success:
            return json_error_response('Failed to save images', status_code=500)

        return json_success_response({
            'success': True,
            'saved_count': len(images)
        })

    except Exception as e:
        logger.error(f"Error saving images: {e}")
        return json_error_response(str(e), status_code=500)


@creation_bp.route('/api/creations/<project_id>/set-cover-image', methods=['PUT'])
def set_cover_image(project_id: str):
    """Set the cover image for the project"""
    try:
        data = request.get_json() or {}
        image_url = data.get('image_url')

        if not image_url:
            return json_error_response('Image URL is required', status_code=400)

        service = get_creation_service()
        project = service.get_by_id(project_id)

        if not project:
            return json_error_response('Creation not found', 'NOT_FOUND', status_code=404)

        # Update project with cover image
        service.update(project_id, cover_image=image_url)

        return json_success_response({
            'success': True,
            'cover_image': image_url
        })

    except Exception as e:
        logger.error(f"Error setting cover image: {e}")
        return json_error_response(str(e), status_code=500)


# Import AICreationAssistantService
from services.creation_assistant import AICreationAssistantService
