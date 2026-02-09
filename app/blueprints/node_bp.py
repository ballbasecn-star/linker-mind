"""
Node API Blueprint

Handles PARA organization system (Projects, Areas, Resources, Archive).
Uses NodeService for all business logic.
"""
from flask import Blueprint, request, jsonify, render_template, redirect
from typing import Optional
import logging

from services.node_service import NodeService, NodeType, NodeStatus
from app.utils.api import json_success_response, json_error_response
from app.utils.pagination import get_pagination_params, Pagination

logger = logging.getLogger(__name__)

# Blueprint definition
node_bp = Blueprint('node', __name__)

# Initialize service
def get_node_service():
    """Get NodeService instance"""
    return NodeService()


# Page routes


@node_bp.route('/projects')
def projects_page():
    """Projects page (legacy route - redirects to nodes)"""
    return redirect('/nodes')


@node_bp.route('/project/<node_id>')
def project_detail_legacy(node_id: str):
    """Legacy project detail route - redirects to node detail"""
    return redirect(f'/nodes/{node_id}')


@node_bp.route('/organization')
def organization_page():
    """Organization page (legacy route - redirects to nodes)"""
    return redirect('/nodes')


@node_bp.route('/nodes')
def nodes_page():
    """PARA organization page"""
    try:
        service = get_node_service()

        # Get all nodes by type
        projects = service.get_projects(active_only=False, limit=100)
        areas = service.get_areas(limit=100)
        resources = service.get_resources(limit=100)
        archive = service.get_archive(limit=100)

        # Get full tree
        tree = service.get_tree(max_depth=3)

        # Use new PARA organization template
        return render_template('para_organization.html',
                            projects=projects,
                            areas=areas,
                            resources=resources,
                            archive=archive,
                            tree=tree)
    except Exception as e:
        logger.error(f"Error loading nodes page: {e}")
        # Render with empty data instead of falling back to index
        return render_template('para_organization.html',
                            projects=[],
                            areas=[],
                            resources=[],
                            archive=[],
                            tree=[])


@node_bp.route('/nodes/<node_id>')
def node_detail(node_id: str):
    """Node detail page"""
    try:
        service = get_node_service()
        node = service.get_by_id(node_id)

        if not node:
            return render_template('error.html', error='Node not found'), 404

        # Get content for this node
        contents = service.get_content(node_id, limit=100)

        # Get children
        children = service.get_children(node_id)

        # Get stats
        stats = service.get_stats(node_id)

        # Get parent
        parent = None
        if node.parent_id:
            parent = service.get_by_id(node.parent_id)

        return render_template('project_detail.html',
                            node=node,
                            contents=contents,
                            children=children,
                            stats=stats,
                            parent=parent)
    except Exception as e:
        logger.error(f"Error loading node detail: {e}")
        return render_template('error.html', error=str(e)), 500


@node_bp.route('/nodes/test-input')
def test_input_page():
    """Test page for input performance"""
    return render_template('para_organization_test.html')


@node_bp.route('/nodes/test-css')
def test_css_page():
    """Test page for CSS performance"""
    return render_template('para_organization_css_test.html')


@node_bp.route('/nodes/test-minimal')
def test_minimal_page():
    """Test page with minimal functionality"""
    return render_template('para_organization_minimal.html')


@node_bp.route('/nodes/test-api')
def test_api_page():
    """Test page that loads api.js but doesn't make API calls"""
    return render_template('para_organization_api_test.html')


# API endpoints


@node_bp.route('/api/nodes', methods=['GET'])
def list_nodes():
    """List all nodes with filtering"""
    try:
        service = get_node_service()

        # Get filters
        node_type = request.args.get('type')
        status = request.args.get('status')
        limit = request.args.get('limit', 100, type=int)

        nodes = []

        if node_type:
            node_type_enum = NodeType(node_type.upper())
            status_enum = NodeStatus(status.upper()) if status else None
            nodes = service.get_by_type(node_type_enum, status=status_enum, limit=limit)
        else:
            # Get all nodes
            nodes = service.get_all(limit=limit)

        return json_success_response([node.__dict__ for node in nodes])

    except Exception as e:
        logger.error(f"Error listing nodes: {e}")
        return json_error_response(str(e), status_code=500)


@node_bp.route('/api/nodes', methods=['POST'])
def create_node():
    """Create a new node"""
    try:
        service = get_node_service()
        data = request.get_json()

        if not data or not data.get('name'):
            return json_error_response('name is required', status_code=400)

        node_type = data.get('node_type', 'PROJECT').upper()
        try:
            node_type_enum = NodeType[node_type]
        except KeyError:
            return json_error_response(f'Invalid node_type: {node_type}', status_code=400)

        node = service.create(
            node_type=node_type_enum,
            name=data['name'],
            description=data.get('description'),
            parent_id=data.get('parent_id'),
            tags=data.get('tags'),
            color=data.get('color'),
            icon=data.get('icon'),
            target_date=data.get('target_date'),
            metadata=data.get('metadata')
        )

        return json_success_response(node.__dict__, status_code=201)

    except Exception as e:
        logger.error(f"Error creating node: {e}")
        return json_error_response(str(e), status_code=500)


@node_bp.route('/api/nodes/<node_id>', methods=['GET'])
def get_node(node_id: str):
    """Get node by ID"""
    try:
        service = get_node_service()
        node = service.get_by_id(node_id)

        if not node:
            return json_error_response('Node not found', 'NOT_FOUND', status_code=404)

        return json_success_response(node.__dict__)

    except Exception as e:
        logger.error(f"Error getting node: {e}")
        return json_error_response(str(e), status_code=500)


@node_bp.route('/api/nodes/<node_id>', methods=['PUT'])
def update_node(node_id: str):
    """Update node"""
    try:
        service = get_node_service()
        data = request.get_json()

        if not data:
            return json_error_response('No data provided', status_code=400)

        # Build kwargs
        kwargs = {}
        for key in ['name', 'description', 'tags', 'color', 'icon', 'target_date', 'metadata']:
            if key in data:
                kwargs[key] = data[key]

        if 'status' in data:
            try:
                kwargs['status'] = NodeStatus[data['status'].upper()]
            except KeyError:
                return json_error_response(f'Invalid status: {data["status"]}', status_code=400)

        node = service.update(node_id, **kwargs)

        if not node:
            return json_error_response('Node not found', 'NOT_FOUND', status_code=404)

        return json_success_response(node.__dict__)

    except Exception as e:
        logger.error(f"Error updating node: {e}")
        return json_error_response(str(e), status_code=500)


@node_bp.route('/api/nodes/<node_id>', methods=['DELETE'])
def delete_node(node_id: str):
    """Delete node"""
    try:
        service = get_node_service()
        cascade = request.args.get('cascade', 'false').lower() == 'true'

        success = service.delete(node_id, cascade=cascade)

        if not success:
            return json_error_response('Node not found or cannot be deleted', 'NOT_FOUND', status_code=404)

        return json_success_response({'deleted': node_id})

    except Exception as e:
        logger.error(f"Error deleting node: {e}")
        return json_error_response(str(e), status_code=500)


@node_bp.route('/api/nodes/<node_id>/contents', methods=['POST'])
def add_content_to_node(node_id: str):
    """Add content to node"""
    try:
        service = get_node_service()
        data = request.get_json()

        if not data or 'content_id' not in data:
            return json_error_response('content_id is required', status_code=400)

        success = service.add_content(node_id, data['content_id'], notes=data.get('notes'))

        if not success:
            return json_error_response('Node not found or content already associated', status_code=404)

        return json_success_response({'added': True})

    except Exception as e:
        logger.error(f"Error adding content to node: {e}")
        return json_error_response(str(e), status_code=500)


@node_bp.route('/api/nodes/<node_id>/contents/<content_id>', methods=['DELETE'])
def remove_content_from_node(node_id: str, content_id: str):
    """Remove content from node"""
    try:
        service = get_node_service()
        success = service.remove_content(node_id, content_id)

        if not success:
            return json_error_response('Association not found', 'NOT_FOUND', status_code=404)

        return json_success_response({'removed': True})

    except Exception as e:
        logger.error(f"Error removing content from node: {e}")
        return json_error_response(str(e), status_code=500)


@node_bp.route('/api/nodes/<node_id>/contents', methods=['GET'])
def get_node_contents(node_id: str):
    """Get all content for a node"""
    try:
        service = get_node_service()
        limit = request.args.get('limit', 100, type=int)
        contents = service.get_content(node_id, limit=limit)

        return json_success_response(contents)

    except Exception as e:
        logger.error(f"Error getting node contents: {e}")
        return json_error_response(str(e), status_code=500)


@node_bp.route('/api/nodes/<node_id>/stats', methods=['GET'])
def get_node_stats(node_id: str):
    """Get statistics for a node"""
    try:
        service = get_node_service()
        stats = service.get_stats(node_id)

        if not stats:
            return json_error_response('Node not found', 'NOT_FOUND', status_code=404)

        return json_success_response({
            'content_count': stats.content_count,
            'with_notes_count': stats.with_notes_count,
            'by_content_type': stats.by_content_type,
            'children_count': stats.children_count,
            'total_reading_progress': stats.total_reading_progress
        })

    except Exception as e:
        logger.error(f"Error getting node stats: {e}")
        return json_error_response(str(e), status_code=500)


@node_bp.route('/api/nodes/tree', methods=['GET'])
def get_tree():
    """Get node tree structure"""
    try:
        service = get_node_service()
        root_id = request.args.get('root_id')
        max_depth = request.args.get('max_depth', 3, type=int)

        tree = service.get_tree(root_id=root_id, max_depth=max_depth)

        return json_success_response(tree)

    except Exception as e:
        logger.error(f"Error getting tree: {e}")
        return json_error_response(str(e), status_code=500)


@node_bp.route('/api/nodes/reorder', methods=['POST'])
def reorder_nodes():
    """Reorder nodes"""
    try:
        service = get_node_service()
        data = request.get_json()

        if not data or 'orders' not in data:
            return json_error_response('orders array is required', status_code=400)

        orders = data['orders']

        for item in orders:
            node_id = item.get('node_id')
            new_parent_id = item.get('parent_id')
            new_index = item.get('order_index')

            if node_id:
                service.move(node_id, new_parent_id, new_index)

        return json_success_response({'reordered': True})

    except Exception as e:
        logger.error(f"Error reordering nodes: {e}")
        return json_error_response(str(e), status_code=500)


@node_bp.route('/api/nodes/tags', methods=['GET'])
def get_all_tags():
    """Get all unique tags"""
    try:
        service = get_node_service()
        tags = service.get_all_tags()
        return json_success_response(tags)

    except Exception as e:
        logger.error(f"Error getting tags: {e}")
        return json_error_response(str(e), status_code=500)
