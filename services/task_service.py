"""
Task Service - Async Task Management

Handles async processing for long-running tasks like video deep analysis.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
import logging
import threading
import uuid

from database.db_interface import get_connection
from database import json_dumps

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskService:
    """Service for managing async tasks"""

    def __init__(self):
        self.db = get_connection()
        self._ensure_table()

    def _ensure_table(self):
        """Ensure tasks table exists"""
        try:
            # PostgreSQL syntax
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id VARCHAR(64) PRIMARY KEY,
                    task_type VARCHAR(50) NOT NULL,
                    url TEXT,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    metadata JSONB,
                    result JSONB,
                    error TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP WITH TIME ZONE,
                    completed_at TIMESTAMP WITH TIME ZONE
                )
            """)
            # Create indexes if not exist
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)")
        except Exception as e:
            # Table might already exist or other error
            logger.debug(f"Task table creation: {e}")

    def create_task(
        self,
        task_type: str,
        url: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Create a new task

        Args:
            task_type: Type of task (e.g., 'video_analysis')
            url: URL being processed
            metadata: Additional metadata

        Returns:
            Task ID
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"

        self.db.insert("tasks", {
            'id': task_id,
            'task_type': task_type,
            'url': url,
            'status': TaskStatus.PENDING.value,
            'metadata': json_dumps(metadata or {}),
            'result': None,
            'error': None,
            'progress': 0,
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None
        })

        logger.info(f"Created task: {task_id} ({task_type})")
        return task_id

    def update_task(
        self,
        task_id: str,
        status: TaskStatus = None,
        progress: int = None,
        result: Dict = None,
        error: str = None
    ) -> bool:
        """
        Update task status

        Args:
            task_id: Task ID
            status: New status
            progress: Progress percentage (0-100)
            result: Task result data
            error: Error message if failed

        Returns:
            True if successful
        """
        updates = {}

        if status:
            updates['status'] = status.value
            if status == TaskStatus.PROCESSING and not self.get_task(task_id).get('started_at'):
                updates['started_at'] = datetime.now().isoformat()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                updates['completed_at'] = datetime.now().isoformat()

        if progress is not None:
            updates['progress'] = progress

        if result is not None:
            updates['result'] = json_dumps(result)

        if error is not None:
            updates['error'] = error

        if not updates:
            return False

        rows = self.db.update("tasks", updates, "id = %s", (task_id,))
        return rows > 0

    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get task by ID"""
        row = self.db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if not row:
            return None

        result = dict(row)
        # Parse JSON fields
        if result.get('metadata') and isinstance(result['metadata'], str):
            from database import json_loads
            result['metadata'] = json_loads(result['metadata']) or {}
        if result.get('result') and isinstance(result['result'], str):
            from database import json_loads
            result['result'] = json_loads(result['result'])

        return result

    def get_tasks_by_status(
        self,
        status: TaskStatus,
        limit: int = 50
    ) -> List[Dict]:
        """Get tasks by status"""
        rows = self.db.fetchall(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status.value, limit)
        )
        return [dict(row) for row in rows]

    def delete_task(self, task_id: str) -> bool:
        """Delete a completed task"""
        rows = self.db.delete("tasks", "id = %s", (task_id,))
        return rows > 0

    def cleanup_old_tasks(self, days: int = 7) -> int:
        """Delete old completed/failed tasks"""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.db.delete(
            "tasks",
            "status IN (?, ?) AND created_at < ?",
            (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, cutoff)
        )
        return rows


class AsyncTaskRunner:
    """Background task runner"""

    def __init__(self):
        self.task_service = TaskService()
        self._running_tasks: Dict[str, threading.Thread] = {}

    def run_async(
        self,
        task_id: str,
        task_func,
        *args,
        **kwargs
    ):
        """
        Run a task asynchronously

        Args:
            task_id: Task ID
            task_func: Function to run
            *args, **kwargs: Arguments for the function
        """
        def task_wrapper():
            try:
                self.task_service.update_task(task_id, TaskStatus.PROCESSING, progress=10)
                result = task_func(*args, **kwargs)
                self.task_service.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    result=result
                )
                logger.info(f"Task {task_id} completed")
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                self.task_service.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    error=str(e)
                )

        thread = threading.Thread(target=task_wrapper, daemon=True)
        self._running_tasks[task_id] = thread
        thread.start()

        return task_id


# Global instance
_task_runner = None


def get_task_runner() -> AsyncTaskRunner:
    """Get global task runner instance"""
    global _task_runner
    if _task_runner is None:
        _task_runner = AsyncTaskRunner()
    return _task_runner
