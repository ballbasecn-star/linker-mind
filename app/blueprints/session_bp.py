"""
Session API Blueprint

Handles learning sessions and review scheduling.
Uses LearningSessionService for all business logic.
"""
from flask import Blueprint, request, jsonify, render_template
from typing import Optional
import logging
from datetime import datetime, timedelta

from services.session_service import LearningSessionService, LearningSession, Mood
from app.utils.api import json_success_response, json_error_response
from database.db_interface import get_connection

logger = logging.getLogger(__name__)

# Blueprint definition
session_bp = Blueprint('session', __name__)


def get_session_service():
    """Get LearningSessionService instance with current db connection"""
    return LearningSessionService()


# Page routes


@session_bp.route('/reviews')
def reviews_page():
    """Reviews page"""
    try:
        service = get_session_service()

        # Get due reviews with content info
        db = get_connection()
        now = datetime.now().isoformat()

        due_reviews = db.fetchall("""
            SELECT rs.*,
                   c.id as content_id,
                   c.title,
                   c.summary,
                   c.content_type,
                   c.reading_progress,
                   (SELECT COUNT(*) FROM learning_sessions WHERE content_id = c.id) as session_count
            FROM review_schedules rs
            JOIN contents c ON rs.content_id = c.id
            WHERE rs.next_review <= ?
            ORDER BY rs.next_review ASC
            LIMIT 20
        """, (now,))

        # Get stats
        total_due = db.fetchval("""
            SELECT COUNT(*) FROM review_schedules WHERE next_review <= ?
        """, (now,)) or 0

        return render_template('reviews.html',
                            due_reviews=[dict(row) for row in due_reviews],
                            total_due=total_due)
    except Exception as e:
        logger.error(f"Error loading reviews page: {e}")
        return render_template('reviews.html', due_reviews=[], total_due=0)


# API endpoints


@session_bp.route('/api/sessions', methods=['GET'])
def list_sessions():
    """List learning sessions"""
    try:
        service = get_session_service()

        content_id = request.args.get('content_id')
        limit = request.args.get('limit', 50, type=int)

        if content_id:
            sessions = service.get_sessions_for_content(content_id, limit=limit)
        else:
            sessions = service.get_recent_sessions(limit=limit)

        # Convert to dict
        items = []
        for session in sessions:
            d = session.__dict__.copy()
            # Parse JSON fields for API response
            if d.get('key_takeaways'):
                d['takeaways'] = d.pop('key_takeaways')
            if d.get('questions'):
                d['questions'] = d['questions']
            items.append(d)

        return json_success_response(items)

    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return json_error_response(str(e), status_code=500)


@session_bp.route('/api/sessions/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """Get session by ID"""
    try:
        service = get_session_service()
        session = service.get_session(session_id)

        if not session:
            return json_error_response('Session not found', 'NOT_FOUND', status_code=404)

        # Convert to dict
        item = session.__dict__.copy()
        # Rename key_takeaways to takeaways for API compatibility
        if item.get('key_takeaways'):
            item['takeaways'] = item.pop('key_takeaways')

        return json_success_response(item)

    except Exception as e:
        logger.error(f"Error getting session: {e}")
        return json_error_response(str(e), status_code=500)


@session_bp.route('/api/sessions/<session_id>', methods=['PUT'])
def update_session(session_id: str):
    """Update/complete a learning session"""
    try:
        service = get_session_service()
        data = request.get_json() or {}

        if not data:
            return json_error_response('No data provided', status_code=400)

        # Check if session exists
        session = service.get_session(session_id)
        if not session:
            return json_error_response('Session not found', 'NOT_FOUND', status_code=404)

        # Update session using end_session method
        duration = data.get('duration', session.duration or 0)
        comprehension = data.get('comprehension', session.comprehension or 3)
        confidence = data.get('confidence', session.confidence or 3)
        mood = data.get('mood', session.mood or Mood.CALM.value)
        key_takeaways = data.get('takeaways') or data.get('key_takeaways')
        questions = data.get('questions')

        # Get original values if not provided
        if 'takeaways' in data and 'key_takeaways' not in data:
            key_takeaways = data['takeaways']

        updated = service.end_session(
            session_id=session_id,
            duration=duration,
            comprehension=comprehension,
            confidence=confidence,
            mood=mood,
            key_takeaways=key_takeaways,
            questions=questions
        )

        # Schedule review if comprehension provided
        if 'comprehension' in data:
            service.schedule_review(session.content_id, comprehension)

        return get_session(session_id)

    except Exception as e:
        logger.error(f"Error updating session: {e}")
        return json_error_response(str(e), status_code=500)


@session_bp.route('/api/sessions/contents/<content_id>/session', methods=['POST'])
def start_session(content_id: str):
    """Start a new learning session"""
    try:
        service = get_session_service()
        db = get_connection()

        # Check if content exists
        content = db.fetchone(
            "SELECT id FROM contents WHERE id = ?",
            (content_id,)
        )

        if not content:
            return json_error_response('Content not found', 'NOT_FOUND', status_code=404)

        # Check for existing active session
        existing_sessions = service.get_sessions_for_content(content_id, limit=1)
        if existing_sessions:
            existing = existing_sessions[0]
            # Check if it's still active (no comprehension set means not ended)
            if existing.comprehension == 3 and existing.duration == 0:
                return json_success_response(existing.__dict__)

        # Create new session
        session = service.start_session(content_id)

        return json_success_response(session.__dict__, status_code=201)

    except Exception as e:
        logger.error(f"Error starting session: {e}")
        return json_error_response(str(e), status_code=500)


@session_bp.route('/api/sessions/reviews/due', methods=['GET'])
def get_due_reviews():
    """Get items due for review"""
    try:
        service = get_session_service()
        limit = request.args.get('limit', 20, type=int)

        # Get due reviews from service
        due_list = service.get_due_reviews(limit=limit)

        # Enrich with content info
        db = get_connection()
        items = []

        for content_id, schedule in due_list:
            # Get content details
            content = db.fetchone(
                "SELECT id, title, summary, content_type, reading_progress FROM contents WHERE id = ?",
                (content_id,)
            )

            if not content:
                continue

            # Get session count
            session_count = db.fetchval(
                "SELECT COUNT(*) FROM learning_sessions WHERE content_id = ?",
                (content_id,)
            ) or 0

            item = dict(content)
            item.update(schedule.__dict__)
            item['session_count'] = session_count

            # Calculate days until due
            try:
                next_review = datetime.fromisoformat(schedule.next_review)
                days_until = (next_review - datetime.now()).days
                item['days_until_due'] = days_until
                item['is_overdue'] = days_until < 0
            except:
                item['days_until_due'] = 0
                item['is_overdue'] = True

            items.append(item)

        return json_success_response(items)

    except Exception as e:
        logger.error(f"Error getting due reviews: {e}")
        return json_error_response(str(e), status_code=500)


@session_bp.route('/api/sessions/reviews/<content_id>', methods=['POST'])
def submit_review(content_id: str):
    """Submit a review and schedule next one"""
    try:
        service = get_session_service()
        data = request.get_json() or {}

        quality = data.get('quality', 3)  # 1-5 scale

        if not 1 <= quality <= 5:
            return json_error_response('quality must be between 1 and 5', status_code=400)

        # Schedule next review using service
        schedule = service.schedule_review(content_id, quality)

        return json_success_response({
            'content_id': content_id,
            'next_review': schedule.next_review,
            'interval_days': schedule.interval_days,
            'ease_factor': schedule.ease_factor,
            'review_count': schedule.review_count
        })

    except Exception as e:
        logger.error(f"Error submitting review: {e}")
        return json_error_response(str(e), status_code=500)


@session_bp.route('/api/sessions/stats/learning', methods=['GET'])
def get_learning_stats():
    """Get learning statistics"""
    try:
        service = get_session_service()
        days = request.args.get('days', 30, type=int)

        # Get overall stats
        overall = service.get_overall_stats()

        # Get learning streak
        streak = service.get_learning_streak()

        # Get mood trends
        mood_trends = service.get_mood_trends(days=days)

        # Get period-specific stats using direct query for now
        db = get_connection()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        # Reviews completed in period
        reviews_completed = db.fetchval("""
            SELECT COUNT(*) FROM review_schedules
            WHERE last_reviewed >= ?
        """, (cutoff,)) or 0

        # Notes created in period
        notes_created = db.fetchval("""
            SELECT COUNT(*) FROM notes
            WHERE created_at >= ?
        """, (cutoff,)) or 0

        # Links created in period
        links_created = db.fetchval("""
            SELECT COUNT(*) FROM links
            WHERE created_at >= ?
        """, (cutoff,)) or 0

        # Daily breakdown
        daily = db.fetchall("""
            SELECT
                DATE(started_at) as date,
                COUNT(*) as sessions,
                SUM(duration) as total_duration,
                AVG(comprehension) as avg_comprehension
            FROM learning_sessions
            WHERE started_at >= ?
            GROUP BY DATE(started_at)
            ORDER BY date DESC
            LIMIT ?
        """, (cutoff, days))

        daily_breakdown = [dict(row) for row in daily]

        return json_success_response({
            'period_days': days,
            'total_sessions': overall['total_sessions'],
            'total_duration_seconds': overall['total_duration'],
            'total_duration_hours': round(overall['total_duration'] / 3600, 2) if overall['total_duration'] else 0,
            'avg_comprehension': overall['avg_comprehension'],
            'content_studied': len(overall.get('top_content', [])),
            'reviews_completed': reviews_completed,
            'notes_created': notes_created,
            'links_created': links_created,
            'daily_breakdown': daily_breakdown,
            'streak': streak,
            'mood_trends': mood_trends
        })

    except Exception as e:
        logger.error(f"Error getting learning stats: {e}")
        return json_error_response(str(e), status_code=500)


@session_bp.route('/api/sessions/stats/content/<content_id>', methods=['GET'])
def get_content_learning_stats(content_id: str):
    """Get learning statistics for specific content"""
    try:
        service = get_session_service()
        db = get_connection()

        # Get content
        content = db.fetchone(
            "SELECT * FROM contents WHERE id = ?",
            (content_id,)
        )

        if not content:
            return json_error_response('Content not found', 'NOT_FOUND', status_code=404)

        # Get stats from service
        stats = service.get_learning_stats(content_id)

        # Get review schedule
        schedule = service.get_review_schedule(content_id)

        # Get session history
        sessions = service.get_sessions_for_content(content_id, limit=10)

        return json_success_response({
            'content_id': content_id,
            'title': content['title'],
            'session_count': stats['total_sessions'],
            'total_duration_seconds': stats['total_duration'],
            'total_duration_hours': round(stats['total_duration'] / 3600, 2) if stats['total_duration'] else 0,
            'avg_comprehension': stats['avg_comprehension'],
            'avg_confidence': stats.get('avg_confidence'),
            'max_summary_layer': max(s.summary_layer for s in sessions) if sessions else 0,
            'reading_progress': content.get('reading_progress', 0),
            'schedule': schedule.__dict__ if schedule else None,
            'sessions': [s.__dict__ for s in sessions],
            'mood_distribution': stats.get('mood_distribution', {})
        })

    except Exception as e:
        logger.error(f"Error getting content learning stats: {e}")
        return json_error_response(str(e), status_code=500)
