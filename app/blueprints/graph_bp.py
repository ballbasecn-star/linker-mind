"""
Graph API Blueprint

Handles knowledge graph visualization and analysis.
Uses KnowledgeGraphService for all business logic.
"""
from flask import Blueprint, request, jsonify, render_template, redirect
from typing import Optional
import logging
from datetime import datetime, timedelta

from services.graph_service import KnowledgeGraphService, GraphType, NodeType
from app.utils.api import json_success_response, json_error_response

logger = logging.getLogger(__name__)

# Blueprint definition
graph_bp = Blueprint('graph', __name__)


def get_graph_service():
    """Get KnowledgeGraphService instance"""
    return KnowledgeGraphService()


# Page routes


@graph_bp.route('/graph')
def graph_page():
    """Knowledge graph visualization page"""
    try:
        return render_template('graph.html')
    except Exception as e:
        logger.error(f"Error loading graph page: {e}")
        return render_template('error.html', error=str(e))


@graph_bp.route('/knowledge_graph')
def knowledge_graph_legacy():
    """Legacy knowledge_graph route - redirects to graph"""
    return redirect('/graph')


# API endpoints


@graph_bp.route('/api/graph', methods=['GET'])
def get_graph():
    """Get force-directed graph data"""
    try:
        service = get_graph_service()
        limit = request.args.get('limit', 100, type=int)
        min_weight = request.args.get('min_weight', 0.1, type=float)

        graph = service.get_force_directed_graph(limit=limit, min_weight=min_weight)

        # Convert to API format
        nodes = []
        for node in graph.nodes:
            nodes.append({
                'id': node.id,
                'label': node.label,
                'type': node.node_type,
                'size': max(5, min(30, node.size * 10)),
                'color': node.color,
                'connection_count': int(node.size * 5)  # Approximate
            })

        links = []
        for edge in graph.edges:
            links.append({
                'source': edge.source,
                'target': edge.target,
                'label': edge.label or 'related',
                'strength': edge.weight
            })

        return json_success_response({
            'nodes': nodes,
            'links': links,
            'metadata': {
                'node_count': len(nodes),
                'link_count': len(links)
            }
        })

    except Exception as e:
        logger.error(f"Error getting graph: {e}")
        return json_error_response(str(e), status_code=500)


@graph_bp.route('/api/graph/cluster', methods=['GET'])
def get_topic_clusters():
    """Get topic clusters"""
    try:
        service = get_graph_service()
        min_cluster_size = request.args.get('min_size', 3, type=int)

        clusters = service.get_topic_clusters(min_cluster_size=min_cluster_size)

        # Convert to API format
        result = []
        for cluster in clusters:
            result.append({
                'topic': cluster.get('topics', ['Unknown'])[0] if cluster.get('topics') else 'Unknown',
                'size': cluster.get('content_count', 0),
                'items': cluster.get('sample_content', [])[:10]
            })

        return json_success_response(result[:20])

    except Exception as e:
        logger.error(f"Error getting clusters: {e}")
        return json_error_response(str(e), status_code=500)


@graph_bp.route('/api/graph/path', methods=['GET'])
def get_shortest_path():
    """Get shortest path between two nodes"""
    try:
        service = get_graph_service()
        source_id = request.args.get('from')
        target_id = request.args.get('to')
        max_depth = request.args.get('max_depth', 5, type=int)

        if not source_id or not target_id:
            return json_error_response('from and to parameters are required', status_code=400)

        if source_id == target_id:
            return json_success_response({
                'path': [{'id': source_id, 'position': 0}],
                'length': 0
            })

        # Find path using service
        from services.graph_service import SkillTreeNode

        # Try to find learning path (closest thing to shortest path in current service)
        # Note: The service's get_learning_path is for skills, not general content
        # So we'll do a simple BFS approach here

        # For now, return that the service needs enhancement
        # Or use get_node_connections to show connectivity

        graph_data = service.get_node_connections(source_id, depth=max_depth)

        # Check if target is in the connected nodes
        target_found = False
        for node in graph_data.nodes:
            if node.id == target_id:
                target_found = True
                break

        if target_found:
            # Build path from edges
            path = [{'id': source_id, 'position': 0}]
            # Simple path extraction (could be improved)
            for i, node in enumerate(graph_data.nodes):
                if node.id == target_id:
                    path.append({'id': node.id, 'position': i + 1})
                    break

            return json_success_response({
                'path': path,
                'length': len(path) - 1
            })

        return json_success_response({
            'path': None,
            'message': 'No path found'
        })

    except Exception as e:
        logger.error(f"Error finding path: {e}")
        return json_error_response(str(e), status_code=500)


@graph_bp.route('/api/graph/timeline', methods=['GET'])
def get_graph_timeline():
    """Get timeline data for graph visualization"""
    try:
        service = get_graph_service()
        days = request.args.get('days', 30, type=int)

        timeline = service.get_timeline(days=days)

        return json_success_response({
            'items': timeline,
            'period_days': days
        })

    except Exception as e:
        logger.error(f"Error getting timeline: {e}")
        return json_error_response(str(e), status_code=500)


@graph_bp.route('/api/graph/connections/<node_id>', methods=['GET'])
def get_node_connections(node_id: str):
    """Get detailed connections for a node"""
    try:
        service = get_graph_service()
        depth = request.args.get('depth', 2, type=int)
        max_nodes = request.args.get('max_nodes', 50, type=int)

        graph = service.get_node_connections(node_id, depth=depth)

        # Convert to API format
        nodes_list = []
        for node in graph.nodes:
            nodes_list.append({
                'id': node.id,
                'title': node.label,
                'content_type': node.node_type,
                'depth': graph.metadata.get('depth', 0) if node.id == node_id else 1
            })

        links_list = []
        for edge in graph.edges:
            links_list.append({
                'source': edge.source,
                'target': edge.target,
                'type': edge.label or 'related'
            })

        center_node = next((n for n in nodes_list if n['id'] == node_id), None)

        return json_success_response({
            'nodes': nodes_list[:max_nodes],
            'links': links_list,
            'center_node': center_node,
            'total_nodes': len(nodes_list),
            'total_links': len(links_list)
        })

    except Exception as e:
        logger.error(f"Error getting node connections: {e}")
        return json_error_response(str(e), status_code=500)


@graph_bp.route('/api/graph/stats', methods=['GET'])
def get_graph_stats():
    """Get graph statistics"""
    try:
        service = get_graph_service()
        stats = service.get_statistics()

        return json_success_response({
            'nodes': {
                'total_content': stats.get('content_nodes', 0),
                'total_notes': stats.get('note_nodes', 0),
                'total_organization_nodes': stats.get('skill_nodes', 0),
                'total': stats.get('total_nodes', 0)
            },
            'links': {
                'total': stats.get('total_edges', 0),
                'avg_connections_per_node': stats.get('avg_connections', 0)
            },
            'most_connected': stats.get('most_connected', [])
        })

    except Exception as e:
        logger.error(f"Error getting graph stats: {e}")
        return json_error_response(str(e), status_code=500)
