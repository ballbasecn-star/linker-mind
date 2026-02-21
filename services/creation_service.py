"""
Creation Workshop Service Module - Creative project management

This module manages creative projects separate from learning projects:
- Article/Blog post writing
- Video script creation
- Presentation preparation
- Book writing
- Course development
- Research reports
- Social media content

Features:
- Creation project CRUD
- Material/source management
- Outline generation and management
- Citation tracking
- Progress tracking
- Publishing workflow
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from database.db_interface import get_connection
from database import json_dumps, json_list, json_dict

logger = logging.getLogger(__name__)


class CreationType(Enum):
    """Types of creative projects"""
    ARTICLE = "article"                    # Blog post, article
    VIDEO_SCRIPT = "video_script"          # YouTube video script
    PRESENTATION = "presentation"          # Slide deck, talk
    BOOK = "book"                          # Book writing
    COURSE = "course"                      # Online course
    PODCAST = "podcast"                    # Podcast episode
    RESEARCH_REPORT = "research_report"    # Research paper/report
    SOCIAL_POST = "social_post"            # Social media content


class CreationStatus(Enum):
    """Status of a creation project"""
    RESEARCH = "research"                  # Gathering materials
    OUTLINING = "outlining"                # Creating outline
    DRAFTING = "drafting"                  # Writing first draft
    EDITING = "editing"                    # Revising and editing
    REVIEWING = "reviewing"                # Getting feedback
    FINALIZING = "finalizing"              # Final polish
    PUBLISHED = "published"                # Published


# AI Writing Workflow - Maps 5-step workflow to CreationStatus
# Reference: LawrenceW_Zen's "最小可闭环的AI写作工作流"
AI_WRITING_WORKFLOW = {
    # Article workflow steps
    'article': [
        {'step': '写草稿', 'status': CreationStatus.DRAFTING, 'description': '先把想法一股脑倒出来，不分结构'},
        {'step': '优化结构', 'status': CreationStatus.EDITING, 'description': '反复看草稿，补充内容，调整结构'},
        {'step': '总结全文', 'status': CreationStatus.REVIEWING, 'description': '思考主题、提炼标题'},
        {'step': '配图', 'status': CreationStatus.FINALIZING, 'description': '按标题或分段生成配图'},
        {'step': '发布平台', 'status': CreationStatus.PUBLISHED, 'description': '转换为平台富文本格式'}
    ],
    # Video script workflow
    'video_script': [
        {'step': '写脚本', 'status': CreationStatus.DRAFTING, 'description': '先把脚本内容倒出来'},
        {'step': '优化结构', 'status': CreationStatus.EDITING, 'description': '调整节奏和叙事结构'},
        {'step': '提炼标题', 'status': CreationStatus.REVIEWING, 'description': '思考标题和开场hook'},
        {'step': '配素材', 'status': CreationStatus.FINALIZING, 'description': '关联素材、添加画面描述'},
        {'step': '导出', 'status': CreationStatus.PUBLISHED, 'description': '导出为视频制作格式'}
    ],
    # Social post workflow
    'social_post': [
        {'step': '写内容', 'status': CreationStatus.DRAFTING, 'description': '把想法倒出来'},
        {'step': '优化表达', 'status': CreationStatus.EDITING, 'description': '调整表达，使其更有感染力'},
        {'step': '提炼标题', 'status': CreationStatus.REVIEWING, 'description': '思考标题和钩子'},
        {'step': '配图/Emoji', 'status': CreationStatus.FINALIZING, 'description': '添加配图和表情'},
        {'step': '发布', 'status': CreationStatus.PUBLISHED, 'description': '复制粘贴到平台'}
    ]
}


def get_workflow_for_type(project_type: str) -> List[Dict[str, Any]]:
    """Get the AI writing workflow for a project type"""
    return AI_WRITING_WORKFLOW.get(project_type, AI_WRITING_WORKFLOW['article'])


@dataclass
class OutlineSection:
    """A section in a creation outline"""
    id: str
    title: str
    content: Optional[str] = None
    order_index: int = 0
    word_count_goal: Optional[int] = None
    word_count_actual: int = 0
    source_materials: Optional[List[str]] = None
    status: str = "pending"                # pending, in_progress, completed
    notes: Optional[str] = None

    def __post_init__(self):
        if self.source_materials is None:
            self.source_materials = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CreationProject:
    """A creative project"""
    id: str
    project_type: str
    title: str
    brief: Optional[str] = None
    source_materials: Optional[List[str]] = None
    quotes: Optional[List[Dict[str, Any]]] = None
    inspirations: Optional[List[str]] = None
    outline: Optional[List[Dict[str, Any]]] = None
    sections: Optional[List[Dict[str, Any]]] = None
    draft_content: Optional[str] = None
    published_url: Optional[str] = None
    status: str = CreationStatus.RESEARCH.value
    progress: float = 0.0
    target_date: Optional[str] = None
    word_count_goal: Optional[int] = None
    word_count_actual: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    published_at: Optional[str] = None
    cover_image: Optional[str] = None
    images: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self):
        """Initialize defaults"""
        if self.source_materials is None:
            self.source_materials = []
        if self.quotes is None:
            self.quotes = []
        if self.inspirations is None:
            self.inspirations = []
        if self.outline is None:
            self.outline = []
        if self.sections is None:
            self.sections = []
        if self.images is None:
            self.images = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        # Handle list serialization
        for field in ['source_materials', 'quotes', 'inspirations', 'outline', 'sections', 'images']:
            if getattr(self, field):
                data[field] = json_dumps(getattr(self, field))
        return data

    def get_word_count_progress(self) -> float:
        """Get word count progress percentage"""
        if not self.word_count_goal or self.word_count_goal == 0:
            return 0.0
        return min(1.0, self.word_count_actual / self.word_count_goal)


class CreationWorkshopService:
    """
    Service for managing creative projects

    Separates creative output from learning:
    - Learning projects: focus on understanding and retention
    - Creation projects: focus on producing output
    """

    def __init__(self, db_path: str = "linker_mind.db"):
        self.db = get_connection()
        self.db_path = db_path

    def create(
        self,
        project_type: CreationType,
        title: str,
        brief: Optional[str] = None,
        target_date: Optional[str] = None,
        word_count_goal: Optional[int] = None
    ) -> CreationProject:
        """
        Create a new creation project

        Args:
            project_type: Type of creative project
            title: Project title
            brief: Brief description of the project
            target_date: Target completion date
            word_count_goal: Target word count

        Returns:
            Created CreationProject
        """
        id = self._generate_id()

        project = CreationProject(
            id=id,
            project_type=project_type.value,
            title=title,
            brief=brief,
            target_date=target_date,
            word_count_goal=word_count_goal,
            status=CreationStatus.RESEARCH.value,
            progress=0.0
        )

        self.db.insert("creation_projects", {
            'id': project.id,
            'project_type': project.project_type,
            'title': project.title,
            'brief': project.brief,
            'source_materials': json_dumps(project.source_materials),
            'quotes': json_dumps(project.quotes),
            'inspirations': json_dumps(project.inspirations),
            'outline': json_dumps(project.outline),
            'sections': json_dumps(project.sections),
            'draft_content': project.draft_content,
            'published_url': project.published_url,
            'status': project.status,
            'progress': project.progress,
            'target_date': project.target_date,
            'word_count_goal': project.word_count_goal,
            'word_count_actual': project.word_count_actual,
            'created_at': project.created_at,
            'updated_at': project.updated_at,
            'cover_image': project.cover_image,
            'images': json_dumps(project.images)
        })

        logger.info(f"Created creation project: {id} - {title}")
        return project

    def get_by_id(self, project_id: str) -> Optional[CreationProject]:
        """Get a creation project by ID"""
        row = self.db.fetchone(
            "SELECT * FROM creation_projects WHERE id = ?",
            (project_id,)
        )
        if row:
            return self._row_to_project(row)
        return None

    def get_by_type(
        self,
        project_type: CreationType,
        status: Optional[CreationStatus] = None
    ) -> List[CreationProject]:
        """Get all projects of a specific type"""
        sql = "SELECT * FROM creation_projects WHERE project_type = ?"
        params = (project_type.value,)

        if status:
            sql += " AND status = ?"
            params = params + (status.value,)

        sql += " ORDER BY created_at DESC"

        rows = self.db.fetchall(sql, params)
        return [self._row_to_project(row) for row in rows]

    def get_active_projects(self, limit: int = 20) -> List[CreationProject]:
        """Get all active (non-published) projects"""
        rows = self.db.fetchall("""
            SELECT * FROM creation_projects
            WHERE status != ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (CreationStatus.PUBLISHED.value, limit))

        return [self._row_to_project(row) for row in rows]

    def get_by_status(
        self,
        status: CreationStatus,
        limit: int = 50
    ) -> List[CreationProject]:
        """Get projects by status"""
        rows = self.db.fetchall("""
            SELECT * FROM creation_projects
            WHERE status = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (status.value, limit))

        return [self._row_to_project(row) for row in rows]

    def update(
        self,
        project_id: str,
        title: Optional[str] = None,
        brief: Optional[str] = None,
        status: Optional[CreationStatus] = None,
        draft_content: Optional[str] = None,
        progress: Optional[float] = None,
        target_date: Optional[str] = None,
        word_count_goal: Optional[int] = None,
        word_count_actual: Optional[int] = None,
        cover_image: Optional[str] = None,
        images: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[CreationProject]:
        """Update a creation project"""
        project = self.get_by_id(project_id)
        if not project:
            return None

        updates = {}

        if title is not None:
            updates['title'] = title
        if brief is not None:
            updates['brief'] = brief
        if status is not None:
            updates['status'] = status.value
            if status == CreationStatus.PUBLISHED and not project.published_at:
                updates['published_at'] = datetime.now().isoformat()
        if draft_content is not None:
            updates['draft_content'] = draft_content
        if progress is not None:
            updates['progress'] = max(0.0, min(1.0, progress))
        if target_date is not None:
            updates['target_date'] = target_date
        if word_count_goal is not None:
            updates['word_count_goal'] = word_count_goal
        if word_count_actual is not None:
            updates['word_count_actual'] = word_count_actual
        if cover_image is not None:
            updates['cover_image'] = cover_image
        if images is not None:
            updates['images'] = json_dumps(images)

        if updates:
            updates['updated_at'] = datetime.now().isoformat()
            self.db.update(
                "creation_projects",
                updates,
                "id = ?",
                (project_id,)
            )

        return self.get_by_id(project_id)

    def delete(self, project_id: str) -> bool:
        """Delete a creation project"""
        # Delete associated citations first
        self.db.delete("citations", "project_id = ?", (project_id,))

        # Delete project
        rows = self.db.delete("creation_projects", "id = ?", (project_id,))
        return rows > 0

    def add_source_material(
        self,
        project_id: str,
        content_id: str
    ) -> bool:
        """
        Add a source material to a project

        Args:
            project_id: Project ID
            content_id: Content ID to add as source

        Returns:
            True if added
        """
        project = self.get_by_id(project_id)
        if not project:
            return False

        if content_id not in project.source_materials:
            project.source_materials.append(content_id)
            self.db.update(
                "creation_projects",
                {'source_materials': json_dumps(project.source_materials)},
                "id = ?",
                (project_id,)
            )
            return True

        return False

    def remove_source_material(
        self,
        project_id: str,
        content_id: str
    ) -> bool:
        """Remove a source material from a project"""
        project = self.get_by_id(project_id)
        if not project:
            return False

        if content_id in project.source_materials:
            project.source_materials.remove(content_id)
            self.db.update(
                "creation_projects",
                {'source_materials': json_dumps(project.source_materials)},
                "id = ?",
                (project_id,)
            )
            return True

        return False

    def add_quote(
        self,
        project_id: str,
        content_id: str,
        quote_text: str,
        context: Optional[str] = None
    ) -> bool:
        """
        Add a quote from source material

        Args:
            project_id: Project ID
            content_id: Source content ID
            quote_text: Text being quoted
            context: Context or usage note

        Returns:
            True if added
        """
        project = self.get_by_id(project_id)
        if not project:
            return False

        quote = {
            'id': f"quote_{len(project.quotes)}_{datetime.now().timestamp()}",
            'content_id': content_id,
            'text': quote_text,
            'context': context,
            'added_at': datetime.now().isoformat()
        }

        project.quotes.append(quote)
        self.db.update(
            "creation_projects",
            {'quotes': json_dumps(project.quotes)},
            "id = ?",
            (project_id,)
        )

        return True

    def add_outline_section(
        self,
        project_id: str,
        title: str,
        content: Optional[str] = None,
        order_index: Optional[int] = None
    ) -> bool:
        """
        Add a section to the project outline

        Args:
            project_id: Project ID
            title: Section title
            content: Section content
            order_index: Position in outline

        Returns:
            True if added
        """
        project = self.get_by_id(project_id)
        if not project:
            return False

        if order_index is None:
            order_index = len(project.outline)

        section = OutlineSection(
            id=f"section_{datetime.now().timestamp()}",
            title=title,
            content=content,
            order_index=order_index
        )

        project.outline.append(asdict(section))
        project.outline.sort(key=lambda x: x.get('order_index', 0))

        self.db.update(
            "creation_projects",
            {'outline': json_dumps(project.outline)},
            "id = ?",
            (project_id,)
        )

        return True

    def update_outline_section(
        self,
        project_id: str,
        section_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        status: Optional[str] = None
    ) -> bool:
        """Update an outline section"""
        project = self.get_by_id(project_id)
        if not project:
            return False

        for section in project.outline:
            if section.get('id') == section_id:
                if title is not None:
                    section['title'] = title
                if content is not None:
                    section['content'] = content
                if status is not None:
                    section['status'] = status

                self.db.update(
                    "creation_projects",
                    {'outline': json_dumps(project.outline)},
                    "id = ?",
                    (project_id,)
                )
                return True

        return False

    def publish(
        self,
        project_id: str,
        url: str
    ) -> bool:
        """
        Mark a project as published

        Args:
            project_id: Project ID
            url: Published URL

        Returns:
            True if updated
        """
        return self.update(
            project_id,
            status=CreationStatus.PUBLISHED,
            published_url=url
        ) is not None

    def get_statistics(self, project_id: str) -> Dict[str, Any]:
        """Get statistics for a creation project"""
        project = self.get_by_id(project_id)
        if not project:
            return {}

        source_materials = self.db.fetchall("""
            SELECT id, title, source_type, created_at
            FROM contents
            WHERE id IN ({})
        """.format(','.join(['?' for _ in project.source_materials])),
            tuple(project.source_materials)
        ) if project.source_materials else []

        return {
            'total_source_materials': len(project.source_materials),
            'total_quotes': len(project.quotes),
            'outline_sections': len(project.outline),
            'word_count_goal': project.word_count_goal,
            'word_count_actual': project.word_count_actual,
            'word_count_progress': project.get_word_count_progress(),
            'source_materials': [dict(row) for row in source_materials]
        }

    def get_overdue_projects(self) -> List[CreationProject]:
        """Get projects that are past their target date"""
        now = datetime.now().isoformat()

        rows = self.db.fetchall("""
            SELECT * FROM creation_projects
            WHERE status != ? AND target_date IS NOT NULL AND target_date < ?
            ORDER BY target_date ASC
        """, (CreationStatus.PUBLISHED.value, now))

        return [self._row_to_project(row) for row in rows]

    def get_material_candidates(
        self,
        project_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Suggest source materials based on project tags/topics

        Args:
            project_id: Project ID
            limit: Maximum suggestions

        Returns:
            List of suggested content items
        """
        # This is a simplified implementation
        # A full version would analyze the project brief and find related content

        rows = self.db.fetchall("""
            SELECT id, title, summary, source_type, created_at
            FROM contents
            WHERE archived = 0
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        return [dict(row) for row in rows]

    def get_citation_list(
        self,
        project_id: str,
        format_type: str = "academic"
    ) -> List[str]:
        """
        Generate formatted citation list for the project

        Args:
            project_id: Project ID
            format_type: Citation format (academic, blog, social)

        Returns:
            List of formatted citations
        """
        project = self.get_by_id(project_id)
        if not project:
            return []

        citations = []

        for quote in project.quotes:
            content_id = quote.get('content_id')
            if not content_id:
                continue

            # Get content details
            content = self.db.fetchone(
                "SELECT title, url, metadata FROM contents WHERE id = ?",
                (content_id,)
            )

            if content:
                metadata = json_dict(content['metadata']) if content['metadata'] else {}
                citation = self._format_citation(
                    quote.get('text', ''),
                    content['title'],
                    content['url'],
                    metadata.get('author', ''),
                    format_type
                )
                citations.append(citation)

        return citations

    def _format_citation(
        self,
        quote_text: str,
        title: str,
        url: str,
        author: str,
        format_type: str
    ) -> str:
        """Format a single citation"""
        if format_type == "academic":
            parts = []
            if author:
                parts.append(author)
            parts.append(f'"{title}"')
            if url:
                parts.append(url)
            return " - ".join(parts)

        elif format_type == "blog":
            return f"[{title}]({url})"

        elif format_type == "social":
            return f'"{quote_text[:100]}..." - {title}'

        return f"{title} - {url}"

    def _row_to_project(self, row: Any) -> CreationProject:
        """Convert database row to CreationProject"""
        return CreationProject(
            id=row['id'],
            project_type=row['project_type'],
            title=row['title'],
            brief=row['brief'],
            source_materials=json_list(row['source_materials']),
            quotes=json_list(row['quotes']),
            inspirations=json_list(row['inspirations']),
            outline=json_list(row['outline']),
            sections=json_list(row['sections']),
            draft_content=row['draft_content'],
            published_url=row['published_url'],
            status=row['status'],
            progress=row['progress'],
            target_date=row['target_date'],
            word_count_goal=row['word_count_goal'],
            word_count_actual=row['word_count_actual'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            published_at=row['published_at'],
            cover_image=row.get('cover_image'),
            images=json_list(row.get('images'))
        )

    def _generate_id(self) -> str:
        """Generate unique project ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        count = self.db.fetchval("SELECT COUNT(*) FROM creation_projects") or 0
        return f"creation_{timestamp}_{count:03d}"


if __name__ == "__main__":
    # Test the creation workshop service
    print("Creation Workshop Service Module")
    print("=" * 50)

    from database import init_database
    init_database(":memory:")

    service = CreationWorkshopService(":memory:")

    # Create a test project
    project = service.create(
        CreationType.ARTICLE,
        "The Future of Productivity",
        brief="An article exploring new productivity paradigms",
        target_date="2024-06-01",
        word_count_goal=2000
    )

    print(f"Created project: {project.id} - {project.title}")

    # Add outline sections
    service.add_outline_section(project.id, "Introduction", "Hook the reader")
    service.add_outline_section(project.id, "Main Body - Section 1", "First key point")
    service.add_outline_section(project.id, "Main Body - Section 2", "Second key point")
    service.add_outline_section(project.id, "Conclusion", "Wrap up and call to action")

    # Update status
    service.update(project.id, status=CreationStatus.OUTLINING)

    # Get project
    updated = service.get_by_id(project.id)
    print(f"Project status: {updated.status}")
    print(f"Outline sections: {len(updated.outline)}")

    # Get statistics
    stats = service.get_statistics(project.id)
    print(f"Statistics: {stats}")

    print("\n✓ Creation workshop service tests passed!")
