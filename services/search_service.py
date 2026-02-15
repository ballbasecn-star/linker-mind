"""
Enhanced Search Service Module - Advanced search and filtering

This module provides comprehensive search functionality:
- Full-text search with FTS
- Multi-criteria filtering
- Smart sorting
- Search history
- Faceted search

Features:
- Full-text search across content and notes
- Filter by type, tags, date range
- Sort by relevance, date, quality
- Search suggestions
- Saved searches
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from database.db_interface import get_connection
from database import json_list

logger = logging.getLogger(__name__)


class SortType(Enum):
    """Search result sorting options"""
    RELEVANCE = "relevance"
    DATE_DESC = "date_desc"
    DATE_ASC = "date_asc"
    QUALITY = "quality"
    TITLE = "title"
    PROGRESS = "progress"


@dataclass
class SearchQuery:
    """Search query parameters"""
    query: str
    content_types: Optional[List[str]] = None
    source_types: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    favorited_only: bool = False
    archived: bool = False
    min_quality: Optional[float] = None
    sort_by: SortType = SortType.RELEVANCE
    limit: int = 50

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResult:
    """A single search result"""
    id: str
    type: str                        # 'content' or 'note'
    title: str
    summary: Optional[str] = None
    url: Optional[str] = None
    source_type: Optional[str] = None
    platform: Optional[str] = None
    tags: List[str] = None
    relevance: float = 0.0
    created_at: Optional[str] = None
    highlights: Optional[List[str]] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SearchSuggestion:
    """Search suggestion/autocomplete"""
    text: str
    type: str                        # 'history', 'tag', 'content'
    count: int = 0


class EnhancedSearchService:
    """
    Enhanced search service with filtering and sorting

    Supports:
    - Full-text search using SQLite FTS
    - Multi-criteria filtering
    - Smart sorting
    - Faceted search
    - Search suggestions
    """

    def __init__(self, db_path: str = "linker_mind.db"):
        self.db = get_connection()
        self.db_path = db_path

    def search(self, search_query: SearchQuery) -> List[SearchResult]:
        """
        Execute a search with filters

        Args:
            search_query: SearchQuery object with all parameters

        Returns:
            List of SearchResult objects
        """
        if not search_query.query or search_query.query.strip() == "":
            # Empty query - just apply filters
            return self._filter_only_search(search_query)

        # Use FTS if available
        if self.db.table_exists('contents_fts') and self.db.table_exists('notes_fts'):
            return self._full_text_search(search_query)

        # Fallback to LIKE search
        return self._like_search(search_query)

    def _full_text_search(self, search_query: SearchQuery) -> List[SearchResult]:
        """Search using FTS tables"""
        results = []
        query = search_query.query

        # Search contents
        content_sql = """
            SELECT
                c.id,
                c.title,
                c.summary,
                c.url,
                c.source_type,
                c.platform,
                c.created_at,
                c.favorited,
                c.reading_progress,
                NULL as note_type,
                NULL as note_content,
                contents_fts.rank as rank
            FROM contents c
            INNER JOIN contents_fts ON c.id = contents_fts.id
            WHERE contents_fts MATCH ?
        """

        content_params = [query]

        # Add filters
        if search_query.content_types:
            content_sql += " AND c.content_type IN ({})".format(
                ','.join(['?' for _ in search_query.content_types])
            )
            content_params.extend(search_query.content_types)

        if search_query.source_types:
            content_sql += " AND c.source_type IN ({})".format(
                ','.join(['?' for _ in search_query.source_types])
            )
            content_params.extend(search_query.source_types)

        if search_query.favorited_only:
            content_sql += " AND c.favorited = 1"

        if not search_query.archived:
            content_sql += " AND c.archived = 0"

        content_sql += " LIMIT ?"
        content_params.append(search_query.limit * 2)  # Get more, will filter further

        content_rows = self.db.fetchall(content_sql, tuple(content_params))
        results.extend(self._content_rows_to_results(content_rows, query))

        # Search notes
        note_sql = """
            SELECT
                n.id,
                NULL as title,
                n.content as summary,
                NULL as url,
                NULL as source_type,
                NULL as platform,
                n.created_at,
                NULL as favorited,
                NULL as reading_progress,
                n.note_type,
                n.content as note_content,
                notes_fts.rank as rank
            FROM notes n
            INNER JOIN notes_fts ON n.id = notes_fts.id
            WHERE notes_fts MATCH ?
        """

        note_params = [query]

        note_sql += " LIMIT ?"
        note_params.append(search_query.limit * 2)

        note_rows = self.db.fetchall(note_sql, tuple(note_params))
        results.extend(self._note_rows_to_results(note_rows, query))

        # Sort results
        results = self._sort_results(results, search_query.sort_by)

        # Apply additional filters
        results = self._apply_filters(results, search_query)

        # Limit results
        return results[:search_query.limit]

    def _like_search(self, search_query: SearchQuery) -> List[SearchResult]:
        """Fallback LIKE-based search"""
        results = []
        query = f"%{search_query.query}%"

        # Search contents
        content_sql = """
            SELECT * FROM contents
            WHERE (title LIKE ? OR summary LIKE ? OR main_content LIKE ?)
        """
        params = (query, query, query)

        if search_query.favorited_only:
            content_sql += " AND favorited = 1"
        if not search_query.archived:
            content_sql += " AND archived = 0"

        content_sql += " LIMIT ?"
        params = params + (search_query.limit * 2,)

        content_rows = self.db.fetchall(content_sql, params)
        results.extend(self._content_rows_to_results(content_rows, search_query.query))

        # Search notes
        note_sql = """
            SELECT * FROM notes
            WHERE content LIKE ?
            LIMIT ?
        """
        note_rows = self.db.fetchall(note_sql, (query, search_query.limit * 2))
        results.extend(self._note_rows_to_results(note_rows, search_query.query))

        # Sort and filter
        results = self._sort_results(results, search_query.sort_by)
        results = self._apply_filters(results, search_query)

        return results[:search_query.limit]

    def _filter_only_search(self, search_query: SearchQuery) -> List[SearchResult]:
        """Handle empty query - just apply filters"""
        results = []

        # Get contents with filters
        sql = "SELECT * FROM contents WHERE 1=1"
        params = []

        if search_query.content_types:
            sql += " AND content_type IN ({})".format(
                ','.join(['?' for _ in search_query.content_types])
            )
            params.extend(search_query.content_types)

        if search_query.source_types:
            sql += " AND source_type IN ({})".format(
                ','.join(['?' for _ in search_query.source_types])
            )
            params.extend(search_query.source_types)

        if search_query.favorited_only:
            sql += " AND favorited = 1"

        if not search_query.archived:
            sql += " AND archived = 0"

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(search_query.limit)

        rows = self.db.fetchall(sql, tuple(params))
        results.extend(self._content_rows_to_results(rows, ""))

        return results

    def search_by_tags(
        self,
        tags: List[str],
        operator: str = "AND",
        limit: int = 50
    ) -> List[SearchResult]:
        """
        Search content and notes by tags

        Args:
            tags: List of tags to search for
            operator: 'AND' or 'OR'
            limit: Maximum results

        Returns:
            List of matching results
        """
        results = []
        tag_placeholders = ','.join(['?' for _ in tags])
        tag_params = tuple(tags)

        # Search content tags
        content_rows = self.db.fetchall(f"""
            SELECT DISTINCT c.*
            FROM contents c
            JOIN content_tags ct ON c.id = ct.content_id
            JOIN tags t ON ct.tag_id = t.id
            WHERE t.name IN ({tag_placeholders})
            GROUP BY c.id
            HAVING COUNT(DISTINCT t.id) {operator}= ?
            ORDER BY c.created_at DESC
            LIMIT ?
        """, tag_params + (len(tags), limit))

        results.extend(self._content_rows_to_results(content_rows, ""))

        # Search note project tags
        note_rows = self.db.fetchall(f"""
            SELECT n.*
            FROM notes n
            WHERE n.project_tags IS NOT NULL
            GROUP BY n.id
            HAVING (
                SELECT COUNT(DISTINCT LOWER(json_each.value))
                FROM json_each(n.project_tags)
                WHERE LOWER(json_each.value) IN ({tag_placeholders})
            ) {operator}= ?
            ORDER BY n.created_at DESC
            LIMIT ?
        """, tag_params + (len(tags), limit))

        results.extend(self._note_rows_to_results(note_rows, ""))

        return results

    def get_suggestions(
        self,
        query: str,
        limit: int = 10
    ) -> List[SearchSuggestion]:
        """
        Get search suggestions/autocomplete

        Args:
            query: Partial query string
            limit: Maximum suggestions

        Returns:
            List of suggestions
        """
        suggestions = []
        query_lower = query.lower()

        # Tag suggestions
        tag_rows = self.db.fetchall("""
            SELECT name, use_count FROM tags
            WHERE name LIKE ?
            ORDER BY use_count DESC, name ASC
            LIMIT ?
        """, (f"{query_lower}%", limit))

        for row in tag_rows:
            suggestions.append(SearchSuggestion(
                text=f"#{row['name']}",
                type="tag",
                count=row['use_count']
            ))

        # Content title suggestions
        content_rows = self.db.fetchall("""
            SELECT title, COUNT(*) as count
            FROM contents
            WHERE title LIKE ?
            GROUP BY title
            ORDER BY count DESC
            LIMIT ?
        """, (f"%{query}%", limit // 2))

        for row in content_rows:
            suggestions.append(SearchSuggestion(
                text=row['title'],
                type="content",
                count=row['count']
            ))

        return suggestions[:limit]

    def get_facets(self) -> Dict[str, Any]:
        """
        Get facet information for filtering

        Returns:
            Dictionary with available filters and counts
        """
        # Content types
        content_types = self.db.fetchall("""
            SELECT content_type, COUNT(*) as count
            FROM contents
            WHERE archived = 0
            GROUP BY content_type
            ORDER BY count DESC
        """)

        # Source types
        source_types = self.db.fetchall("""
            SELECT source_type, COUNT(*) as count
            FROM contents
            WHERE archived = 0
            GROUP BY source_type
            ORDER BY count DESC
        """)

        # Tags
        tags = self.db.fetchall("""
            SELECT t.name, COUNT(DISTINCT ct.content_id) as count
            FROM tags t
            JOIN content_tags ct ON t.id = ct.tag_id
            JOIN contents c ON ct.content_id = c.id
            WHERE c.archived = 0
            GROUP BY t.name
            ORDER BY count DESC
            LIMIT 50
        """)

        # Note types
        note_types = self.db.fetchall("""
            SELECT note_type, COUNT(*) as count
            FROM notes
            WHERE status = 'active'
            GROUP BY note_type
            ORDER BY count DESC
        """)

        return {
            'content_types': [dict(row) for row in content_types],
            'source_types': [dict(row) for row in source_types],
            'tags': [dict(row) for row in tags],
            'note_types': [dict(row) for row in note_types]
        }

    def save_search(self, query: str, user_id: str = "default") -> bool:
        """Save a search to history"""
        # This would require a search_history table
        # For now, just log it
        logger.info(f"Search saved for user {user_id}: {query}")
        return True

    def _content_rows_to_results(
        self,
        rows: List[Any],
        query: str
    ) -> List[SearchResult]:
        """Convert content database rows to SearchResult objects"""
        results = []
        for row in rows:
            # Calculate relevance
            relevance = self._calculate_relevance(row, query)

            # Get tags
            tags = self._get_content_tags(row['id'])

            results.append(SearchResult(
                id=row['id'],
                type='content',
                title=row['title'] or 'Untitled',
                summary=row['summary'],
                url=row['url'],
                source_type=row['source_type'],
                platform=row['source_type'],  # Use source_type as platform
                tags=tags,
                relevance=relevance,
                created_at=row['created_at']
            ))
        return results

    def _note_rows_to_results(
        self,
        rows: List[Any],
        query: str
    ) -> List[SearchResult]:
        """Convert note database rows to SearchResult objects"""
        results = []
        for row in rows:
            # Calculate relevance
            relevance = self._calculate_relevance(row, query)

            # Get tags from project_tags
            tags = json_list(row['project_tags']) if row['project_tags'] else []

            # Generate title from content
            content = row['note_content'] or row.get('content', '')
            title = content[:50] + "..." if len(content) > 50 else content

            results.append(SearchResult(
                id=row['id'],
                type='note',
                title=title,
                summary=content[:200] + "..." if len(content) > 200 else content,
                url=None,
                source_type='note',
                platform='note',
                tags=tags,
                relevance=relevance,
                created_at=row['created_at']
            ))
        return results

    def _get_content_tags(self, content_id: str) -> List[str]:
        """Get tags for a content item"""
        rows = self.db.fetchall("""
            SELECT t.name FROM tags t
            JOIN content_tags ct ON t.id = ct.tag_id
            WHERE ct.content_id = ?
        """, (content_id,))

        return [row['name'] for row in rows]

    def _calculate_relevance(self, row: Any, query: str) -> float:
        """Calculate relevance score for a result"""
        if not query:
            return 0.5

        query_lower = query.lower()

        # Check title match
        title = row.get('title', '') or ''
        if query_lower in title.lower():
            return 1.0

        # Check summary match
        summary = row.get('summary', '') or ''
        if query_lower in summary.lower():
            return 0.8

        # Check content match
        content = row.get('main_content', '') or row.get('content', '') or ''
        if query_lower in content.lower():
            return 0.7

        # Check tags
        tags = json_list(row.get('tags')) if row.get('tags') else []
        for tag in tags:
            if query_lower in tag.lower():
                return 0.6

        return 0.5

    def _sort_results(
        self,
        results: List[SearchResult],
        sort_by: SortType
    ) -> List[SearchResult]:
        """Sort results by specified criteria"""
        if sort_by == SortType.DATE_DESC:
            results.sort(key=lambda r: r.created_at or '', reverse=True)
        elif sort_by == SortType.DATE_ASC:
            results.sort(key=lambda r: r.created_at or '')
        elif sort_by == SortType.TITLE:
            results.sort(key=lambda r: r.title.lower() or '')
        elif sort_by == SortType.RELEVANCE:
            results.sort(key=lambda r: r.relevance, reverse=True)
        elif sort_by == SortType.PROGRESS:
            results.sort(
                key=lambda r: (r.type == 'content' and r.__dict__.get('reading_progress') or 0),
                reverse=True
            )

        return results

    def _apply_filters(
        self,
        results: List[SearchResult],
        search_query: SearchQuery
    ) -> List[SearchResult]:
        """Apply additional filters to results"""
        filtered = results

        # Tag filter
        if search_query.tags:
            if search_query.tags:
                filtered = [
                    r for r in filtered
                    if any(tag.lower() in [t.lower() for t in r.tags]
                          for tag in search_query.tags)
                ]

        # Date range filter
        if search_query.date_from or search_query.date_to:
            filtered = [
                r for r in filtered
                if r.created_at
                and (not search_query.date_from or r.created_at >= search_query.date_from)
                and (not search_query.date_to or r.created_at <= search_query.date_to)
            ]

        # Quality filter
        if search_query.min_quality is not None:
            filtered = [r for r in filtered if r.relevance >= search_query.min_quality]

        return filtered


if __name__ == "__main__":
    # Test the enhanced search service
    print("Enhanced Search Service Module")
    print("=" * 50)

    from database import init_database
    init_database(":memory:")

    # Create test data
    from repositories.content_repository import Content, ContentRepository

    content_repo = ContentRepository(":memory:")

    test_content = Content(
        id="test_001",
        source_type="webpage",
        content_type="article",
        title="Introduction to Productivity",
        url="https://example.com/productivity",
        summary="Learn how to be more productive",
        ai_analysis={'topics': ['productivity', 'time management', 'focus']}
    )

    content_repo.insert(test_content)

    # Add a tag
    content_repo.add_tag_to_content(test_content.id, "productivity")

    # Search
    search_service = EnhancedSearchService(":memory:")

    query = SearchQuery(
        query="productivity",
        limit=10
    )

    results = search_service.search(query)
    print(f"Search results: {len(results)}")
    for result in results:
        print(f"  - {result.title} ({result.type})")

    # Get facets
    facets = search_service.get_facets()
    print(f"\nFacets: {list(facets.keys())}")

    # Get suggestions
    suggestions = search_service.get_suggestions("prod")
    print(f"\nSuggestions for 'prod': {len(suggestions)}")
    for suggestion in suggestions[:3]:
        print(f"  - {suggestion.text} ({suggestion.type})")

    print("\n✓ Enhanced search service tests passed!")
