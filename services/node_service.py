"""
Node Service Module - PARA organization system

This module implements the PARA method for organizing knowledge:
- Projects: Short-term efforts with specific goals
- Areas: Long-term responsibilities/areas of interest
- Resources: Topics you're interested in
- Archive: Completed or inactive items

Features:
- Node CRUD operations
- Hierarchical organization
- Content-node associations
- Statistics and insights
"""
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from database.db_interface import get_connection
from database.connection import json_dumps, json_dict, json_list

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """PARA node types"""
    PROJECT = "PROJECT"       # Short-term efforts with specific goals and timelines
    AREA = "AREA"            # Long-term responsibilities and areas of interest
    RESOURCE = "RESOURCE"     # Topics of ongoing interest
    ARCHIVE = "ARCHIVE"       # Completed or inactive items
    CUSTOM = "CUSTOM"         # User-defined types


class NodeStatus(Enum):
    """Node status values"""
    ACTIVE = "ACTIVE"               # Currently active
    INACTIVE = "INACTIVE"           # Temporarily inactive
    COMPLETED = "COMPLETED"         # Successfully completed
    ARCHIVED = "ARCHIVED"           # Archived
    PAUSED = "PAUSED"              # On hold


@dataclass
class OrganizationNode:
    """PARA organization node"""
    id: str
    node_type: str                 # PROJECT, AREA, RESOURCE, ARCHIVE, CUSTOM
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    order_index: int = 0
    status: str = NodeStatus.ACTIVE.value
    color: str = "#3498db"
    icon: str = "📁"
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    target_date: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        """Initialize defaults"""
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        # Handle tags and metadata serialization
        if self.tags:
            data['tags'] = json_dumps(self.tags)
        if self.metadata:
            data['metadata'] = json_dumps(self.metadata)
        return data

    def is_active(self) -> bool:
        """Check if node is active"""
        return self.status == NodeStatus.ACTIVE.value

    def is_project(self) -> bool:
        """Check if node is a project"""
        return self.node_type == NodeType.PROJECT.value

    def is_completed(self) -> bool:
        """Check if node is completed"""
        return self.status == NodeStatus.COMPLETED.value


@dataclass
class NodeStats:
    """Statistics for a node"""
    content_count: int
    with_notes_count: int
    by_content_type: Dict[str, int]
    children_count: int
    total_reading_progress: float


class NodeService:
    """
    Service for managing PARA organization nodes

    Implements the PARA method for organizing knowledge:
    - Projects: Short-term, goal-oriented efforts
    - Areas: Long-term responsibilities and areas of interest
    - Resources: Topics of ongoing interest for future reference
    - Archive: Completed or inactive items
    """

    def __init__(self, db_path: str = "linker_mind.db"):
        self.db = get_connection()
        self.db_path = db_path

    def create(
        self,
        node_type: NodeType,
        name: str,
        description: Optional[str] = None,
        parent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        color: Optional[str] = None,
        icon: Optional[str] = None,
        target_date: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> OrganizationNode:
        """
        Create a new organization node

        Args:
            node_type: Type of node (PROJECT, AREA, RESOURCE, ARCHIVE, CUSTOM)
            name: Node name
            description: Optional description
            parent_id: Optional parent node ID
            tags: Optional tags
            color: Optional color hex
            icon: Optional icon emoji
            target_date: Optional target completion date
            metadata: Optional additional metadata

        Returns:
            Created OrganizationNode
        """
        id = self._generate_id(node_type)

        # Set default color and icon based on type
        if not color:
            color = self._get_default_color(node_type)
        if not icon:
            icon = self._get_default_icon(node_type)

        # Set max order index for parent
        order_index = 0
        if parent_id:
            max_order = self.db.fetchval(
                "SELECT MAX(order_index) FROM nodes WHERE parent_id = ?",
                (parent_id,)
            )
            if max_order is not None:
                order_index = max_order + 1

        node = OrganizationNode(
            id=id,
            node_type=node_type.value,
            name=name,
            description=description,
            parent_id=parent_id,
            order_index=order_index,
            status=NodeStatus.ACTIVE.value,
            color=color,
            icon=icon,
            tags=tags or [],
            metadata=metadata or {},
            target_date=target_date
        )

        self.db.insert("nodes", {
            'id': node.id,
            'node_type': node.node_type,
            'name': node.name,
            'description': node.description,
            'parent_id': node.parent_id,
            'order_index': node.order_index,
            'status': node.status,
            'color': node.color,
            'icon': node.icon,
            'tags': json_dumps(node.tags),
            'metadata': json_dumps(node.metadata),
            'target_date': node.target_date,
            'created_at': node.created_at,
            'updated_at': node.updated_at
        })

        logger.info(f"Created node: {node.id} ({node.node_type}) - {node.name}")
        return node

    def get_by_id(self, node_id: str) -> Optional[OrganizationNode]:
        """Get a node by ID"""
        row = self.db.fetchone(
            "SELECT * FROM nodes WHERE id = ?",
            (node_id,)
        )
        if row:
            return self._row_to_node(row)
        return None

    def get_by_type(
        self,
        node_type: NodeType,
        status: Optional[NodeStatus] = None,
        limit: int = 100
    ) -> List[OrganizationNode]:
        """Get all nodes of a specific type"""
        sql = "SELECT * FROM nodes WHERE node_type = ?"
        params = (node_type.value,)

        if status:
            sql += " AND status = ?"
            params = params + (status.value,)

        sql += " ORDER BY order_index, name ASC LIMIT ?"
        params = params + (limit,)

        rows = self.db.fetchall(sql, params)
        return [self._row_to_node(row) for row in rows]

    def get_projects(
        self,
        active_only: bool = True,
        limit: int = 100
    ) -> List[OrganizationNode]:
        """Get all project nodes"""
        if active_only:
            return self.get_by_type(
                NodeType.PROJECT,
                status=NodeStatus.ACTIVE,
                limit=limit
            )
        return self.get_by_type(NodeType.PROJECT, limit=limit)

    def get_areas(self, limit: int = 50) -> List[OrganizationNode]:
        """Get all area nodes"""
        return self.get_by_type(NodeType.AREA, limit=limit)

    def get_resources(self, limit: int = 100) -> List[OrganizationNode]:
        """Get all resource nodes"""
        return self.get_by_type(NodeType.RESOURCE, limit=limit)

    def get_archive(self, limit: int = 100) -> List[OrganizationNode]:
        """Get archived nodes"""
        return self.get_by_type(NodeType.ARCHIVE, limit=limit)

    def get_children(
        self,
        parent_id: str,
        include_inactive: bool = False
    ) -> List[OrganizationNode]:
        """Get child nodes of a parent"""
        sql = "SELECT * FROM nodes WHERE parent_id = ?"
        params = (parent_id,)

        if not include_inactive:
            sql += " AND status = ?"
            params = params + (NodeStatus.ACTIVE.value,)

        sql += " ORDER BY order_index ASC"

        rows = self.db.fetchall(sql, params)
        return [self._row_to_node(row) for row in rows]

    def get_tree(
        self,
        root_id: Optional[str] = None,
        max_depth: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get node tree structure

        Args:
            root_id: Root node ID (None for all root nodes)
            max_depth: Maximum depth to traverse

        Returns:
            List of node dictionaries with children
        """
        if root_id:
            root = self.get_by_id(root_id)
            if not root:
                return []
            return [self._build_tree(root, max_depth)]

        # Get all root nodes (no parent)
        roots = self.db.fetchall(
            "SELECT * FROM nodes WHERE parent_id IS NULL ORDER BY order_index ASC"
        )

        return [self._build_tree(self._row_to_node(row), max_depth) for row in roots]

    def _build_tree(
        self,
        node: OrganizationNode,
        max_depth: int,
        current_depth: int = 0
    ) -> Dict[str, Any]:
        """Build tree structure recursively"""
        data = {
            'node': node,
            'depth': current_depth,
            'children': []
        }

        if current_depth < max_depth:
            children = self.get_children(node.id)
            data['children'] = [
                self._build_tree(child, max_depth, current_depth + 1)
                for child in children
            ]

        return data

    def update(
        self,
        node_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[NodeStatus] = None,
        tags: Optional[List[str]] = None,
        color: Optional[str] = None,
        icon: Optional[str] = None,
        target_date: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[OrganizationNode]:
        """Update a node"""
        node = self.get_by_id(node_id)
        if not node:
            return None

        updates = {}

        if name is not None:
            updates['name'] = name
        if description is not None:
            updates['description'] = description
        if status is not None:
            updates['status'] = status.value
            # Handle status-specific updates
            if status == NodeStatus.COMPLETED and not node.completed_at:
                updates['completed_at'] = datetime.now().isoformat()
            elif status == NodeStatus.ACTIVE and not node.started_at:
                updates['started_at'] = datetime.now().isoformat()
        if tags is not None:
            updates['tags'] = json_dumps(tags)
        if color is not None:
            updates['color'] = color
        if icon is not None:
            updates['icon'] = icon
        if target_date is not None:
            updates['target_date'] = target_date
        if metadata is not None:
            updates['metadata'] = json_dumps(metadata)

        if updates:
            updates['updated_at'] = datetime.now().isoformat()
            self.db.update(
                "nodes",
                updates,
                "id = ?",
                (node_id,)
            )

        return self.get_by_id(node_id)

    def delete(self, node_id: str, cascade: bool = False) -> bool:
        """
        Delete a node

        Args:
            node_id: Node ID to delete
            cascade: If True, also delete all children

        Returns:
            True if deleted
        """
        # Check for children
        children = self.get_children(node_id, include_inactive=True)

        if children and not cascade:
            logger.warning(f"Cannot delete node {node_id}: has children")
            return False

        if cascade:
            for child in children:
                self.delete(child.id, cascade=True)

        # Delete content associations
        self.db.delete("node_contents", "node_id = ?", (node_id,))

        # Delete the node
        rows = self.db.delete("nodes", "id = ?", (node_id,))
        return rows > 0

    def add_content(
        self,
        node_id: str,
        content_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Add content to a node

        Args:
            node_id: Node ID
            content_id: Content ID
            notes: Optional notes about the association

        Returns:
            True if added
        """
        # Check if node exists
        if not self.get_by_id(node_id):
            return False

        # Check if already associated
        existing = self.db.fetchone(
            "SELECT * FROM node_contents WHERE node_id = ? AND content_id = ?",
            (node_id, content_id)
        )
        if existing:
            return False

        self.db.insert("node_contents", {
            'node_id': node_id,
            'content_id': content_id,
            'added_at': datetime.now().isoformat(),
            'order_index': 0,
            'notes': notes
        })

        return True

    def remove_content(self, node_id: str, content_id: str) -> bool:
        """Remove content from a node"""
        rows = self.db.delete(
            "node_contents",
            "node_id = ? AND content_id = ?",
            (node_id, content_id)
        )
        return rows > 0

    def get_content(
        self,
        node_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all content associated with a node

        Args:
            node_id: Node ID
            limit: Maximum content items

        Returns:
            List of content dictionaries
        """
        rows = self.db.fetchall("""
            SELECT c.*,
                   nc.added_at as associated_at,
                   nc.notes as association_notes
            FROM node_contents nc
            JOIN contents c ON nc.content_id = c.id
            WHERE nc.node_id = ?
            ORDER BY nc.added_at DESC
            LIMIT ?
        """, (node_id, limit))

        # Convert datetime objects to ISO strings
        def to_iso(dt):
            if dt is None:
                return None
            if isinstance(dt, datetime):
                return dt.isoformat()
            return str(dt)

        result = []
        for row in rows:
            row_dict = dict(row)
            # Convert datetime columns
            for key in ['created_at', 'updated_at', 'processed_at', 'associated_at']:
                if key in row_dict and row_dict[key] is not None:
                    if isinstance(row_dict[key], datetime):
                        row_dict[key] = row_dict[key].isoformat()
            result.append(row_dict)

        return result

    def get_stats(self, node_id: str) -> Optional[NodeStats]:
        """
        Get statistics for a node

        Args:
            node_id: Node ID

        Returns:
            NodeStats or None if node not found
        """
        if not self.get_by_id(node_id):
            return None

        # Content count
        content_count = self.db.fetchval(
            "SELECT COUNT(*) FROM node_contents WHERE node_id = ?",
            (node_id,)
        ) or 0

        # With notes count
        with_notes_count = self.db.fetchval("""
            SELECT COUNT(*) FROM node_contents
            WHERE node_id = ? AND notes IS NOT NULL AND notes != ''
        """, (node_id,)) or 0

        # By content type
        type_rows = self.db.fetchall("""
            SELECT c.content_type, COUNT(*) as count
            FROM node_contents nc
            JOIN contents c ON nc.content_id = c.id
            WHERE nc.node_id = ?
            GROUP BY c.content_type
        """, (node_id,))
        by_content_type = {row['content_type']: row['count'] for row in type_rows}

        # Children count
        children_count = self.db.fetchval(
            "SELECT COUNT(*) FROM nodes WHERE parent_id = ?",
            (node_id,)
        ) or 0

        # Total reading progress
        progress_row = self.db.fetchone("""
            SELECT COALESCE(AVG(c.reading_progress), 0) as avg_progress
            FROM node_contents nc
            JOIN contents c ON nc.content_id = c.id
            WHERE nc.node_id = ?
        """, (node_id,))
        total_reading_progress = progress_row['avg_progress'] if progress_row else 0

        return NodeStats(
            content_count=content_count,
            with_notes_count=with_notes_count,
            by_content_type=by_content_type,
            children_count=children_count,
            total_reading_progress=round(total_reading_progress, 2)
        )

    def get_all_tags(self) -> List[str]:
        """Get all unique tags across all nodes"""
        rows = self.db.fetchall("SELECT tags FROM nodes WHERE tags IS NOT NULL")

        all_tags = set()
        for row in rows:
            tags = json_list(row['tags'])
            all_tags.update(tags)

        return sorted(list(all_tags))

    def find_by_tag(self, tag: str, limit: int = 50) -> List[OrganizationNode]:
        """Find nodes with a specific tag"""
        all_nodes = self.db.fetchall(
            "SELECT * FROM nodes WHERE tags IS NOT NULL ORDER BY name LIMIT 500"
        )

        matching = []
        for row in all_nodes:
            tags = json_list(row['tags'])
            if tag.lower() in [t.lower() for t in tags]:
                matching.append(self._row_to_node(row))
            if len(matching) >= limit:
                break

        return matching

    def search(self, query: str, limit: int = 50) -> List[OrganizationNode]:
        """Search nodes by name or description"""
        search_query = f"%{query}%"

        rows = self.db.fetchall("""
            SELECT * FROM nodes
            WHERE (name LIKE ? OR description LIKE ?)
            ORDER BY name ASC
            LIMIT ?
        """, (search_query, search_query, limit))

        return [self._row_to_node(row) for row in rows]

    def move(
        self,
        node_id: str,
        new_parent_id: Optional[str],
        new_index: Optional[int] = None
    ) -> bool:
        """
        Move a node to a new parent

        Args:
            node_id: Node to move
            new_parent_id: New parent ID (None for root)
            new_index: Optional new order index

        Returns:
            True if moved
        """
        node = self.get_by_id(node_id)
        if not node:
            return False

        # Check for circular reference
        if new_parent_id:
            current = new_parent_id
            visited = {node_id}
            while current:
                if current == node_id:
                    logger.error(f"Circular reference detected for {node_id}")
                    return False
                parent = self.get_by_id(current)
                if not parent:
                    break
                current = parent.parent_id

        updates = {'parent_id': new_parent_id}

        if new_index is not None:
            updates['order_index'] = new_index
        else:
            # Place at end
            max_order = self.db.fetchval(
                "SELECT MAX(order_index) FROM nodes WHERE parent_id " +
                ("IS NULL" if new_parent_id is None else "= ?"),
                () if new_parent_id is None else (new_parent_id,)
            )
            updates['order_index'] = (max_order or 0) + 1

        rows = self.db.update(
            "nodes",
            updates,
            "id = ?",
            (node_id,)
        )

        return rows > 0

    def get_overdue_projects(self) -> List[OrganizationNode]:
        """Get projects that are past their target date"""
        now = datetime.now().isoformat()

        rows = self.db.fetchall("""
            SELECT * FROM nodes
            WHERE node_type = ? AND status = ? AND target_date IS NOT NULL AND target_date < ?
            ORDER BY target_date ASC
        """, (NodeType.PROJECT.value, NodeStatus.ACTIVE.value, now))

        return [self._row_to_node(row) for row in rows]

    def get_recently_completed(self, limit: int = 10) -> List[OrganizationNode]:
        """Get recently completed projects"""
        rows = self.db.fetchall("""
            SELECT * FROM nodes
            WHERE status = ? AND completed_at IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT ?
        """, (NodeStatus.COMPLETED.value, limit))

        return [self._row_to_node(row) for row in rows]

    def _row_to_node(self, row: Any) -> OrganizationNode:
        """Convert database row to OrganizationNode"""

        # Helper to convert datetime to ISO string
        def to_iso(dt):
            if dt is None:
                return None
            if isinstance(dt, datetime):
                return dt.isoformat()
            return str(dt)

        return OrganizationNode(
            id=row['id'],
            node_type=row['node_type'],
            name=row['name'],
            description=row['description'],
            parent_id=row['parent_id'],
            order_index=row['order_index'],
            status=row['status'],
            color=row['color'],
            icon=row['icon'],
            tags=json_list(row['tags']),
            metadata=json_dict(row['metadata']),
            target_date=to_iso(row['target_date']),
            started_at=to_iso(row['started_at']),
            completed_at=to_iso(row['completed_at']),
            created_at=to_iso(row['created_at']),
            updated_at=to_iso(row['updated_at'])
        )

    def _generate_id(self, node_type: NodeType) -> str:
        """Generate unique node ID"""
        prefix = {
            NodeType.PROJECT: "proj",
            NodeType.AREA: "area",
            NodeType.RESOURCE: "res",
            NodeType.ARCHIVE: "arch",
            NodeType.CUSTOM: "node"
        }
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        count = self.db.fetchval("SELECT COUNT(*) FROM nodes") or 0
        return f"{prefix[node_type]}_{timestamp}_{count:03d}"

    def _get_default_color(self, node_type: NodeType) -> str:
        """Get default color for node type"""
        colors = {
            NodeType.PROJECT: "#e74c3c",    # Red
            NodeType.AREA: "#3498db",       # Blue
            NodeType.RESOURCE: "#2ecc71",   # Green
            NodeType.ARCHIVE: "#95a5a6",    # Gray
            NodeType.CUSTOM: "#9b59b6"      # Purple
        }
        return colors.get(node_type, "#95a5a6")

    def _get_default_icon(self, node_type: NodeType) -> str:
        """Get default icon for node type"""
        icons = {
            NodeType.PROJECT: "🚀",
            NodeType.AREA: "📁",
            NodeType.RESOURCE: "📚",
            NodeType.ARCHIVE: "📦",
            NodeType.CUSTOM: "🏷️"
        }
        return icons.get(node_type, "📁")


# Preset tags for organization
PRESET_NODE_TAGS = {
    'work': '💼 Work',
    'personal': '👤 Personal',
    'learning': '📖 Learning',
    'creative': '🎨 Creative',
    'finance': '💰 Finance',
    'health': '🏃 Health',
    'relationships': '❤️ Relationships',
    'development': '💻 Development',
    'design': '🎨 Design',
    'writing': '✍️ Writing',
    'research': '🔬 Research',
    'business': '📊 Business'
}


if __name__ == "__main__":
    # Test the node service
    print("Node Service Module")
    print("=" * 50)

    from database.connection import init_database
    init_database(":memory:")

    service = NodeService(":memory:")

    # Create some test nodes
    area = service.create(
        NodeType.AREA,
        "Web Development",
        description="Skills and resources for web development",
        tags=["learning", "development"]
    )

    project = service.create(
        NodeType.PROJECT,
        "Build Portfolio Website",
        description="Create a personal portfolio website",
        parent_id=area.id,
        target_date="2024-06-01"
    )

    resource = service.create(
        NodeType.RESOURCE,
        "Design Inspiration",
        description="Collection of design resources and inspiration",
        tags=["design", "creative"]
    )

    print(f"Created nodes: {area.id}, {project.id}, {resource.id}")

    # Get projects
    projects = service.get_projects()
    print(f"Active projects: {len(projects)}")

    # Get tree
    tree = service.get_tree(root_id=area.id)
    print(f"Tree for {area.name}: {len(tree[0]['children'])} children")

    # Get stats
    stats = service.get_stats(project.id)
    print(f"Project stats: {stats}")

    print("\n✓ Node service tests passed!")
