"""
AI Creation Assistant Service Module - AI-powered creative support

This module provides AI assistance for creative projects:
- Outline generation from source materials
- Content gap analysis
- Section expansion
- Connection suggestions
- Citation management

Features:
- Generate outlines from materials
- Find content gaps
- Suggest connections
- Expand sections
- Generate citation lists
"""
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

from database.db_interface import get_connection
from database import json_dumps, json_list, json_dict

logger = logging.getLogger(__name__)


@dataclass
class OutlineSuggestion:
    """Suggested outline structure"""
    title: str
    description: Optional[str]
    suggested_sections: List[Dict[str, Any]]
    estimated_word_count: int
    confidence: float


@dataclass
class ContentGap:
    """Identified gap in source materials"""
    gap_type: str                    # missing_topic, insufficient_depth, need_example
    description: str
    suggested_search_terms: List[str]
    priority: int                    # 1-10, higher = more important


@dataclass
class ConnectionSuggestion:
    """Suggested connection between materials"""
    source_id: str
    target_id: str
    connection_type: str             # supports, contradicts, extends, example_of
    reason: str
    confidence: float


class AICreationAssistantService:
    """
    AI assistant service for creative projects

    Provides intelligent suggestions and automation
    for the creative workflow
    """

    def __init__(self, db_path: str = "linker_mind.db"):
        self.db = get_connection()
        self.db_path = db_path

    def suggest_outline(
        self,
        project_id: str,
        max_sections: int = 10
    ) -> Optional[OutlineSuggestion]:
        """
        Generate an outline suggestion based on source materials

        Args:
            project_id: Creation project ID
            max_sections: Maximum number of sections

        Returns:
            OutlineSuggestion or None
        """
        from services.creation_service import CreationWorkshopService
        from repositories.content_repository import ContentRepository

        creation_service = CreationWorkshopService(self.db_path)
        content_repo = ContentRepository(self.db_path)

        project = creation_service.get_by_id(project_id)
        if not project or not project.source_materials:
            return None

        # Get source materials
        materials = []
        for content_id in project.source_materials[:10]:  # Limit to 10 sources
            content = content_repo.find_by_id(content_id)
            if content:
                materials.append(content)

        if not materials:
            return None

        # Analyze materials and suggest outline structure
        sections = []
        section_counter = 1

        # Common section patterns by project type
        type_patterns = {
            'article': [
                {'title': 'Introduction', 'description': 'Hook and thesis'},
                {'title': 'Background', 'description': 'Context and history'},
                {'title': 'Main Points', 'description': 'Core arguments'},
                {'title': 'Evidence', 'description': 'Supporting examples'},
                {'title': 'Counterarguments', 'description': 'Address objections'},
                {'title': 'Conclusion', 'description': 'Summary and call to action'}
            ],
            'video_script': [
                {'title': 'Hook/Intro', 'description': 'Grab attention'},
                {'title': 'Problem Statement', 'description': 'Define the issue'},
                {'title': 'Solution Overview', 'description': 'Present approach'},
                {'title': 'How It Works', 'description': 'Step by step'},
                {'title': 'Examples', 'description': 'Real-world use cases'},
                {'title': 'Call to Action', 'description': 'What to do next'}
            ],
            'presentation': [
                {'title': 'Opening', 'description': 'Attention grabber'},
                {'title': 'The Problem', 'description': 'Why it matters'},
                {'title': 'The Solution', 'description': 'Your approach'},
                {'title': 'Proof/Evidence', 'description': 'Data and examples'},
                {'title': 'Benefits', 'description': 'What they gain'},
                {'title': 'Next Steps', 'description': 'How to proceed'}
            ]
        }

        # Get pattern for project type
        pattern = type_patterns.get(project.project_type, type_patterns['article'])

        # Customize sections based on materials
        for section_template in pattern[:max_sections]:
            # Find relevant content from materials
            relevant_content = self._find_relevant_content(
                section_template['title'],
                materials
            )

            section = {
                'id': f"section_{section_counter}",
                'title': section_template['title'],
                'description': section_template['description'],
                'content': '',
                'order_index': section_counter - 1,
                'source_materials': [c.id for c in relevant_content],
                'suggested_content': self._generate_section_content(section_template, relevant_content),
                'status': 'pending'
            }

            sections.append(section)
            section_counter += 1

        return OutlineSuggestion(
            title=project.title,
            description=project.brief,
            suggested_sections=sections,
            estimated_word_count=self._estimate_word_count(project.project_type, len(sections)),
            confidence=0.7
        )

    def find_gaps(
        self,
        project_id: str
    ) -> List[ContentGap]:
        """
        Find gaps in source materials

        Args:
            project_id: Creation project ID

        Returns:
            List of identified gaps
        """
        from services.creation_service import CreationWorkshopService
        from repositories.content_repository import ContentRepository

        creation_service = CreationWorkshopService(self.db_path)
        content_repo = ContentRepository(self.db_path)

        project = creation_service.get_by_id(project_id)
        if not project:
            return []

        gaps = []

        # Check for common gaps based on project type
        if project.project_type == 'article':
            # Check for evidence gaps
            evidence_count = sum(1 for q in project.quotes if 'evidence' in q.get('context', '').lower())
            if evidence_count < 2:
                gaps.append(ContentGap(
                    gap_type='insufficient_depth',
                    description='Need more supporting evidence and examples',
                    suggested_search_terms=['evidence', 'examples', 'case studies'],
                    priority=7
                ))

        # Check topic coverage
        topics = set()
        for content_id in project.source_materials:
            content = content_repo.find_by_id(content_id)
            if content:
                topics.update(content.get_ai_topics())

        # Common topics that might be missing
        common_topics = ['introduction', 'conclusion', 'background', 'examples', 'methodology']

        for topic in common_topics:
            if not any(topic in t.lower() for t in topics):
                gaps.append(ContentGap(
                    gap_type='missing_topic',
                    description=f'Missing coverage of: {topic}',
                    suggested_search_terms=[topic],
                    priority=5
                ))

        # Check for counterarguments
        has_counter = any(
            'counter' in q.get('context', '').lower() or 'opposing' in q.get('context', '').lower()
            for q in project.quotes
        )

        if not has_counter and project.project_type in ['article', 'research_report']:
            gaps.append(ContentGap(
                gap_type='missing_topic',
                description='Consider adding counterarguments and alternative perspectives',
                suggested_search_terms=['counterarguments', 'criticism', 'alternative views'],
                priority=6
            ))

        return gaps

    def suggest_connections(
        self,
        project_id: str,
        limit: int = 10
    ) -> List[ConnectionSuggestion]:
        """
        Suggest connections between source materials

        Args:
            project_id: Creation project ID
            limit: Maximum suggestions

        Returns:
            List of connection suggestions
        """
        from services.creation_service import CreationWorkshopService
        from repositories.content_repository import ContentRepository

        creation_service = CreationWorkshopService(self.db_path)
        content_repo = ContentRepository(self.db_path)

        project = creation_service.get_by_id(project_id)
        if not project or not project.source_materials:
            return []

        suggestions = []
        materials = project.source_materials

        # Find similar content that could be connected
        for i, content_id_1 in enumerate(materials):
            content_1 = content_repo.find_by_id(content_id_1)
            if not content_1:
                continue

            topics_1 = set(content_1.get_ai_topics())

            for content_id_2 in materials[i+1:]:
                content_2 = content_repo.find_by_id(content_id_2)
                if not content_2:
                    continue

                topics_2 = set(content_2.get_ai_topics())

                # Check topic overlap
                common_topics = topics_1 & topics_2

                if common_topics:
                    # Determine connection type
                    common = list(common_topics)

                    # Check if they support or contradict each other
                    connection_type = 'related'
                    reason = f"Both discuss: {', '.join(common[:3])}"

                    suggestions.append(ConnectionSuggestion(
                        source_id=content_id_1,
                        target_id=content_id_2,
                        connection_type=connection_type,
                        reason=reason,
                        confidence=len(common) / max(len(topics_1), len(topics_2))
                    ))

        # Sort by confidence and return
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        return suggestions[:limit]

    def expand_section(
        self,
        project_id: str,
        section_id: str,
        max_words: int = 500
    ) -> Optional[str]:
        """
        Generate content to expand a section

        Args:
            project_id: Creation project ID
            section_id: Section ID to expand
            max_words: Maximum word count for generated content

        Returns:
            Generated content or None
        """
        from services.creation_service import CreationWorkshopService

        creation_service = CreationWorkshopService(self.db_path)
        project = creation_service.get_by_id(project_id)

        if not project:
            return None

        # Find the section
        section = None
        for s in project.outline:
            if s.get('id') == section_id:
                section = s
                break

        if not section:
            return None

        # Get source materials for this section
        source_ids = section.get('source_materials', [])

        if not source_ids:
            # Use all project materials
            source_ids = project.source_materials

        # Generate content from source materials
        content_parts = []

        for content_id in source_ids[:5]:  # Limit to 5 sources
            content = self.db.fetchone(
                "SELECT title, summary, main_content FROM contents WHERE id = ?",
                (content_id,)
            )

            if content:
                if content['summary']:
                    content_parts.append(f"According to \"{content['title']}\", {content['summary']}")
                elif content['main_content']:
                    # Extract first paragraph or so
                    text = content['main_content'][:500]
                    content_parts.append(f"From \"{content['title']}\": {text}")

        if not content_parts:
            return None

        # Generate expanded content
        generated = f"# {section.get('title', 'Section')}\n\n"
        generated += "\n\n".join(content_parts[:3])

        return generated

    def generate_citations(
        self,
        project_id: str,
        format_type: str = "academic"
    ) -> List[str]:
        """
        Generate citation list for the project

        Args:
            project_id: Creation project ID
            format_type: Citation format (academic, blog, social)

        Returns:
            List of formatted citations
        """
        from services.creation_service import CreationWorkshopService

        creation_service = CreationWorkshopService(self.db_path)

        # Get citations from the creation service
        citations = creation_service.get_citation_list(project_id, format_type)

        return citations

    def suggest_keywords(self, project_id: str) -> List[str]:
        """
        Suggest keywords/hashtags for the project

        Args:
            project_id: Creation project ID

        Returns:
            List of suggested keywords
        """
        from services.creation_service import CreationWorkshopService
        from repositories.content_repository import ContentRepository

        creation_service = CreationWorkshopService(self.db_path)
        content_repo = ContentRepository(self.db_path)

        project = creation_service.get_by_id(project_id)
        if not project:
            return []

        # Collect topics from all source materials
        all_topics = []
        for content_id in project.source_materials:
            content = content_repo.find_by_id(content_id)
            if content:
                all_topics.extend(content.get_ai_topics())

        # Get unique topics
        unique_topics = list(set(all_topics))

        # Sort by frequency
        topic_counts = {}
        for topic in all_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

        # Return top topics
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, count in sorted_topics[:15]]

    def estimate_reading_time(self, project_id: str) -> Optional[Dict[str, int]]:
        """
        Estimate reading time for the project

        Args:
            project_id: Creation project ID

        Returns:
            Dictionary with time estimates in minutes
        """
        from services.creation_service import CreationWorkshopService

        creation_service = CreationWorkshopService(self.db_path)
        project = creation_service.get_by_id(project_id)

        if not project:
            return None

        word_count = project.word_count_actual or project.word_count_goal or 0

        # Average reading speeds (words per minute)
        reading_speeds = {
            'slow': 150,
            'average': 250,
            'fast': 400
        }

        return {
            'slow_minutes': word_count // reading_speeds['slow'],
            'average_minutes': word_count // reading_speeds['average'],
            'fast_minutes': word_count // reading_speeds['fast'],
            'word_count': word_count
        }

    def _find_relevant_content(
        self,
        section_title: str,
        materials: List[Any]
    ) -> List[Any]:
        """Find materials relevant to a section"""
        title_lower = section_title.lower()

        relevant = []

        # Check by AI topics
        for material in materials:
            topics = material.get_ai_topics()
            for topic in topics:
                if any(word in topic.lower() for word in title_title_lower.split()):
                    relevant.append(material)
                    break

        # If no matches by topics, check title/summary
        if not relevant:
            for material in materials:
                title = material.title or ""
                summary = material.summary or ""

                if any(word in title.lower() for word in title_title_lower.split()):
                    relevant.append(material)
                elif summary and any(word in summary.lower() for word in title_title_lower.split()):
                    relevant.append(material)

        return relevant[:5]  # Limit to 5 materials

    def _generate_section_content(
        self,
        section_template: Dict[str, Any],
        materials: List[Any]
    ) -> str:
        """Generate suggested content for a section"""
        if not materials:
            return f"[Add content for {section_template['title']}]"

        # Use the first material's summary as base
        material = materials[0]
        if material.summary:
            return material.summary[:200]
        elif material.main_content:
            return material.main_content[:200]

        return "[Add content here]"

    def _estimate_word_count(self, project_type: str, section_count: int) -> int:
        """Estimate total word count based on type and sections"""
        base_words = {
            'article': 1500,
            'video_script': 2000,
            'presentation': 800,
            'book': 50000,
            'course': 10000,
            'podcast': 3000,
            'research_report': 5000,
            'social_post': 200
        }

        base = base_words.get(project_type, 1500)
        return base + (section_count * 200)


if __name__ == "__main__":
    # Test the AI creation assistant service
    print("AI Creation Assistant Service Module")
    print("=" * 50)

    from database import init_database
    init_database(":memory:")

    assistant = AICreationAssistantService(":memory:")

    # Create a test project and materials
    from services.creation_service import CreationWorkshopService, CreationType
    from repositories.content_repository import Content, ContentRepository

    creation_service = CreationWorkshopService(":memory:")
    content_repo = ContentRepository(":memory:")

    project = creation_service.create(
        CreationType.ARTICLE,
        "Test Article for AI Assistant",
        brief="Testing the AI outline generation"
    )

    # Add some test content
    test_content_1 = Content(
        id="test_content_1",
        source_type="webpage",
        content_type="article",
        title="Productivity Tips",
        url="https://example.com/productivity",
        summary="This article discusses various productivity techniques",
        ai_analysis={
            'topics': ['productivity', 'time management', 'focus']
        }
    )

    test_content_2 = Content(
        id="test_content_2",
        source_type="webpage",
        content_type="article",
        title="Time Management Strategies",
        url="https://example.com/time",
        summary="Learn to manage your time effectively",
        ai_analysis={
            'topics': ['productivity', 'time management', 'planning']
        }
    )

    content_repo.insert(test_content_1)
    content_repo.insert(test_content_2)

    creation_service.add_source_material(project.id, test_content_1.id)
    creation_service.add_source_material(project.id, test_content_2.id)

    # Test outline generation
    outline = assistant.suggest_outline(project.id)
    if outline:
        print(f"Generated outline: {outline.title}")
        print(f"Sections: {len(outline.suggested_sections)}")
        for section in outline.suggested_sections[:3]:
            print(f"  - {section['title']}: {section['description']}")

    # Test gap analysis
    gaps = assistant.find_gaps(project.id)
    print(f"\nFound {len(gaps)} gaps:")
    for gap in gaps:
        print(f"  - {gap.gap_type}: {gap.description}")

    # Test connection suggestions
    connections = assistant.suggest_connections(project.id)
    print(f"\nFound {len(connections)} connections:")
    for conn in connections[:3]:
        print(f"  - {conn.source_id} -> {conn.target_id}: {conn.reason}")

    # Test keyword suggestions
    keywords = assistant.suggest_keywords(project.id)
    print(f"\nSuggested keywords: {keywords}")

    print("\n✓ AI creation assistant tests passed!")
