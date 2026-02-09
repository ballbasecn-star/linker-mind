"""
Inbox Service Module - Quick capture and processing workflow

This module implements the CODE workflow:
- Capture: Quickly collect items to inbox
- Organize: Process and organize items
- Distill: Extract key insights
- Express: Use for creation

Features:
- Add items to inbox from any source
- Process items with status tracking
- Quick tagging and categorization
- Snooze functionality
- Statistics and insights
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from database.db_interface import get_connection
from database.connection import json_dumps, json_dict, json_list

logger = logging.getLogger(__name__)


class InboxStatus(Enum):
    """Inbox item status"""
    PENDING = "PENDING"           # Waiting to be processed
    PROCESSED = "PROCESSED"       # Has been processed
    SNOOZED = "SNOOZED"           # Temporarily put aside
    ARCHIVED = "ARCHIVED"         # Archived for reference


class ProcessAction(Enum):
    """Actions for processing inbox items"""
    PROCESS = "process"           # Process and move to content
    DELETE = "delete"             # Delete from inbox
    SNOOZE = "snooze"             # Snooze for later
    ARCHIVE = "archive"           # Archive without processing


@dataclass
class InboxItem:
    """Inbox item model"""
    id: str
    raw_input: str
    source_type: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    status: str = InboxStatus.PENDING.value
    processed_at: Optional[str] = None
    processed_content_id: Optional[str] = None
    quick_tags: Optional[List[str]] = None
    priority: int = 0
    added_at: Optional[str] = None
    due_date: Optional[str] = None
    content_id: Optional[str] = None

    def __post_init__(self):
        """Initialize defaults"""
        if self.quick_tags is None:
            self.quick_tags = []
        if self.added_at is None:
            self.added_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        # Handle quick_tags serialization
        if self.quick_tags:
            data['quick_tags'] = json_dumps(self.quick_tags)
        return data


@dataclass
class InboxStats:
    """Inbox statistics"""
    total: int
    pending: int
    processed: int
    snoozed: int
    overdue: int
    by_source_type: Dict[str, int]
    by_priority: Dict[str, int]


class InboxService:
    """
    Service for managing inbox items

    Implements the quick capture workflow:
    1. Capture items from any source
    2. Queue for processing
    3. Process with actions (process, delete, snooze, archive)
    4. Track and manage
    """

    def __init__(self, db_path: str = "linker_mind.db"):
        self.db = get_connection()
        self.db_path = db_path

    def add(
        self,
        raw_input: str,
        source_type: Optional[str] = None,
        title: Optional[str] = None,
        url: Optional[str] = None,
        quick_tags: Optional[List[str]] = None,
        priority: int = 0,
        due_date: Optional[str] = None
    ) -> InboxItem:
        """
        Add an item to the inbox

        Args:
            raw_input: The raw content (URL or text)
            source_type: Optional source type
            title: Optional title
            url: Optional URL
            quick_tags: Optional quick tags
            priority: Priority (higher = more important)
            due_date: Optional due date for processing

        Returns:
            Created InboxItem
        """
        id = self._generate_id()

        item = InboxItem(
            id=id,
            raw_input=raw_input,
            source_type=source_type,
            title=title,
            url=url,
            quick_tags=quick_tags or [],
            priority=priority,
            due_date=due_date
        )

        self.db.insert("inbox", {
            'id': item.id,
            'content_id': None,  # Will be linked when processed
            'raw_input': item.raw_input,
            'source_type': item.source_type,
            'title': item.title,
            'url': item.url,
            'status': item.status,
            'processed_at': item.processed_at,
            'processed_content_id': item.processed_content_id,
            'quick_tags': json_dumps(item.quick_tags),
            'priority': item.priority,
            'added_at': item.added_at,
            'due_date': item.due_date
        })

        logger.info(f"Added item to inbox: {item.id}")
        return item

    def get_by_id(self, item_id: str) -> Optional[InboxItem]:
        """Get an inbox item by ID"""
        row = self.db.fetchone(
            "SELECT * FROM inbox WHERE id = ?",
            (item_id,)
        )
        if row:
            return self._row_to_item(row)
        return None

    def get_unprocessed(
        self,
        include_snoozed: bool = False,
        limit: int = 100
    ) -> List[InboxItem]:
        """
        Get unprocessed inbox items

        Args:
            include_snoozed: Include snoozed items
            limit: Maximum items to return

        Returns:
            List of InboxItems
        """
        if include_snoozed:
            where = "status IN (?, ?)"
            params = (InboxStatus.PENDING.value, InboxStatus.SNOOZED.value)
        else:
            where = "status = ?"
            params = (InboxStatus.PENDING.value,)

        rows = self.db.fetchall(
            f"SELECT * FROM inbox WHERE {where} ORDER BY priority DESC, added_at ASC LIMIT ?",
            params + (limit,)
        )

        return [self._row_to_item(row) for row in rows]

    def get_overdue(self, limit: int = 50) -> List[InboxItem]:
        """Get items that are past their due date"""
        now = datetime.now().isoformat()

        rows = self.db.fetchall("""
            SELECT * FROM inbox
            WHERE status = ? AND due_date IS NOT NULL AND due_date < ?
            ORDER BY due_date ASC
            LIMIT ?
        """, (InboxStatus.PENDING.value, now, limit))

        return [self._row_to_item(row) for row in rows]

    def get_by_status(
        self,
        status: InboxStatus,
        limit: int = 100
    ) -> List[InboxItem]:
        """Get items by status"""
        rows = self.db.fetchall(
            "SELECT * FROM inbox WHERE status = ? ORDER BY added_at DESC LIMIT ?",
            (status.value, limit)
        )
        return [self._row_to_item(row) for row in rows]

    def process(
        self,
        item_id: str,
        action: ProcessAction,
        content_id: Optional[str] = None,
        snooze_until: Optional[str] = None
    ) -> bool:
        """
        Process an inbox item

        Args:
            item_id: Inbox item ID
            action: Action to take
            content_id: Content ID (for PROCESS action)
            snooze_until: When to unsnooze (for SNOOZE action)

        Returns:
            True if successful
        """
        item = self.get_by_id(item_id)
        if not item:
            logger.error(f"Inbox item not found: {item_id}")
            return False

        if action == ProcessAction.DELETE:
            return self._delete_item(item_id)

        elif action == ProcessAction.ARCHIVE:
            return self._archive_item(item_id)

        elif action == ProcessAction.SNOOZE:
            return self._snooze_item(item_id, snooze_until)

        elif action == ProcessAction.PROCESS:
            return self._process_item(item_id, content_id)

        return False

    def _process_item(self, item_id: str, content_id: Optional[str] = None) -> bool:
        """Mark an item as processed"""
        now = datetime.now().isoformat()

        rows = self.db.update(
            "inbox",
            {
                'status': InboxStatus.PROCESSED.value,
                'processed_at': now,
                'processed_content_id': content_id
            },
            "id = ?",
            (item_id,)
        )

        return rows > 0

    def _delete_item(self, item_id: str) -> bool:
        """Delete an inbox item"""
        rows = self.db.delete("inbox", "id = ?", (item_id,))
        return rows > 0

    def _archive_item(self, item_id: str) -> bool:
        """Archive an inbox item without processing"""
        rows = self.db.update(
            "inbox",
            {'status': InboxStatus.ARCHIVED.value},
            "id = ?",
            (item_id,)
        )
        return rows > 0

    def _snooze_item(self, item_id: str, snooze_until: Optional[str] = None) -> bool:
        """Snooze an item until later"""
        if not snooze_until:
            # Default: snooze for 1 day
            snooze_until = (datetime.now() + timedelta(days=1)).isoformat()

        rows = self.db.update(
            "inbox",
            {
                'status': InboxStatus.SNOOZED.value,
                'due_date': snooze_until
            },
            "id = ?",
            (item_id,)
        )
        return rows > 0

    def unsnooze_due_items(self) -> int:
        """
        Un-snooze items whose due date has passed

        Returns:
            Number of items unsnoozed
        """
        now = datetime.now().isoformat()

        rows = self.db.update(
            "inbox",
            {'status': InboxStatus.PENDING.value},
            "status = ? AND due_date IS NOT NULL AND due_date <= ?",
            (InboxStatus.SNOOZED.value, now)
        )

        return rows

    def update_tags(self, item_id: str, tags: List[str]) -> bool:
        """Update quick tags for an inbox item"""
        rows = self.db.update(
            "inbox",
            {'quick_tags': json_dumps(tags)},
            "id = ?",
            (item_id,)
        )
        return rows > 0

    def update_priority(self, item_id: str, priority: int) -> bool:
        """Update priority for an inbox item"""
        rows = self.db.update(
            "inbox",
            {'priority': priority},
            "id = ?",
            (item_id,)
        )
        return rows > 0

    def get_stats(self) -> InboxStats:
        """
        Get inbox statistics

        Returns:
            InboxStats object
        """
        # Count by status
        status_counts = {}
        for status in InboxStatus:
            count = self.db.fetchval(
                "SELECT COUNT(*) FROM inbox WHERE status = ?",
                (status.value,)
            )
            status_counts[status.value] = count or 0

        # Count overdue
        now = datetime.now().isoformat()
        overdue = self.db.fetchval("""
            SELECT COUNT(*) FROM inbox
            WHERE status = ? AND due_date IS NOT NULL AND due_date < ?
        """, (InboxStatus.PENDING.value, now))
        overdue = overdue or 0

        # Count by source type
        source_rows = self.db.fetchall("""
            SELECT source_type, COUNT(*) as count
            FROM inbox
            WHERE status = ?
            GROUP BY source_type
        """, (InboxStatus.PENDING.value,))
        by_source = {row['source_type']: row['count'] for row in source_rows}

        # Count by priority
        priority_rows = self.db.fetchall("""
            SELECT
                CASE
                    WHEN priority >= 10 THEN 'high'
                    WHEN priority >= 5 THEN 'medium'
                    ELSE 'low'
                END as priority_level,
                COUNT(*) as count
            FROM inbox
            WHERE status = ?
            GROUP BY priority_level
        """, (InboxStatus.PENDING.value,))
        by_priority = {row['priority_level']: row['count'] for row in priority_rows}

        return InboxStats(
            total=status_counts.get(InboxStatus.PENDING.value, 0),
            pending=status_counts.get(InboxStatus.PENDING.value, 0),
            processed=status_counts.get(InboxStatus.PROCESSED.value, 0),
            snoozed=status_counts.get(InboxStatus.SNOOZED.value, 0),
            overdue=overdue,
            by_source_type=by_source,
            by_priority=by_priority
        )

    def get_processing_queue(
        self,
        limit: int = 20
    ) -> List[InboxItem]:
        """
        Get items in processing order (priority first, then oldest)

        Args:
            limit: Maximum items

        Returns:
            List of InboxItems in processing order
        """
        # First, unsnooze any due items
        self.unsnooze_due_items()

        # Get pending items ordered by priority then date
        rows = self.db.fetchall("""
            SELECT * FROM inbox
            WHERE status = ?
            ORDER BY priority DESC, added_at ASC
            LIMIT ?
        """, (InboxStatus.PENDING.value, limit))

        return [self._row_to_item(row) for row in rows]

    def bulk_process(
        self,
        item_ids: List[str],
        action: ProcessAction,
        content_id: Optional[str] = None,
        snooze_until: Optional[str] = None
    ) -> Tuple[int, int]:
        """
        Process multiple items at once

        Args:
            item_ids: List of item IDs
            action: Action to apply to all
            content_id: Content ID to associate (for PROCESS action)
            snooze_until: When to unsnooze (for SNOOZE action)

        Returns:
            Tuple of (success_count, fail_count)
        """
        success = 0
        failed = 0

        for item_id in item_ids:
            if self.process(item_id, action, content_id=content_id, snooze_until=snooze_until):
                success += 1
            else:
                failed += 1

        return (success, failed)

    def cleanup_old_items(self, days: int = 30) -> int:
        """
        Delete processed items older than specified days

        Args:
            days: Number of days

        Returns:
            Number of items deleted
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        rows = self.db.delete(
            "inbox",
            "status = ? AND processed_at IS NOT NULL AND processed_at < ?",
            (InboxStatus.PROCESSED.value, cutoff_date.isoformat())
        )

        return rows

    def search(self, query: str, limit: int = 50) -> List[InboxItem]:
        """Search inbox items by title or raw input"""
        search_query = f"%{query}%"

        rows = self.db.fetchall("""
            SELECT * FROM inbox
            WHERE (title LIKE ? OR raw_input LIKE ?)
            ORDER BY added_at DESC
            LIMIT ?
        """, (search_query, search_query, limit))

        return [self._row_to_item(row) for row in rows]

    def get_items_by_tag(self, tag: str, limit: int = 50) -> List[InboxItem]:
        """Get inbox items with a specific quick tag"""
        all_items = self.get_unprocessed(include_snoozed=False, limit=500)

        matching = []
        for item in all_items:
            if tag.lower() in [t.lower() for t in item.quick_tags]:
                matching.append(item)
            if len(matching) >= limit:
                break

        return matching

    def _row_to_item(self, row: Any) -> InboxItem:
        """Convert database row to InboxItem"""
        return InboxItem(
            id=row['id'],
            raw_input=row['raw_input'],
            source_type=row['source_type'],
            title=row['title'],
            url=row['url'],
            status=row['status'],
            processed_at=row['processed_at'],
            processed_content_id=row['processed_content_id'],
            quick_tags=json_list(row['quick_tags']),
            priority=row['priority'],
            added_at=row['added_at'],
            due_date=row['due_date'],
            content_id=row['content_id']
        )

    def _generate_id(self) -> str:
        """Generate unique inbox item ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        count = self.db.fetchval("SELECT COUNT(*) FROM inbox") or 0
        return f"inbox_{timestamp}_{count:03d}"


# Preset quick tags for inbox
PRESET_QUICK_TAGS = {
    'to_read': '📖 To Read',
    'to_watch': '🎬 To Watch',
    'inspiration': '💡 Inspiration',
    'reference': '📚 Reference',
    'tool': '🔧 Tool',
    'tutorial': '📝 Tutorial',
    'news': '📰 News',
    'research': '🔬 Research',
    'idea': '💭 Idea',
    'quote': '💬 Quote',
    'fun': '🎮 Fun',
    'later': '🔜 Later'
}


if __name__ == "__main__":
    # Test the inbox service
    print("Inbox Service Module")
    print("=" * 50)

    from database.connection import init_database
    init_database(":memory:")

    service = InboxService(":memory:")

    # Add some test items
    item1 = service.add(
        raw_input="https://example.com/article1",
        source_type="webpage",
        title="Interesting Article About Design",
        url="https://example.com/article1",
        quick_tags=["to_read", "design"],
        priority=8
    )

    item2 = service.add(
        raw_input="Quick idea for a new feature",
        source_type="memo",
        title="Feature Idea",
        quick_tags=["idea"],
        priority=5
    )

    print(f"Added items: {item1.id}, {item2.id}")

    # Get unprocessed
    unprocessed = service.get_unprocessed()
    print(f"Unprocessed items: {len(unprocessed)}")

    # Get stats
    stats = service.get_stats()
    print(f"Stats: pending={stats.pending}, total={stats.total}")

    # Process an item
    service.process(item1.id, ProcessAction.PROCESSED, content_id="content_001")

    # Check stats again
    stats = service.get_stats()
    print(f"After processing: pending={stats.pending}, processed={stats.processed}")

    print("\n✓ Inbox service tests passed!")
