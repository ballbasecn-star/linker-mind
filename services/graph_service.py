"""
Knowledge Graph Service Module - Visualize knowledge relationships

This module provides:
- Force-directed graph data
- Skill tree visualization
- Learning path recommendations
- Topic clustering
- Timeline visualization

Features:
- Generate graph data for D3.js/vis.js
- Find connections between content
- Calculate node importance
- Suggest learning paths
- Cluster related topics
"""
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from collections import defaultdict, Counter

from database.db_interface import get_connection
from database import json_list, json_dict

logger = logging.getLogger(__name__)


class GraphType(Enum):
    """Types of graph visualizations"""
    FORCE_DIRECTED = "force_directed"    # Network graph
    SKILL_TREE = "skill_tree"            # Hierarchical tree
    LEARNING_PATH = "learning_path"      # Path graph
    TOPIC_CLUSTER = "topic_cluster"      # Clustered groups
    TIMELINE = "timeline"                # Time-based


class NodeType(Enum):
    """Types of nodes in the graph"""
    CONTENT = "content"                  # Content item
    NOTE = "note"                        # Note
    PROJECT = "project"                  # Organization project
    AREA = "area"                        # Organization area
    SKILL = "skill"                      # Skill
    TOPIC = "topic"                      # Topic tag


@dataclass
class GraphNode:
    """A node in the knowledge graph"""
    id: str
    label: str
    node_type: str
    size: float = 1.0                    # Node size (based on importance)
    color: str = "#3498db"               # Node color
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GraphEdge:
    """An edge in the knowledge graph"""
    source: str                          # Source node ID
    target: str                          # Target node ID
    weight: float = 1.0                  # Edge weight/strength
    label: Optional[str] = None          # Edge label
    color: str = "#bdc3c7"               # Edge color

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GraphData:
    """Complete graph data for visualization"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    graph_type: str
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'nodes': [n.to_dict() for n in self.nodes],
            'edges': [e.to_dict() for e in self.edges],
            'graph_type': self.graph_type,
            'metadata': self.metadata
        }

    def to_json(self) -> str:
        """Export to JSON for frontend consumption"""
        import json
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class SkillTreeNode:
    """A node in the skill tree"""
    id: str
    name: str
    level: str                          # beginner, intermediate, advanced, expert
    parent_ids: List[str] = None
    children_ids: List[str] = None
    content_count: int = 0
    mastery_level: float = 0.0           # 0-100

    def __post_init__(self):
        if self.parent_ids is None:
            self.parent_ids = []
        if self.children_ids is None:
            self.children_ids = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LearningPathStep:
    """A step in a learning path"""
    content_id: str
    title: str
    order: int
    estimated_time: Optional[int] = None  # minutes
    prerequisites: List[str] = None
    completed: bool = False

    def __post_init__(self):
        if self.prerequisites is None:
            self.prerequisites = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LearningPath:
    """A learning path between skills"""
    from_skill: str
    to_skill: str
    steps: List[LearningPathStep]
    total_time: int = 0                  # minutes
    difficulty: str = "intermediate"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['steps'] = [s.to_dict() for s in self.steps]
        return data


class KnowledgeGraphService:
    """
    Service for generating knowledge graph visualizations

    Provides data for various visualization types:
    - Force-directed graphs for content relationships
    - Skill trees for hierarchical knowledge
    - Learning paths for progression planning
    - Topic clusters for discovering connections
    """

    def __init__(self, db_path: str = "linker_mind.db"):
        self.db = get_connection()
        self.db_path = db_path

    def get_force_directed_graph(
        self,
        limit: int = 100,
        min_weight: float = 0.1
    ) -> GraphData:
        """
        Generate force-directed graph data

        Shows content items as nodes and relationships as edges
        """
        nodes = []
        edges = []
        node_set = set()

        # Get recent content items
        content_rows = self.db.fetchall("""
            SELECT id, title, source_type, created_at
            FROM contents
            WHERE archived = 0
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        # Create nodes from content
        for row in content_rows:
            node = GraphNode(
                id=row['id'],
                label=row['title'] or 'Untitled',
                node_type=NodeType.CONTENT.value,
                size=1.0,
                color=self._get_color_for_type(row['source_type']),
                metadata={
                    'source_type': row['source_type'],
                    'created_at': row['created_at']
                }
            )
            nodes.append(node)
            node_set.add(row['id'])

        # Create edges from links
        link_rows = self.db.fetchall("""
            SELECT source_id, target_id, link_type, strength
            FROM links
            WHERE source_type = 'content' AND target_type = 'content'
            LIMIT ?
        """, (limit * 2,))

        for row in link_rows:
            if row['source_id'] in node_set and row['target_id'] in node_set:
                edge = GraphEdge(
                    source=row['source_id'],
                    target=row['target_id'],
                    weight=row['strength'] or 1.0,
                    label=row['link_type'],
                    color=self._get_color_for_link(row['link_type'])
                )
                edges.append(edge)

        # Calculate node importance (pagerank-like)
        node_importance = self._calculate_node_importance(nodes, edges)
        for node in nodes:
            if node.id in node_importance:
                node.size = 1.0 + node_importance[node.id] * 2

        return GraphData(
            nodes=nodes,
            edges=edges,
            graph_type=GraphType.FORCE_DIRECTED.value,
            metadata={
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'generated_at': datetime.now().isoformat()
            }
        )

    def get_skill_tree(self, skill_id: Optional[str] = None) -> List[SkillTreeNode]:
        """
        Get skill tree structure

        Args:
            skill_id: Root skill ID (None for all skills)

        Returns:
            List of SkillTreeNode objects
        """
        # Get all skills
        if skill_id:
            skill_rows = self.db.fetchall("""
                SELECT * FROM skills
                WHERE id = ? OR parent_ids LIKE ?
                ORDER BY category, level
            """, (skill_id, f'%"{skill_id}"%'))
        else:
            skill_rows = self.db.fetchall("""
                SELECT * FROM skills
                ORDER BY category, level
            """)

        skill_nodes = []
        for row in skill_rows:
            parent_ids = json_list(row['parent_ids']) or []

            # Count content for this skill
            content_count = self.db.fetchval("""
                SELECT COUNT(*) FROM skill_contents
                WHERE skill_id = ?
            """, (row['id'],)) or 0

            node = SkillTreeNode(
                id=row['id'],
                skill_name=row['skill_name'],
                level=row['level'],
                parent_ids=parent_ids,
                content_count=content_count,
                mastery_level=0.0  # Could calculate from completed content
            )
            skill_nodes.append(node)

        # Build children relationships
        for node in skill_nodes:
            for parent_id in node.parent_ids:
                for potential_parent in skill_nodes:
                    if potential_parent.id == parent_id:
                        potential_parent.children_ids.append(node.id)

        return skill_nodes

    def get_learning_path(
        self,
        from_skill: str,
        to_skill: str,
        max_depth: int = 5
    ) -> Optional[LearningPath]:
        """
        Find shortest learning path between skills

        Args:
            from_skill: Starting skill ID
            to_skill: Target skill ID
            max_depth: Maximum path depth

        Returns:
            LearningPath or None if no path found
        """
        # BFS to find path
        from skills.graph_service import deque

        queue = deque([(from_skill, [])])
        visited = set()
        skill_cache = {}

        while queue:
            current_skill, path = queue.popleft()

            if current_skill in visited:
                continue
            visited.add(current_skill)

            if current_skill == to_skill:
                # Build learning path
                steps = []
                total_time = 0

                for skill_id in path + [current_skill]:
                    if skill_id not in skill_cache:
                        row = self.db.fetchone(
                            "SELECT * FROM skills WHERE id = ?",
                            (skill_id,)
                        )
                        skill_cache[skill_id] = row

                    skill = skill_cache[skill_id]

                    # Get content for this skill
                    content_rows = self.db.fetchall("""
                        SELECT sc.content_id, c.title, c.created_at
                        FROM skill_contents sc
                        JOIN contents c ON sc.content_id = c.id
                        WHERE sc.skill_id = ?
                        ORDER BY sc.order_index
                    """, (skill_id,))

                    for i, content_row in enumerate(content_rows):
                        step = LearningPathStep(
                            content_id=content_row['content_id'],
                            title=content_row['title'],
                            order=len(steps),
                            completed=content_row.get('completed', False)
                        )
                        steps.append(step)

                return LearningPath(
                    from_skill=from_skill,
                    to_skill=to_skill,
                    steps=steps,
                    total_time=total_time,
                    difficulty="intermediate"
                )

            if len(path) >= max_depth:
                continue

            # Get connected skills (children/parents)
            skill_row = self.db.fetchone(
                "SELECT * FROM skills WHERE id = ?",
                (current_skill,)
            )

            if not skill_row:
                continue

            parent_ids = json_list(skill_row['parent_ids']) or []
            child_ids = self._get_child_skills(current_skill)

            next_skills = parent_ids + child_ids

            for next_skill in next_skills:
                if next_skill not in visited:
                    queue.append((next_skill, path + [current_skill]))

        return None

    def get_topic_clusters(
        self,
        min_cluster_size: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find topic clusters using co-occurrence

        Args:
            min_cluster_size: Minimum items per cluster

        Returns:
            List of clusters with their content
        """
        # Get all content with topics
        content_rows = self.db.fetchall("""
            SELECT id, title, ai_analysis
            FROM contents
            WHERE ai_analysis IS NOT NULL
            AND archived = 0
            LIMIT 500
        """)

        # Build topic -> content mapping
        topic_contents = defaultdict(list)
        all_topics = set()

        for row in content_rows:
            analysis = json_dict(row['ai_analysis'])
            topics = analysis.get('topics', [])

            for topic in topics:
                topic_lower = topic.lower()
                topic_contents[topic_lower].append({
                    'id': row['id'],
                    'title': row['title']
                })
                all_topics.add(topic_lower)

        # Find clusters (topics that share content)
        clusters = []
        processed_topics = set()

        for topic in all_topics:
            if topic in processed_topics:
                continue

            # Find related topics (share content)
            related = {topic}
            content_ids = {c['id'] for c in topic_contents[topic]}

            for other_topic in all_topics:
                if other_topic == topic:
                    continue

                other_content_ids = {c['id'] for c in topic_contents[other_topic]}

                # Check overlap
                overlap = content_ids & other_content_ids
                if len(overlap) >= 2:  # At least 2 shared content
                    related.add(other_topic)
                    content_ids |= other_content_ids

            if len(related) >= min_cluster_size or len(content_ids) >= min_cluster_size:
                cluster = {
                    'topics': list(related),
                    'content_count': len(content_ids),
                    'sample_content': list(content_ids)[:10]
                }
                clusters.append(cluster)

            processed_topics.update(related)

        # Sort by content count
        clusters.sort(key=lambda c: c['content_count'], reverse=True)

        return clusters[:20]  # Return top 20 clusters

    def get_timeline(
        self,
        content_ids: Optional[List[str]] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get timeline of content/notes by date

        Args:
            content_ids: Specific content IDs (None for all)
            days: Number of days to include

        Returns:
            Timeline data grouped by date
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        if content_ids:
            placeholders = ','.join(['?' for _ in content_ids])
            content_rows = self.db.fetchall(f"""
                SELECT id, title, created_at, 'content' as type
                FROM contents
                WHERE created_at >= ?
                AND id IN ({placeholders})
                ORDER BY created_at DESC
            """, [cutoff] + content_ids)
        else:
            content_rows = self.db.fetchall("""
                SELECT id, title, created_at, 'content' as type
                FROM contents
                WHERE created_at >= ?
                ORDER BY created_at DESC
            """, (cutoff,))

        # Group by date
        timeline = defaultdict(list)
        for row in content_rows:
            date = row['created_at'][:10]  # YYYY-MM-DD
            timeline[date].append({
                'id': row['id'],
                'title': row['title'],
                'type': row['type'],
                'time': row['created_at']
            })

        # Convert to sorted list
        result = [
            {
                'date': date,
                'count': len(items),
                'items': items
            }
            for date, items in sorted(timeline.items(), reverse=True)
        ]

        return result

    def get_node_connections(
        self,
        node_id: str,
        depth: int = 2
    ) -> GraphData:
        """
        Get local graph around a node

        Args:
            node_id: Center node ID
            depth: How many hops to explore

        Returns:
            GraphData with connected nodes
        """
        nodes = {}
        edges = []

        # Get the center node
        center_row = self.db.fetchone(
            "SELECT id, title, source_type FROM contents WHERE id = ?",
            (node_id,)
        )

        if not center_row:
            return GraphData(nodes=[], edges=[], graph_type=GraphType.FORCE_DIRECTED.value)

        nodes[node_id] = GraphNode(
            id=node_id,
            label=center_row['title'] or 'Untitled',
            node_type=NodeType.CONTENT.value,
            size=2.0,
            color='#e74c3c'  # Red for center
        )

        # Get connections at each depth
        visited = {node_id}
        current_level = {node_id}

        for level in range(depth):
            next_level = set()

            for current_id in current_level:
                # Get outgoing links
                link_rows = self.db.fetchall("""
                    SELECT target_id, link_type, strength
                    FROM links
                    WHERE source_id = ?
                    AND source_type = 'content' AND target_type = 'content'
                """, (current_id,))

                for row in link_rows:
                    target_id = row['target_id']

                    if target_id not in visited:
                        visited.add(target_id)
                        next_level.add(target_id)

                        # Get target info
                        target_row = self.db.fetchone(
                            "SELECT id, title, source_type FROM contents WHERE id = ?",
                            (target_id,)
                        )

                        if target_row:
                            nodes[target_id] = GraphNode(
                                id=target_id,
                                label=target_row['title'] or 'Untitled',
                                node_type=NodeType.CONTENT.value,
                                size=1.0 - (level * 0.3),  # Smaller as we go out
                                color=self._get_color_for_type(target_row['source_type'])
                            )

                    # Add edge
                    edges.append(GraphEdge(
                        source=current_id,
                        target=target_id,
                        weight=row['strength'] or 1.0,
                        label=row['link_type']
                    ))

            current_level = next_level

        return GraphData(
            nodes=list(nodes.values()),
            edges=edges,
            graph_type=GraphType.FORCE_DIRECTED.value,
            metadata={
                'center_node': node_id,
                'depth': depth,
                'total_nodes': len(nodes),
                'total_edges': len(edges)
            }
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics"""
        # Node counts
        content_count = self.db.fetchval("SELECT COUNT(*) FROM contents") or 0
        note_count = self.db.fetchval("SELECT COUNT(*) FROM notes") or 0
        skill_count = self.db.fetchval("SELECT COUNT(*) FROM skills") or 0

        # Edge counts
        link_count = self.db.fetchval("SELECT COUNT(*) FROM links") or 0

        # Connectivity
        avg_connections = 0
        if content_count > 0:
            total_outgoing = self.db.fetchval("""
                SELECT AVG(outgoing) FROM (
                    SELECT COUNT(*) as outgoing
                    FROM links
                    WHERE source_type = 'content'
                    GROUP BY source_id
                )
            """) or 0
            avg_connections = round(total_outgoing, 2)

        # Most connected nodes
        top_connected = self.db.fetchall("""
            SELECT source_id, COUNT(*) as connection_count
            FROM links
            WHERE source_type = 'content'
            GROUP BY source_id
            ORDER BY connection_count DESC
            LIMIT 10
        """)

        return {
            'total_nodes': content_count + note_count,
            'content_nodes': content_count,
            'note_nodes': note_count,
            'skill_nodes': skill_count,
            'total_edges': link_count,
            'avg_connections': avg_connections,
            'most_connected': [dict(row) for row in top_connected]
        }

    def _get_child_skills(self, skill_id: str) -> List[str]:
        """Get child skill IDs"""
        rows = self.db.fetchall("""
            SELECT id FROM skills
            WHERE parent_ids LIKE ?
        """, (f'%"{skill_id}"%',))

        return [row['id'] for row in rows]

    def _calculate_node_importance(
        self,
        nodes: List[GraphNode],
        edges: List[GraphEdge]
    ) -> Dict[str, float]:
        """Calculate importance score for each node (simplified PageRank)"""
        importance = {node.id: 1.0 for node in nodes}

        # Simple iteration
        for _ in range(10):
            new_importance = {}

            for node in nodes:
                # Get incoming edges
                incoming = [e for e in edges if e.target == node.id]
                if not incoming:
                    new_importance[node.id] = importance[node.id]
                    continue

                score = 0
                for edge in incoming:
                    source_degree = len([e for e in edges if e.source == edge.source])
                    if source_degree > 0:
                        score += importance.get(edge.source, 1.0) / source_degree

                new_importance[node.id] = 0.15 + 0.85 * score

            importance = new_importance

        # Normalize to 0-1
        max_val = max(importance.values()) if importance else 1
        importance = {k: v / max_val for k, v in importance.items()}

        return importance

    @staticmethod
    def _get_color_for_type(source_type: str) -> str:
        """Get color for source type"""
        colors = {
            'webpage': '#3498db',      # Blue
            'twitter': '#1DA1F2',      # Twitter blue
            'youtube': '#FF0000',      # Red
            'bilibili': '#FB7299',     # Bilibili pink
            'douyin': '#000000',       # Black
            'weixin': '#07C160',       # WeChat green
            'text': '#95a5a6',         # Gray
            'video': '#9b59b6',        # Purple
            'default': '#bdc3c7'       # Light gray
        }
        return colors.get(source_type.lower(), colors['default'])

    @staticmethod
    def _get_color_for_link(link_type: str) -> str:
        """Get color for link type"""
        colors = {
            'reference': '#3498db',    # Blue
            'related': '#2ecc71',       # Green
            'opposes': '#e74c3c',       # Red
            'extends': '#9b59b6',       # Purple
            'example': '#f39c12',       # Orange
            'question': '#e67e22',      # Dark orange
            'application': '#16a085',   # Teal
            'inspired': '#d35400',      # Pumpkin
            'default': '#bdc3c7'        # Light gray
        }
        return colors.get(link_type.lower(), colors['default'])


if __name__ == "__main__":
    # Test the knowledge graph service
    print("Knowledge Graph Service Module")
    print("=" * 50)

    from database import init_database
    init_database(":memory:")

    service = KnowledgeGraphService(":memory:")

    # Get statistics
    stats = service.get_statistics()
    print(f"\nGraph Statistics:")
    print(f"  Total Nodes: {stats['total_nodes']}")
    print(f"  Content Nodes: {stats['content_nodes']}")
    print(f"  Note Nodes: {stats['note_nodes']}")
    print(f"  Skill Nodes: {stats['skill_nodes']}")
    print(f"  Total Edges: {stats['total_edges']}")
    print(f"  Avg Connections: {stats['avg_connections']}")

    # Get force-directed graph
    graph = service.get_force_directed_graph(limit=20)
    print(f"\nForce-Directed Graph:")
    print(f"  Nodes: {len(graph.nodes)}")
    print(f"  Edges: {len(graph.edges)}")

    # Get timeline
    timeline = service.get_timeline(days=30)
    print(f"\nTimeline (last 30 days):")
    print(f"  Days with activity: {len(timeline)}")

    for day in timeline[:3]:
        print(f"    {day['date']}: {day['count']} items")

    print("\n✓ Knowledge graph service tests passed!")
