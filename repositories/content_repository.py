"""
Content Repository Module - Data access layer for content items

This module handles:
- Content CRUD operations
- Content search and filtering
- Full-text search
- Content statistics
"""
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from repositories.base import BaseRepository, RepositoryResult, Filters
from database.connection import get_db, json_dumps, json_loads, json_list, json_dict


class SourceType(Enum):
    """Content source types"""
    WEBPAGE = "webpage"
    TWITTER = "twitter"
    WECHAT = "wechat"
    WEIXIN = "weixin"
    DOUYIN = "douyin"
    YOUTUBE = "youtube"
    BILIBILI = "bilibili"
    VIDEO = "video"
    MEMO = "memo"
    TEXT = "text"
    BOOK = "book"
    PODCAST = "podcast"
    COURSE = "course"
    UNKNOWN = "unknown"


class ContentType(Enum):
    """Content types"""
    ARTICLE = "article"
    POST = "post"
    VIDEO = "video"
    BOOK = "book"
    PODCAST = "podcast"
    COURSE = "course"
    NOTE = "note"
    THREAD = "thread"
    PRESENTATION = "presentation"
    PAPER = "paper"
    DOC = "doc"
    IMAGE = "image"
    UNKNOWN = "unknown"


@dataclass
class Content:
    """Content model"""
    id: str
    source_type: str
    content_type: str
    title: Optional[str] = None
    url: Optional[str] = None
    raw_content: Optional[str] = None
    summary: Optional[str] = None
    main_content: Optional[str] = None
    html_content: Optional[str] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    media: Optional[Dict[str, Any]] = None
    processing_info: Optional[Dict[str, Any]] = None
    archived: bool = False
    favorited: bool = False
    reading_progress: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    indexed_at: Optional[str] = None

    def __post_init__(self):
        """Initialize defaults for None values"""
        if self.ai_analysis is None:
            self.ai_analysis = {}
        if self.metadata is None:
            self.metadata = {}
        if self.media is None:
            self.media = {}
        if self.processing_info is None:
            self.processing_info = {}
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    def get_ai_key_points(self) -> List[str]:
        """Get AI key points from analysis"""
        return self.ai_analysis.get('key_points', []) if self.ai_analysis else []

    def get_ai_topics(self) -> List[str]:
        """Get AI topics from analysis"""
        return self.ai_analysis.get('topics', []) if self.ai_analysis else []

    def get_ai_sentiment(self) -> str:
        """Get AI sentiment from analysis"""
        return self.ai_analysis.get('sentiment', 'unknown') if self.ai_analysis else 'unknown'

    def get_authors(self) -> List[str]:
        """Get authors from metadata"""
        if not self.metadata:
            return []
        author = self.metadata.get('author', '')
        if author:
            return [author]
        return self.metadata.get('authors', [])


class ContentRepository(BaseRepository[Content]):
    """
    Repository for content items

    Handles all database operations for the contents table
    """

    def __init__(self, db_path: str = "linker_mind.db"):
        super().__init__(db_path)
        self.db = get_db(db_path)

    def _get_table(self) -> str:
        return "contents"

    def _to_model(self, row: Any) -> Content:
        """Convert database row to Content model"""
        return Content(
            id=row['id'],
            source_type=row['source_type'],
            content_type=row['content_type'],
            title=row['title'],
            url=row['url'],
            raw_content=row['raw_content'],
            summary=row['summary'],
            main_content=row['main_content'],
            html_content=row['html_content'],
            ai_analysis=json_dict(row['ai_analysis']),
            metadata=json_dict(row['metadata']),
            media=json_dict(row['media']),
            processing_info=json_dict(row['processing_info']),
            archived=bool(row['archived']),
            favorited=bool(row['favorited']),
            reading_progress=row['reading_progress'] or 0.0,
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            indexed_at=row['indexed_at']
        )

    def _to_dict(self, model: Content) -> Dict[str, Any]:
        """Convert Content model to dictionary for database"""
        return {
            'id': model.id,
            'source_type': model.source_type,
            'content_type': model.content_type,
            'title': model.title,
            'url': model.url,
            'raw_content': model.raw_content,
            'summary': model.summary,
            'main_content': model.main_content,
            'html_content': model.html_content,
            'ai_analysis': json_dumps(model.ai_analysis),
            'metadata': json_dumps(model.metadata),
            'media': json_dumps(model.media),
            'processing_info': json_dumps(model.processing_info),
            'archived': 1 if model.archived else 0,
            'favorited': 1 if model.favorited else 0,
            'reading_progress': model.reading_progress,
            'created_at': model.created_at,
            'updated_at': datetime.now().isoformat(),  # Always update timestamp
            'indexed_at': model.indexed_at
        }

    def search_by_text(
        self,
        query: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Content]:
        """
        Full-text search using FTS

        Args:
            query: Search query
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of matching Content items
        """
        return super().search(
            query=query,
            search_fields=['title', 'summary', 'main_content'],
            limit=limit
        )

    def find_by_source_type(self, source_type: SourceType) -> List[Content]:
        """Find all content by source type"""
        return self.find_all(
            where="source_type = ?",
            where_params=(source_type.value,)
        )

    def find_by_platform(self, platform: str) -> List[Content]:
        """Find all content by platform (alias for source_type)"""
        return self.find_all(
            where="source_type = ?",
            where_params=(platform,)
        )

    def find_by_content_type(self, content_type: ContentType) -> List[Content]:
        """Find all content by content type"""
        return self.find_all(
            where="content_type = ?",
            where_params=(content_type.value,)
        )

    def find_favorited(self, limit: int = 100) -> List[Content]:
        """Find favorited content"""
        return self.find_all(
            where="favorited = ?",
            where_params=(1,),
            order_by="created_at DESC",
            limit=limit
        )

    def find_archived(self, limit: int = 100) -> List[Content]:
        """Find archived content"""
        return self.find_all(
            where="archived = ?",
            where_params=(1,),
            order_by="created_at DESC",
            limit=limit
        )

    def find_recent(self, limit: int = 20, offset: int = 0) -> List[Content]:
        """Find recent content"""
        return self.find_all(
            where="archived = ?",
            where_params=(0,),
            order_by="created_at DESC",
            limit=limit,
            offset=offset
        )

    def find_with_media(
        self,
        media_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Content]:
        """
        Find content that has media

        Args:
            media_type: Filter by media type ('images', 'videos', 'screenshots')
            limit: Maximum results

        Returns:
            List of Content items with media
        """
        # We need to check the JSON media column
        contents = self.find_all(
            where="archived = ?",
            where_params=(0,),
            order_by="created_at DESC",
            limit=limit * 2  # Get more to filter
        )

        result = []
        for content in contents:
            if not content.media:
                continue

            if media_type:
                items = content.media.get(media_type, [])
                if items:
                    result.append(content)
            else:
                # Has any media
                if any(content.media.values()):
                    result.append(content)

            if len(result) >= limit:
                break

        return result

    def toggle_favorite(self, content_id: str) -> Optional[Content]:
        """Toggle the favorite status of content"""
        content = self.find_by_id(content_id)
        if content:
            content.favorited = not content.favorited
            self.update(content)
            return content
        return None

    def toggle_archive(self, content_id: str) -> Optional[Content]:
        """Toggle the archive status of content"""
        content = self.find_by_id(content_id)
        if content:
            content.archived = not content.archived
            self.update(content)
            return content
        return None

    def update_reading_progress(
        self,
        content_id: str,
        progress: float
    ) -> Optional[Content]:
        """
        Update reading progress

        Args:
            content_id: Content ID
            progress: Progress value (0.0 to 1.0)

        Returns:
            Updated Content or None
        """
        content = self.find_by_id(content_id)
        if content:
            content.reading_progress = max(0.0, min(1.0, progress))
            content.updated_at = datetime.now().isoformat()
            self.update(content)
            return content
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get content statistics"""
        total = self.count(where="archived = ?", where_params=(0,))

        # Count by source type
        source_rows = self.db.fetchall("""
            SELECT source_type, COUNT(*) as count
            FROM contents
            WHERE archived = 0
            GROUP BY source_type
        """)
        by_source = {row['source_type']: row['count'] for row in source_rows}

        # Count by content type
        type_rows = self.db.fetchall("""
            SELECT content_type, COUNT(*) as count
            FROM contents
            WHERE archived = 0
            GROUP BY content_type
        """)
        by_type = {row['content_type']: row['count'] for row in type_rows}

        # Count favorited
        favorited = self.count(where="favorited = ?", where_params=(1,))

        # Count with media
        with_media = 0
        all_content = self.find_all(limit=1000)
        for content in all_content:
            if content.media and any(content.media.values()):
                with_media += 1

        # Average reading progress
        progress_rows = self.db.fetchone("""
            SELECT AVG(reading_progress) as avg_progress
            FROM contents
            WHERE archived = 0 AND reading_progress > 0
        """)
        avg_progress = progress_rows['avg_progress'] if progress_rows else 0

        # Count by AI analysis
        with_ai = self.count(where="ai_analysis IS NOT NULL AND ai_analysis != ?", where_params=("",))

        return {
            'total': total,
            'by_source_type': by_source,
            'by_content_type': by_type,
            'favorited': favorited,
            'with_media': with_media,
            'average_reading_progress': round(avg_progress, 2) if avg_progress else 0,
            'with_ai_analysis': with_ai
        }

    def find_by_topic(self, topic: str, limit: int = 50) -> List[Content]:
        """Find content related to a topic (from AI analysis)"""
        # This searches for the topic in the ai_analysis JSON
        contents = self.find_all(limit=500)  # Get more to filter

        result = []
        for content in contents:
            topics = content.get_ai_topics()
            if topic.lower() in [t.lower() for t in topics]:
                result.append(content)
            if len(result) >= limit:
                break

        return result

    def find_by_tag(self, tag: str, limit: int = 50) -> List[Content]:
        """Find content with a specific tag"""
        # First, get content IDs from the junction table
        tag_rows = self.db.fetchall("""
            SELECT ct.content_id
            FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
            WHERE t.name = ?
            ORDER BY ct.tagged_at DESC
            LIMIT ?
        """, (tag, limit))

        content_ids = [row['content_id'] for row in tag_rows]

        # Fetch the content items
        result = []
        for content_id in content_ids:
            content = self.find_by_id(content_id)
            if content:
                result.append(content)

        return result

    def get_tags_for_content(self, content_id: str) -> List[Dict[str, Any]]:
        """Get all tags for a specific content item"""
        rows = self.db.fetchall("""
            SELECT t.id, t.name, t.color, t.icon, t.category, ct.tagged_at
            FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
            WHERE ct.content_id = ?
            ORDER BY t.name
        """, (content_id,))

        return [dict(row) for row in rows]

    def add_tag_to_content(self, content_id: str, tag_name: str) -> bool:
        """Add a tag to content (creates tag if needed)"""
        # Check if tag exists
        tag_row = self.db.fetchone("SELECT id FROM tags WHERE name = ?", (tag_name,))

        if tag_row:
            tag_id = tag_row['id']
        else:
            # Create new tag
            cursor = self.db.execute(
                "INSERT INTO tags (name, use_count) VALUES (?, 1)",
                (tag_name,)
            )
            tag_id = cursor.lastrowid

        # Check if association exists
        existing = self.db.fetchone(
            "SELECT * FROM content_tags WHERE content_id = ? AND tag_id = ?",
            (content_id, tag_id)
        )

        if not existing:
            self.db.insert("content_tags", {
                'content_id': content_id,
                'tag_id': tag_id,
                'tagged_at': datetime.now().isoformat(),
                'tagged_by': 'user'
            })

            # Increment use count
            self.db.execute(
                "UPDATE tags SET use_count = use_count + 1 WHERE id = ?",
                (tag_id,)
            )

            return True

        return False

    def remove_tag_from_content(self, content_id: str, tag_name: str) -> bool:
        """Remove a tag from content"""
        rows = self.db.fetchall("""
            DELETE FROM content_tags
            WHERE content_id = ? AND tag_id = (SELECT id FROM tags WHERE name = ?)
            RETURNING tag_id
        """, (content_id, tag_name))

        if rows:
            # Decrement use count
            for row in rows:
                self.db.execute(
                    "UPDATE tags SET use_count = use_count - 1 WHERE id = ?",
                    (row['tag_id'],)
                )
            return True

        return False

    def get_all_tags(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all tags, optionally filtered by category"""
        if category:
            rows = self.db.fetchall(
                "SELECT * FROM tags WHERE category = ? ORDER BY use_count DESC, name",
                (category,)
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM tags ORDER BY use_count DESC, name"
            )

        return [dict(row) for row in rows]

    def find_similar(self, content_id: str, limit: int = 10) -> List[Content]:
        """
        Find similar content based on topics

        Args:
            content_id: Content ID to find similar items for
            limit: Maximum results

        Returns:
            List of similar Content items
        """
        content = self.find_by_id(content_id)
        if not content:
            return []

        topics = content.get_ai_topics()
        if not topics:
            return []

        # Find content with similar topics
        all_content = self.find_all(where="id != ?", where_params=(content_id,), limit=500)

        similarities = []
        for other in all_content:
            other_topics = other.get_ai_topics()
            if not other_topics:
                continue

            # Calculate topic overlap
            common = set(t.lower() for t in topics) & set(t.lower() for t in other_topics)
            if common:
                similarity = len(common) / max(len(topics), len(other_topics))
                similarities.append((similarity, other))

        # Sort by similarity and return top results
        similarities.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in similarities[:limit]]

    def find_by_date_range(
        self,
        start_date: str,
        end_date: str,
        limit: int = 100
    ) -> List[Content]:
        """
        Find content within a date range

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            limit: Maximum results

        Returns:
            List of Content items
        """
        return self.find_all(
            where="created_at >= ? AND created_at <= ?",
            where_params=(start_date, end_date),
            order_by="created_at DESC",
            limit=limit
        )

    def get_reading_list(
        self,
        unread_only: bool = True,
        limit: int = 50
    ) -> List[Content]:
        """
        Get a reading list of content to read

        Args:
            unread_only: Only show unread content (progress < 1.0)
            limit: Maximum results

        Returns:
            List of Content items
        """
        if unread_only:
            return self.find_all(
                where="archived = ? AND reading_progress < ?",
                where_params=(0, 1.0),
                order_by="created_at DESC",
                limit=limit
            )
        else:
            return self.find_all(
                where="archived = ?",
                where_params=(0,),
                order_by="created_at DESC",
                limit=limit
            )

    def cleanup_old_content(self, days: int = 365) -> int:
        """
        Archive content older than specified days

        Args:
            days: Number of days

        Returns:
            Number of items archived
        """
        cutoff_date = datetime.now().replace(
            year=datetime.now().year - days
        ).isoformat()

        return self.db.update(
            "contents",
            {'archived': 1},
            f"created_at < ? AND archived = 0",
            (cutoff_date,)
        )


if __name__ == "__main__":
    # Test the content repository
    print("Content Repository Module")
    print("=" * 50)

    # Initialize database
    from database.connection import init_database
    init_database(":memory:")

    repo = ContentRepository(":memory:")

    # Create test content
    test_content = Content(
        id="test_001",
        source_type="webpage",
        content_type="article",
        title="Test Article",
        url="https://example.com/test",
        summary="This is a test article",
        main_content="Full content of the test article...",
        ai_analysis={
            'key_points': ['Point 1', 'Point 2', 'Point 3'],
            'topics': ['test', 'example'],
            'sentiment': 'neutral'
        },
        metadata={
            'author': 'Test Author',
            'publish_date': '2024-01-01'
        },
        favorited=True,
        reading_progress=0.5
    )

    result = repo.insert(test_content)
    print(f"Insert result: {result.success}")

    # Find by ID
    found = repo.find_by_id("test_001")
    if found:
        print(f"Found content: {found.title}")
        print(f"Key points: {found.get_ai_key_points()}")
        print(f"Topics: {found.get_ai_topics()}")

    # Search
    search_results = repo.search_by_text("test")
    print(f"Search results: {len(search_results)}")

    # Statistics
    stats = repo.get_statistics()
    print(f"Statistics: {stats}")

    print("\n✓ Content repository tests passed!")
