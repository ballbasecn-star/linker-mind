"""
Skill API Blueprint

Handles skill tree and learning path management.
Uses SkillService for all business logic.
"""
from flask import Blueprint, request, jsonify, render_template, redirect
from typing import Optional
import logging

from services.skill_service import SkillService, SkillLevel
from app.utils.api import json_success_response, json_error_response
from app.utils.pagination import get_pagination_params, Pagination

logger = logging.getLogger(__name__)

# Blueprint definition
skill_bp = Blueprint('skill', __name__)

# Initialize service
def get_skill_service():
    """Get SkillService instance"""
    return SkillService()


# Page routes


@skill_bp.route('/skills')
def skills_page():
    """Skills page"""
    try:
        service = get_skill_service()

        # Get all skills
        skills = service.list_skills(limit=100)

        # Get by category
        categories = service.get_categories()

        return render_template('skills.html',
                            skills=skills,
                            categories=categories)
    except Exception as e:
        logger.error(f"Error loading skills page: {e}")
        return render_template('skills.html', skills=[], categories=[])


@skill_bp.route('/skill_trees')
def skill_trees_legacy():
    """Legacy skill_trees route - redirects to skills"""
    return redirect('/skills')


# API endpoints


@skill_bp.route('/api/skills', methods=['GET'])
def list_skills():
    """List all skills"""
    try:
        service = get_skill_service()

        # Get filters
        category = request.args.get('category')
        level = request.args.get('level')
        limit = request.args.get('limit', 100, type=int)

        skills = service.list_skills(
            category=category,
            level=level,
            limit=limit
        )

        return json_success_response(skills)

    except Exception as e:
        logger.error(f"Error listing skills: {e}")
        return json_error_response(str(e), status_code=500)


@skill_bp.route('/api/skills', methods=['POST'])
def create_skill():
    """Create a new skill"""
    try:
        service = get_skill_service()
        data = request.get_json()

        if not data or not data.get('skill_name'):
            return json_error_response('skill_name is required', status_code=400)

        skill = service.create_skill(
            skill_name=data['skill_name'],
            category=data.get('category', 'General'),
            level=data.get('level', SkillLevel.BEGINNER),
            parent_ids=data.get('parent_ids'),
            description=data.get('description')
        )

        return json_success_response(skill, status_code=201)

    except Exception as e:
        logger.error(f"Error creating skill: {e}")
        return json_error_response(str(e), status_code=500)


@skill_bp.route('/api/skills/<skill_id>', methods=['GET'])
def get_skill(skill_id: str):
    """Get skill by ID"""
    try:
        service = get_skill_service()
        skill = service.get_skill(skill_id)

        if not skill:
            return json_error_response('Skill not found', 'NOT_FOUND', status_code=404)

        return json_success_response(skill)

    except Exception as e:
        logger.error(f"Error getting skill: {e}")
        return json_error_response(str(e), status_code=500)


@skill_bp.route('/api/skills/<skill_id>', methods=['PUT'])
def update_skill(skill_id: str):
    """Update skill"""
    try:
        service = get_skill_service()
        data = request.get_json()

        if not data:
            return json_error_response('No data provided', status_code=400)

        skill = service.update_skill(
            skill_id=skill_id,
            skill_name=data.get('skill_name'),
            category=data.get('category'),
            level=data.get('level'),
            parent_ids=data.get('parent_ids'),
            description=data.get('description')
        )

        if not skill:
            return json_error_response('Skill not found', 'NOT_FOUND', status_code=404)

        return json_success_response(skill)

    except Exception as e:
        logger.error(f"Error updating skill: {e}")
        return json_error_response(str(e), status_code=500)


@skill_bp.route('/api/skills/<skill_id>', methods=['DELETE'])
def delete_skill(skill_id: str):
    """Delete skill"""
    try:
        service = get_skill_service()
        success = service.delete_skill(skill_id)

        if not success:
            return json_error_response('Skill not found', 'NOT_FOUND', status_code=404)

        return json_success_response({'deleted': skill_id})

    except Exception as e:
        logger.error(f"Error deleting skill: {e}")
        return json_error_response(str(e), status_code=500)


@skill_bp.route('/api/skills/<skill_id>/contents', methods=['POST'])
def add_content_to_skill(skill_id: str):
    """Add content to skill learning path"""
    try:
        service = get_skill_service()
        data = request.get_json()

        if not data or 'content_id' not in data:
            return json_error_response('content_id is required', status_code=400)

        # Check if skill exists
        skill = service.get_skill(skill_id)
        if not skill:
            return json_error_response('Skill not found', 'NOT_FOUND', status_code=404)

        success = service.add_content_to_skill(
            skill_id=skill_id,
            content_id=data['content_id'],
            order_index=data.get('order_index')
        )

        if not success:
            return json_error_response('Content already added to skill or skill not found', status_code=400)

        return json_success_response({'added': True})

    except Exception as e:
        logger.error(f"Error adding content to skill: {e}")
        return json_error_response(str(e), status_code=500)


@skill_bp.route('/api/skills/tree', methods=['GET'])
def get_skill_tree():
    """Get skill tree structure"""
    try:
        service = get_skill_service()
        tree = service.get_skill_tree()

        return json_success_response(tree)

    except Exception as e:
        logger.error(f"Error getting skill tree: {e}")
        return json_error_response(str(e), status_code=500)


@skill_bp.route('/api/skills/<skill_id>/path', methods=['GET'])
def get_learning_path(skill_id: str):
    """Get learning path for a skill"""
    try:
        service = get_skill_service()
        path = service.get_learning_path(skill_id)

        return json_success_response(path)

    except Exception as e:
        logger.error(f"Error getting learning path: {e}")
        return json_error_response(str(e), status_code=500)


@skill_bp.route('/api/skills/<skill_id>/resources/<content_id>', methods=['PUT'])
def update_skill_resource(skill_id: str, content_id: str):
    """Update skill resource (mark complete, reorder, etc.)"""
    try:
        service = get_skill_service()
        data = request.get_json() or {}

        if 'completed' in data:
            service.update_resource_progress(
                skill_id=skill_id,
                content_id=content_id,
                completed=data['completed']
            )

            return json_success_response({'updated': True})

        return json_error_response('No valid fields to update', status_code=400)

    except Exception as e:
        logger.error(f"Error updating skill resource: {e}")
        return json_error_response(str(e), status_code=500)


@skill_bp.route('/api/skills/categories', methods=['GET'])
def get_skill_categories():
    """Get all skill categories"""
    try:
        service = get_skill_service()
        categories = service.get_categories()

        return json_success_response(categories)

    except Exception as e:
        logger.error(f"Error getting skill categories: {e}")
        return json_error_response(str(e), status_code=500)


@skill_bp.route('/api/skills/stats', methods=['GET'])
def get_skill_stats():
    """Get skill statistics"""
    try:
        service = get_skill_service()
        stats = service.get_stats()

        return json_success_response(stats)

    except Exception as e:
        logger.error(f"Error getting skill stats: {e}")
        return json_error_response(str(e), status_code=500)
