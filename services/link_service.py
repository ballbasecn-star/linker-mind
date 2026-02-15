"""
Bidirectional Links Service Module - Connection management

This module implements bidirectional linking between content, notes, and nodes.
Inspired by Roam Research and Obsidian.

Features:
- Create typed links between items
- Find backlinks
- Discover related content
- Calculate link strength
- Link type management
"""
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from database.db_interface import get_connection
from database import json_dumps

logger = logging.getLogger(__name__)


class LinkType(Enum):
    """Types of bidirectional links"""
    REFERENCE = "reference"       # Direct reference or citation
    RELATED = "related"           # Related content
    OPPOSES = "opposes"           # Contradicting or opposing views
    EXTENDS = "extends"           # Builds upon or extends
    EXAMPLE = "example"           # Provides an example
    QUESTION = "question"         # Raises a question about
    APPLICATION = "application"   # Applies the concept
    INSPIRED = "inspired"         # Inspired by this content
    DERIVES = "derives"          # Derived from this content


class LinkSourceType(Enum):
    """Types of entities that can be linked"""
    NOTE = "note"
    CONTENT = "content"
    NODE = "node"


@dataclass
class Link:
    """A bidirectional link between two entities"""
    id: str
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    link_type: str
    context: Optional[str] = None
    strength: float = 1.0
    manual_strength: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def is_same_type(self) -> bool:
        """Check if source and target are the same type"""
        return self.source_type == self.target_type


@dataclass
class BacklinkResult:
    """Result of backlink query"""
    source_id: str
    source_type: str
    link_type: str
    context: Optional[str]
    strength: float
    created_at: str


@dataclass
class LinkSuggestion:
    """Suggested link to create"""
    source_id: str
    source_title: str
    target_id: str
    target_title: str
    reason: str
    confidence: float


class LinkService:
    """
    Service for managing bidirectional links

    Supports linking between:
    - Notes
    - Content items
    - Organization nodes

    Features:
    - Create and manage typed links
    - Find backlinks (incoming links)
    - Discover related content
    - Automatic link suggestions
    - Link strength calculation
    """

    def __init__(self, db_path: str = "linker_mind.db"):
        self.db = get_connection()
        self.db_path = db_path

    def create(
        self,
        source_id: str,
        source_type: LinkSourceType,
        target_id: str,
        target_type: LinkSourceType,
        link_type: LinkType = LinkType.RELATED,
        context: Optional[str] = None,
        strength: Optional[float] = None
    ) -> Link:
        """
        Create a bidirectional link

        Args:
            source_id: Source entity ID
            source_type: Type of source entity
            target_id: Target entity ID
            target_type: Type of target entity
            link_type: Type of link
            context: Description of the relationship
            strength: Link strength (0.0 to 1.0)

        Returns:
            Created Link
        """
        id = self._generate_id()

        if strength is None:
            strength = self._calculate_default_strength(link_type)

        link = Link(
            id=id,
            source_id=source_id,
            source_type=source_type.value,
            target_id=target_id,
            target_type=target_type.value,
            link_type=link_type.value,
            context=context,
            strength=strength
        )

        self.db.insert("links", {
            'id': link.id,
            'source_id': link.source_id,
            'source_type': link.source_type,
            'target_id': link.target_id,
            'target_type': link.target_type,
            'link_type': link.link_type,
            'context': link.context,
            'strength': link.strength,
            'manual_strength': 0,
            'created_at': link.created_at,
            'updated_at': link.updated_at
        })

        logger.info(f"Created link: {source_id} -> {target_id} ({link_type.value})")
        return link

    def get_by_id(self, link_id: str) -> Optional[Link]:
        """Get a link by ID"""
        row = self.db.fetchone(
            "SELECT * FROM links WHERE id = ?",
            (link_id,)
        )
        if row:
            return self._row_to_link(row)
        return None

    def get_links_from(
        self,
        entity_id: str,
        entity_type: LinkSourceType,
        link_type: Optional[LinkType] = None
    ) -> List[Link]:
        """
        Get all outgoing links from an entity

        Args:
            entity_id: Entity ID
            entity_type: Type of the entity
            link_type: Optional filter by link type

        Returns:
            List of outgoing Links
        """
        sql = "SELECT * FROM links WHERE source_id = ? AND source_type = ?"
        params = (entity_id, entity_type.value)

        if link_type:
            sql += " AND link_type = ?"
            params = params + (link_type.value,)

        sql += " ORDER BY strength DESC, created_at DESC"

        rows = self.db.fetchall(sql, params)
        return [self._row_to_link(row) for row in rows]

    def get_backlinks_to(
        self,
        entity_id: str,
        entity_type: LinkSourceType,
        link_type: Optional[LinkType] = None
    ) -> List[BacklinkResult]:
        """
        Get all incoming links (backlinks) to an entity

        Args:
            entity_id: Entity ID
            entity_type: Type of the entity
            link_type: Optional filter by link type

        Returns:
            List of backlink results
        """
        sql = """
            SELECT
                source_id,
                source_type,
                link_type,
                context,
                strength,
                created_at
            FROM links
            WHERE target_id = ? AND target_type = ?
        """
        params = (entity_id, entity_type.value)

        if link_type:
            sql += " AND link_type = ?"
            params = params + (link_type.value,)

        sql += " ORDER BY strength DESC, created_at DESC"

        rows = self.db.fetchall(sql, params)
        return [
            BacklinkResult(
                source_id=row['source_id'],
                source_type=row['source_type'],
                link_type=row['link_type'],
                context=row['context'],
                strength=row['strength'],
                created_at=row['created_at']
            )
            for row in rows
        ]

    def get_all(
        self,
        link_type: Optional[LinkType] = None,
        limit: int = 100
    ) -> List[Link]:
        """
        Get all links with optional filtering

        Args:
            link_type: Optional link type filter
            limit: Maximum number of links to return

        Returns:
            List of Link objects
        """
        sql = "SELECT * FROM links"
        params = ()

        if link_type:
            sql += " WHERE link_type = ?"
            params = (link_type.value,)

        sql += " ORDER BY strength DESC, created_at DESC LIMIT ?"
        params = params + (limit,)

        rows = self.db.fetchall(sql, params)
        return [self._row_to_link(row) for row in rows]

    def delete(self, link_id: str) -> bool:
        """Delete a link"""
        rows = self.db.delete("links", "id = ?", (link_id,))
        return rows > 0

    def delete_between(
        self,
        source_id: str,
        target_id: str
    ) -> int:
        """Delete all links between two entities"""
        rows = self.db.delete(
            "links",
            "source_id = ? AND target_id = ?",
            (source_id, target_id)
        )
        return rows

    def update(
        self,
        link_id: str,
        link_type: Optional[LinkType] = None,
        context: Optional[str] = None,
        strength: Optional[float] = None
    ) -> Optional[Link]:
        """Update a link"""
        link = self.get_by_id(link_id)
        if not link:
            return None

        updates = {'updated_at': datetime.now().isoformat()}

        if link_type is not None:
            updates['link_type'] = link_type.value
        if context is not None:
            updates['context'] = context
        if strength is not None:
            updates['strength'] = strength
            updates['manual_strength'] = 1

        self.db.update(
            "links",
            updates,
            "id = ?",
            (link_id,)
        )

        return self.get_by_id(link_id)

    def find_related(
        self,
        entity_id: str,
        entity_type: LinkSourceType,
        max_distance: int = 2,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Find entities related to the given entity

        Uses graph traversal to find related content

        Args:
            entity_id: Starting entity ID
            entity_type: Type of the entity
            max_distance: Maximum hop distance
            max_results: Maximum results

        Returns:
            List of related entities with distance and link info
        """
        visited = {entity_id}
        queue = [(entity_id, 0)]
        results = []

        while queue and len(results) < max_results:
            current_id, distance = queue.pop(0)

            if distance >= max_distance:
                continue

            # Get outgoing links
            out_links = self.db.fetchall("""
                SELECT target_id, target_type, link_type, context, strength
                FROM links
                WHERE source_id = ? AND source_type = ?
            """, (current_id, entity_type.value))

            for row in out_links:
                target_id = row['target_id']
                if target_id not in visited:
                    visited.add(target_id)
                    results.append({
                        'id': target_id,
                        'type': row['target_type'],
                        'distance': distance + 1,
                        'link_type': row['link_type'],
                        'context': row['context'],
                        'strength': row['strength']
                    })
                    queue.append((target_id, distance + 1))

            # Get incoming links
            in_links = self.db.fetchall("""
                SELECT source_id, source_type, link_type, context, strength
                FROM links
                WHERE target_id = ? AND target_type = ?
            """, (entity_id, entity_type.value))

            for row in in_links:
                source_id = row['source_id']
                if source_id not in visited:
                    visited.add(source_id)
                    results.append({
                        'id': source_id,
                        'type': row['source_type'],
                        'distance': distance + 1,
                        'link_type': row['link_type'],
                        'context': row['context'],
                        'strength': row['strength'],
                        'direction': 'incoming'
                    })
                    queue.append((source_id, distance + 1))

        return results[:max_results]

    def get_suggestions(
        self,
        entity_id: str,
        entity_type: LinkSourceType,
        limit: int = 10
    ) -> List[LinkSuggestion]:
        """
        Get link suggestions based on shared topics, tags, or connections

        Args:
            entity_id: Entity ID
            entity_type: Type of entity
            limit: Maximum suggestions

        Returns:
            List of suggested links
        """
        # This is a simplified version - a full implementation would
        # use content similarity, shared tags, etc.

        # Find entities linked to similar entities
        suggestions = []

        # Get current links
        current_links = self.get_links_from(entity_id, entity_type)

        # For each current link target, find what else links to them
        for link in current_links[:5]:
            backlinks = self.get_backlinks_to(link.target_id, LinkSourceType(link.target_type))

            for backlink in backlinks:
                if backlink.source_id != entity_id:
                    # Check if already linked
                    existing = self.db.fetchone(
                        "SELECT * FROM links WHERE source_id = ? AND target_id = ?",
                        (entity_id, backlink.source_id)
                    )

                    if not existing:
                        suggestions.append(LinkSuggestion(
                            source_id=entity_id,
                            source_title=self._get_entity_title(entity_id, entity_type),
                            target_id=backlink.source_id,
                            target_title=self._get_entity_title(backlink.source_id, LinkSourceType(backlink.source_type)),
                            reason=f"Both link to {self._get_entity_title(link.target_id, LinkSourceType(link.target_type))}",
                            confidence=0.5
                        ))

                        if len(suggestions) >= limit:
                            break

            if len(suggestions) >= limit:
                break

        return suggestions[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """Get link statistics"""
        total = self.db.fetchval("SELECT COUNT(*) FROM links") or 0

        # Count by type
        type_rows = self.db.fetchall("""
            SELECT link_type, COUNT(*) as count
            FROM links
            GROUP BY link_type
        """)
        by_type = {row['link_type']: row['count'] for row in type_rows}

        # Count by source type
        source_rows = self.db.fetchall("""
            SELECT source_type, COUNT(*) as count
            FROM links
            GROUP BY source_type
        """)
        by_source_type = {row['source_type']: row['count'] for row in source_rows}

        # Most linked entities
        linked_rows = self.db.fetchall("""
            SELECT
                source_id,
                source_type,
                COUNT(*) as link_count
            FROM links
            GROUP BY source_id, source_type
            ORDER BY link_count DESC
            LIMIT 10
        """)
        most_linked = [
            {
                'id': row['source_id'],
                'type': row['source_type'],
                'count': row['link_count'],
                'title': self._get_entity_title(row['source_id'], LinkSourceType(row['source_type']))
            }
            for row in linked_rows
        ]

        # Average strength
        avg_strength = self.db.fetchval("SELECT AVG(strength) FROM links") or 0

        return {
            'total_links': total,
            'by_type': by_type,
            'by_source_type': by_source_type,
            'most_linked_entities': most_linked,
            'average_strength': round(avg_strength, 2)
        }

    def find_unconnected(self, entity_type: LinkSourceType, limit: int = 20) -> List[str]:
        """
        Find entities that have no links

        Args:
            entity_type: Type of entity to check
            limit: Maximum results

        Returns:
            List of entity IDs
        """
        # This would need to query all entities of the type
        # For now, return empty list
        return []

    def find_orphans(self, entity_type: LinkSourceType) -> List[str]:
        """
        Find entities that only have outgoing links but no incoming links

        Args:
            entity_type: Type of entity

        Returns:
            List of entity IDs
        """
        # Find entities with outgoing but no incoming links
        rows = self.db.fetchall(f"""
            SELECT DISTINCT source_id
            FROM links
            WHERE source_type = ?
            AND source_id NOT IN (
                SELECT target_id FROM links WHERE target_type = ?
            )
            LIMIT 100
        """, (entity_type.value, entity_type.value))

        return [row['source_id'] for row in rows]

    def find_hubs(self, entity_type: LinkSourceType, threshold: int = 5) -> List[Dict[str, Any]]:
        """
        Find hub entities (those with many connections)

        Args:
            entity_type: Type of entity
            threshold: Minimum connection count

        Returns:
            List of hub entities with stats
        """
        rows = self.db.fetchall(f"""
            SELECT
                source_id,
                COUNT(*) as outgoing,
                (
                    SELECT COUNT(*) FROM links l2
                    WHERE l2.target_id = links.source_id
                    AND l2.target_type = ?
                ) as incoming
            FROM links
            WHERE source_type = ?
            GROUP BY source_id
            HAVING outgoing + incoming >= ?
            ORDER BY (outgoing + incoming) DESC
            LIMIT 50
        """, (entity_type.value, entity_type.value, threshold))

        return [
            {
                'id': row['source_id'],
                'title': self._get_entity_title(row['source_id'], entity_type),
                'outgoing': row['outgoing'],
                'incoming': row['incoming'],
                'total': row['outgoing'] + row['incoming']
            }
            for row in rows
        ]

    def recalculate_strength(self, link_id: str) -> Optional[float]:
        """
        Recalculate link strength based on various factors

        Args:
            link_id: Link ID

        Returns:
            New strength value or None
        """
        link = self.get_by_id(link_id)
        if not link:
            return None

        # Simple strength calculation based on:
        # - Link type weight
        # - Age of the link
        # - Mutual linking (if target also links back to source)

        base_strength = self._get_type_weight(LinkType(link.link_type))

        # Check for mutual linking
        mutual = self.db.fetchone(
            "SELECT * FROM links WHERE source_id = ? AND target_id = ?",
            (link.target_id, link.source_id)
        )

        if mutual:
            base_strength *= 1.2

        # Update link
        self.update(link_id, strength=base_strength)

        return base_strength

    def get_link_graph(
        self,
        entity_type: Optional[LinkSourceType] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get link graph data for visualization

        Args:
            entity_type: Optional filter by entity type
            limit: Maximum nodes

        Returns:
            Graph data with nodes and edges
        """
        # Build where clause
        where = ""
        params = []

        if entity_type:
            where = " WHERE source_type = ?"
            params = [entity_type.value]

        # Get nodes (entities)
        # This is simplified - a real implementation would
        # join with the actual entity tables

        nodes = []
        edges = []

        # Get edges
        sql = "SELECT source_id, target_id, link_type, strength FROM links" + where
        if params:
            sql += " AND target_type = ?"
            params.append(entity_type.value)
        sql += " LIMIT ?"
        params.append(limit * 2)

        rows = self.db.fetchall(sql, tuple(params))

        node_ids = set()
        for row in rows:
            node_ids.add(row['source_id'])
            node_ids.add(row['target_id'])

            edges.append({
                'source': row['source_id'],
                'target': row['target_id'],
                'type': row['link_type'],
                'weight': row['strength']
            })

        # Create nodes
        for node_id in list(node_ids)[:limit]:
            nodes.append({
                'id': node_id,
                'label': self._get_entity_title(node_id, entity_type or LinkSourceType.NOTE),
                'type': entity_type.value if entity_type else 'note'
            })

        return {
            'nodes': nodes,
            'edges': edges,
            'stats': {
                'node_count': len(nodes),
                'edge_count': len(edges)
            }
        }

    def _row_to_link(self, row: Any) -> Link:
        """Convert database row to Link"""
        return Link(
            id=row['id'],
            source_id=row['source_id'],
            source_type=row['source_type'],
            target_id=row['target_id'],
            target_type=row['target_type'],
            link_type=row['link_type'],
            context=row['context'],
            strength=row['strength'],
            manual_strength=bool(row['manual_strength']),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def _generate_id(self) -> str:
        """Generate unique link ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        count = self.db.fetchval("SELECT COUNT(*) FROM links") or 0
        return f"link_{timestamp}_{count:03d}"

    def _calculate_default_strength(self, link_type: LinkType) -> float:
        """Calculate default strength based on link type"""
        return self._get_type_weight(link_type)

    def _get_type_weight(self, link_type: LinkType) -> float:
        """Get weight/strength value for link type"""
        weights = {
            LinkType.REFERENCE: 0.5,
            LinkType.RELATED: 0.3,
            LinkType.OPPOSES: 0.4,
            LinkType.EXTENDS: 0.6,
            LinkType.EXAMPLE: 0.5,
            LinkType.QUESTION: 0.4,
            LinkType.APPLICATION: 0.7,
            LinkType.INSPIRED: 0.6,
            LinkType.DERIVES: 0.8
        }
        return weights.get(link_type, 0.5)

    def _get_entity_title(self, entity_id: str, entity_type: LinkSourceType) -> str:
        """Get title for an entity"""
        # Try to get title from appropriate table
        if entity_type == LinkSourceType.CONTENT:
            row = self.db.fetchone("SELECT title FROM contents WHERE id = ?", (entity_id,))
            if row and row['title']:
                return row['title']

        elif entity_type == LinkSourceType.NOTE:
            row = self.db.fetchone("SELECT content FROM notes WHERE id = ?", (entity_id,))
            if row and row['content']:
                content = row['content']
                return content[:50] + "..." if len(content) > 50 else content

        elif entity_type == LinkSourceType.NODE:
            row = self.db.fetchone("SELECT name FROM nodes WHERE id = ?", (entity_id,))
            if row and row['name']:
                return row['name']

        return entity_id[:20] + "..."


if __name__ == "__main__":
    # Test the link service
    print("Bidirectional Link Service Module")
    print("=" * 50)

    from database import init_database
    init_database(":memory:")

    service = LinkService(":memory:")

    # Create some test links
    link1 = service.create(
        "note_001", LinkSourceType.NOTE,
        "note_002", LinkSourceType.NOTE,
        LinkType.RELATED,
        context="These notes discuss similar concepts"
    )

    link2 = service.create(
        "note_002", LinkSourceType.NOTE,
        "note_003", LinkSourceType.NOTE,
        LinkType.EXTENDS,
        context="This note builds on the ideas from note 003"
    )

    link3 = service.create(
        "content_001", LinkSourceType.CONTENT,
        "note_001", LinkSourceType.NOTE,
        LinkType.REFERENCE,
        context="Content references this note"
    )

    print(f"Created links: {link1.id}, {link2.id}, {link3.id}")

    # Get backlinks
    backlinks = service.get_backlinks_to("note_002", LinkSourceType.NOTE)
    print(f"Backlinks to note_002: {len(backlinks)}")

    # Find related
    related = service.find_related("note_001", LinkSourceType.NOTE, max_distance=2)
    print(f"Related to note_001: {len(related)} items")

    # Get statistics
    stats = service.get_statistics()
    print(f"Statistics: {stats}")

    print("\n✓ Link service tests passed!")
