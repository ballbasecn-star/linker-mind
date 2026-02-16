"""
Background Task Workers

Handles async task execution for long-running operations.
"""
import logging
from typing import Dict, Any
import time

from services.content_service import ContentService

logger = logging.getLogger(__name__)


def process_video_deep_analysis(task_id: str, url: str, enable_ai: bool = True, deep_analysis: bool = True) -> Dict[str, Any]:
    """
    Background task: Process video with deep analysis

    Args:
        task_id: Task ID
        url: URL to process
        enable_ai: Enable AI analysis
        deep_analysis: Enable deep video analysis

    Returns:
        Result dict with content_id and message
    """
    content = None

    try:
        logger.info(f"[Task {task_id}] Starting video deep analysis for: {url}")

        # Update progress - import here to get fresh connection
        from services.task_service import get_task_runner, TaskStatus
        task_runner = get_task_runner()
        task_runner.task_service.update_task(task_id, TaskStatus.PROCESSING, progress=20)

        # Process content
        service = ContentService()
        content = service.create_from_url(url, enable_ai=enable_ai, deep_analysis=deep_analysis)

        if not content:
            raise Exception("Failed to process content")

        # Update progress with fresh connection
        task_runner.task_service.update_task(task_id, TaskStatus.PROCESSING, progress=80)

        # Send notification to inbox - create new connection to avoid timeout
        try:
            from database.db_interface import get_connection
            db = get_connection()
            db.insert("inbox", {
                'id': f"inbox_msg_{task_id}",
                'raw_input': f"视频深度分析完成: {content.get('title', url)}",
                'source_type': 'system',
                'title': f"✅ 视频分析完成",
                'url': url,
                'status': 'PENDING',
                'content_id': content['id'],
                'quick_tags': '["video", "analysis_complete"]',
                'priority': 0,
                'added_at': content.get('created_at')
            })
            logger.info(f"[Task {task_id}] Notification sent to inbox")
        except Exception as e:
            logger.warning(f"[Task {task_id}] Failed to send inbox notification: {e}")

        task_runner.task_service.update_task(task_id, TaskStatus.PROCESSING, progress=100)

        return {
            'content_id': content['id'],
            'title': content.get('title'),
            'message': 'Video deep analysis completed'
        }

    except Exception as e:
        logger.error(f"[Task {task_id}] Video deep analysis failed: {e}")

        # Send failure notification to inbox - create new connection
        try:
            from database.db_interface import get_connection
            db = get_connection()
            db.insert("inbox", {
                'id': f"inbox_msg_{task_id}",
                'raw_input': f"视频深度分析失败: {url}",
                'source_type': 'system',
                'title': f"❌ 视频分析失败",
                'url': url,
                'status': 'PENDING',
                'quick_tags': '["video", "analysis_failed"]',
                'priority': 0,
                'added_at': None
            })
        except Exception:
            pass

        raise


def start_async_task(task_id: str, task_type: str, **kwargs):
    """
    Start an async task

    Args:
        task_id: Task ID
        task_type: Type of task
        **kwargs: Task arguments
    """
    from services.task_service import get_task_runner, TaskStatus
    from database.db_interface import get_connection

    # Force a fresh connection for the task
    db = get_connection()

    task_runner = get_task_runner()

    if task_type == 'video_deep_analysis':
        task_runner.run_async(
            task_id,
            process_video_deep_analysis,
            task_id,
            kwargs.get('url'),
            kwargs.get('enable_ai', True),
            kwargs.get('deep_analysis', True)
        )
    else:
        raise ValueError(f"Unknown task type: {task_type}")
