"""
AI Creation Assistant Service Module - AI-powered creative support

This module provides AI assistance for creative projects:
- Outline generation from source materials
- Content gap analysis
- Section expansion
- Connection suggestions
- Citation management
- AI Writing Workflow (based on LawrenceW_Zen's 最小可闭环的AI写作工作流)
- Markdown parsing with inline image generation
- WeChat HTML formatting

Features:
- Generate outlines from materials
- Find content gaps
- Suggest connections
- Expand sections
- Generate citation lists
- Generate draft from materials
- Suggest structural improvements (A/B versions)
- Generate titles
- Convert to platform format
- Markdown to HTML conversion
- Inline AI image generation (using generate: syntax)
- WeChat HTML export with inline styles
"""
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import logging
from dotenv import load_dotenv

# Markdown support
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False
    logging.warning("markdown library not installed, Markdown parsing will be limited")

# Load environment variables
load_dotenv()

from database.db_interface import get_connection
from database import json_dumps, json_list, json_dict

logger = logging.getLogger(__name__)


def get_llm_client():
    """Get LLM client for AI generation"""
    try:
        from openai import OpenAI
        api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('DEEPSEEK_API_KEY')
        base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.deepseek.com')

        if api_key:
            return OpenAI(api_key=api_key, base_url=base_url)
    except Exception as e:
        logger.warning(f"Failed to initialize LLM client: {e}")
    return None


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

        # Use a single query with IN clause instead of multiple queries
        if source_ids[:5]:
            placeholders = ','.join(['%s'] * len(source_ids[:5]))
            query = f"SELECT title, summary, main_content FROM contents WHERE id IN ({placeholders})"
            rows = self.db.fetchall(query, tuple(source_ids[:5]))

            for content in rows:
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

    # ============== AI Writing Workflow Methods ==============

    def generate_draft(
        self,
        project_id: str,
        target_words: int = 1000
    ) -> Optional[Dict[str, Any]]:
        """
        Generate initial draft from source materials
        Based on the "写草稿" step of AI writing workflow

        Args:
            project_id: Creation project ID
            target_words: Target word count for the draft

        Returns:
            Dictionary with generated draft content
        """
        from services.creation_service import CreationWorkshopService

        creation_service = CreationWorkshopService(self.db_path)

        project = creation_service.get_by_id(project_id)
        if not project:
            return None

        # Get source materials - use direct DB query instead of repository
        materials_data = []
        if project.source_materials:
            # Build a single query with IN clause to avoid multiple DB calls
            placeholders = ','.join(['%s'] * len(project.source_materials[:10]))
            query = f"SELECT id, title, summary, ai_analysis FROM contents WHERE id IN ({placeholders})"
            params = tuple(project.source_materials[:10])

            rows = self.db.fetchall(query, params)

            for row in rows:
                # Parse AI analysis for topics
                topics = []
                try:
                    import json
                    ai_analysis = row.get('ai_analysis')
                    if ai_analysis:
                        if isinstance(ai_analysis, str):
                            ai_data = json.loads(ai_analysis)
                        else:
                            ai_data = ai_analysis
                        topics = ai_data.get('topics', [])
                except:
                    pass

                materials_data.append({
                    'title': row.get('title', ''),
                    'summary': row.get('summary', '') or '',
                    'topics': topics,
                    'main_content': ''
                })

        if not materials_data:
            # 无素材时返回提示信息，让用户手动撰写
            return {
                'draft': '',
                'word_count': 0,
                'source_count': 0,
                'message': '暂无素材，请先添加素材或手动撰写初稿',
                'need_manual': True
            }

        # Build prompt for draft generation
        prompt = self._build_draft_prompt(project, materials_data, target_words)

        # Call LLM
        draft_content = self._call_llm(prompt)

        if draft_content:
            return {
                'draft': draft_content,
                'word_count': len(draft_content.split()),
                'source_count': len(materials_data)
            }

        return {'error': 'Failed to generate draft', 'draft': ''}

    def suggest_structural_improvements(
        self,
        project_id: str,
        draft_content: str
    ) -> Optional[Dict[str, Any]]:
        """
        Suggest A/B structural improvements for draft
        Based on the "优化结构" step of AI writing workflow

        Args:
            project_id: Creation project ID
            draft_content: The current draft content

        Returns:
            Dictionary with A/B version suggestions
        """
        from services.creation_service import CreationWorkshopService

        creation_service = CreationWorkshopService(self.db_path)
        project = creation_service.get_by_id(project_id)

        if not project:
            return None

        # Build prompt for structural improvement
        prompt = self._build_structure_prompt(project, draft_content)

        # Call LLM
        result = self._call_llm(prompt)

        if result:
            # Try to parse A/B versions
            try:
                versions = self._parse_structural_suggestions(result)
                return versions
            except Exception as e:
                logger.warning(f"Failed to parse structural suggestions: {e}")

        return {
            'version_a': {'structure': 'Linear flow', 'changes': []},
            'version_b': {'structure': 'Problem-Solution', 'changes': []}
        }

    def generate_titles(
        self,
        project_id: str,
        content: str,
        num_titles: int = 5
    ) -> Optional[List[Dict[str, str]]]:
        """
        Generate title suggestions
        Based on the "总结全文" step of AI writing workflow

        Args:
            project_id: Creation project ID
            content: The full content
            num_titles: Number of titles to generate

        Returns:
            List of title suggestions with types
        """
        from services.creation_service import CreationWorkshopService

        creation_service = CreationWorkshopService(self.db_path)
        project = creation_service.get_by_id(project_id)

        if not project:
            logger.warning(f"Project not found: {project_id}")
            return None

        # Build prompt for title generation
        prompt = self._build_title_prompt(project, content, num_titles)
        logger.info(f"Generating titles for project {project_id}, content length: {len(content)}")

        # Call LLM
        result = self._call_llm(prompt)
        logger.info(f"LLM result length: {len(result) if result else 0}")

        if result:
            titles = self._parse_titles(result, num_titles)
            logger.info(f"Parsed {len(titles)} titles")
            return titles

        logger.warning(f"Failed to generate titles for project {project_id}")
        return []

    def convert_to_platform_format(
        self,
        project_id: str,
        content: str,
        platform: str = 'x'
    ) -> Optional[Dict[str, Any]]:
        """
        Convert content to platform-specific format
        Based on the "发布平台" step of AI writing workflow

        Args:
            project_id: Creation project ID
            content: The final content to convert
            platform: Target platform (x, weixin, linkedin, etc.)

        Returns:
            Dictionary with converted content
        """
        if platform == 'weixin':
            # Preprocess: Convert Chinese section markers to markdown headings
            # This handles content like "一、xxx" -> "## 一、xxx"
            import re

            # ===== Step 0: Simple cleanup =====
            # Detect if content uses proper markdown list syntax (markers at line start)
            # vs indented text (markers after whitespace)
            lines = content.split('\n')
            cleaned_lines = []
            prev_was_table_row = False

            for line in lines:
                # Check original line: does it start with "- " or "* " at position 0?
                original_starts_with_marker = line.lstrip().startswith(('- ', '* '))
                # Was there whitespace before the marker?
                had_leading_whitespace = line and line[0] in ' \t'

                # Strip trailing whitespace only
                line = line.rstrip()

                if line:
                    # Check if this is a table row
                    is_table_row = line.startswith('|') or line.endswith('|')

                    # If it had leading whitespace before the marker, it's NOT a markdown list
                    # Keep it as plain text (remove the marker entirely)
                    if had_leading_whitespace and original_starts_with_marker:
                        line = line.lstrip()
                        # Remove the marker: "- " or "* " at the start
                        if line.startswith('- ') or line.startswith('* '):
                            line = line[2:]
                        elif line.startswith('-') or line.startswith('*'):
                            line = line[1:].lstrip()

                    # If previous was a table row and this is also a table row, join without blank line
                    if prev_was_table_row and is_table_row:
                        cleaned_lines[-1] = cleaned_lines[-1] + '\n' + line
                    else:
                        cleaned_lines.append(line)

                    prev_was_table_row = is_table_row
                else:
                    prev_was_table_row = False

            # Join with double newlines for markdown paragraph detection
            content = '\n\n'.join(cleaned_lines)

            # ===== Step 1: Convert numbered sections to h2 (before first line conversion) =====
            # Note: \s* allows for optional whitespace after the delimiter
            content = re.sub(r'^((一|二|三|四|五|六|七|八|九|十|零)[、.]\s*)', r'## \1', content, flags=re.MULTILINE)

            # ===== Step 2: Convert common section titles to h2 =====
            section_titles = '前言|概述|简介|摘要|总结|安装|配置|使用|常见问题|FAQ|下一步|典型使用场景|推荐配置|实战场景演示|总结'
            content = re.sub(rf'^({section_titles})$', r'## \1', content, flags=re.MULTILINE)

            # ===== Step 3: First line should be h1 (if not already a heading) =====
            lines = content.split('\n')
            if lines and lines[0] and not lines[0].startswith('#'):
                lines[0] = '# ' + lines[0]
            content = '\n'.join(lines)

            # ===== Step 4: Add blank lines after numbered/section headings =====
            # After h2/h3 headings followed by content, add blank line
            content = re.sub(r'(## .+？)\n([^#])', r'\1\n\n\2', content)

            # ===== Step 5: Handle code fence markers =====
            content = re.sub(r'^CODE$', '```', content, flags=re.MULTILINE)
            content = re.sub(r'^BASH$', '```bash', content, flags=re.MULTILINE)
            content = re.sub(r'^PYTHON$', '```python', content, flags=re.MULTILINE)
            content = re.sub(r'^SHELL$', '```bash', content, flags=re.MULTILINE)

            # ===== Step 6: Add blank lines after headings to separate from content =====
            # Match headings followed by non-blank content and add blank line
            content = re.sub(r'(#+.+)\n([^#\n])', r'\1\n\n\2', content)

            # 1. Check if content contains Markdown syntax
            has_markdown = bool(re.search(r'^#{1,6}\s+', content, re.MULTILINE)) or '**' in content or '*' in content or '- ' in content or '> ' in content or '```' in content or '|' in content

            if has_markdown:
                # Parse Markdown to HTML
                html = self.parse_markdown(content)
            else:
                # Plain text - convert newlines to paragraphs
                # Split on double newlines but preserve single line breaks within content
                paragraphs = content.split('\n\n')
                html_parts = []
                for p in paragraphs:
                    p = p.strip()
                    if p:
                        # Don't wrap in <p> - let _format_weixin_html handle it
                        # This avoids double-wrapping issues
                        html_parts.append(p)
                html = '<p>' + '</p><p>'.join(html_parts) + '</p>'

            # 2. Add warm beige theme styles
            html = self._format_weixin_html(html)

            return {
                'platform': 'weixin',
                'content': html,
                'format_notes': '✓ 直接复制富文本粘贴到微信编辑器'
            }

        # For other platforms: use LLM conversion
        from services.creation_service import CreationWorkshopService

        creation_service = CreationWorkshopService(self.db_path)
        project = creation_service.get_by_id(project_id)

        if not project:
            return None

        # Build prompt for platform conversion
        prompt = self._build_platform_prompt(project, content, platform)

        # Call LLM
        result = self._call_llm(prompt)

        if result:
            return {
                'platform': platform,
                'content': result,
                'format_notes': self._get_platform_notes(platform)
            }

        return {'error': 'Failed to convert format', 'content': content}

    # ============== Helper Methods ==============

    def _call_llm(self, prompt: str, max_tokens: int = 2000) -> Optional[str]:
        """Call LLM with prompt"""
        client = get_llm_client()
        if not client:
            logger.error("No LLM client available - check API key configuration")
            return None

        try:
            # Use deepseek or openai
            model = os.environ.get('LLM_MODEL', 'deepseek-chat')
            logger.info(f"Calling LLM with model: {model}")

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a professional writing assistant. Help users with their creative writing projects. Respond in Chinese if the user's context is in Chinese."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )

            content = response.choices[0].message.content
            logger.info(f"LLM response received, length: {len(content) if content else 0}")
            return content

        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            return None

    def _build_draft_prompt(
        self,
        project: Any,
        materials: List[Dict[str, Any]],
        target_words: int
    ) -> str:
        """Build prompt for draft generation"""
        materials_summary = "\n\n".join([
            f"## {m['title']}\n- Topics: {', '.join(m['topics'])}\n- Summary: {m['summary'][:300]}"
            for m in materials
        ])

        prompt = f"""基于以下素材，为创作项目生成初稿。

项目标题: {project.title}
项目简介: {project.brief or '无'}
目标字数: {target_words} 字

素材:
{materials_summary}

要求:
1. 先把想法一股脑倒出来，不分结构
2. 保留素材中的关键信息和引用
3. 使用自然、对话式的风格
4. 直接开始写作，不需要标题

初稿内容:"""

        return prompt

    def _build_structure_prompt(
        self,
        project: Any,
        draft_content: str
    ) -> str:
        """Build prompt for structural improvement"""
        prompt = f"""分析以下草稿，提供A/B两种结构优化方案。

项目标题: {project.title}
当前状态: {project.status}

草稿内容:
{draft_content[:3000]}

请提供两种结构优化方案:

## Version A (线性结构)
- 主要特点
- 需要调整的部分
- 具体修改建议

## Version B (问题-解决方案结构)
- 主要特点
- 需要调整的部分
- 具体修改建议

请用JSON格式回复:
{{
  "version_a": {{"title": "方案A标题", "structure": "主要特点", "changes": ["修改1", "修改2"]}},
  "version_b": {{"title": "方案B标题", "structure": "主要特点", "changes": ["修改1", "修改2"]}}
}}"""

        return prompt

    def _build_title_prompt(
        self,
        project: Any,
        content: str,
        num_titles: int
    ) -> str:
        """Build prompt for title generation"""
        project_type = project.project_type or "通用内容"
        content_snippet = content[:3000] if content else ""

        prompt = f"""基于以下内容，生成{num_titles}个标题建议。

项目类型: {project_type}

内容摘要:
{content_snippet}

请生成以下类型的标题:
1. 常规标题 (中性、描述性)
2. 钩子型标题 (引起好奇)
3. 问答型标题 (提问引发思考)
4. 数字型标题 (使用数据和列表)
5. 情感型标题 (引发情感共鸣)

请用JSON数组格式回复，每项包含 type, title, reason:
[{{"type": "常规", "title": "标题内容", "reason": "为什么好"}}, ...]"""

        return prompt

    def _build_platform_prompt(
        self,
        project: Any,
        content: str,
        platform: str
    ) -> str:
        """Build prompt for platform conversion with detailed format guidelines"""
        import re

        # Get first 2000 chars of content for the prompt
        content_snippet = content[:2000] if content else ""

        if platform == 'weixin':
            # WeChat detailed format guide
            platform_guide = """
微信公众号格式要求（必须严格遵循）:
1. 使用HTML标签：p, h2, h3, h4, img, blockquote, ul, ol, li, a, span, strong, em
2. 所有样式必须内联（微信不支持外部样式表），格式如：style="margin:15px 0;line-height:2;font-size:16px;color:#333333"
3. 内容宽度不超过677px（自动居中）
4. 标题使用h2或h3，加粗，颜色#222222
5. 引用使用blockquote，左边框3px solid #e8e8e8，背景#f9f9f9，padding:10px
6. 列表使用ul/ol，缩进
7. 段落样式：font-size:16px;color:#333333;line-height:1.8;margin:15px 0
8. 图片使用img标签，建议添加说明文字
9. 使用中文标点符号
10. 输出完整的HTML代码，不要包含```html代码块标记

示例输出格式：
<h2 style="font-size:20px;font-weight:bold;color:#222222;margin:20px 0 10px;">标题</h2>
<p style="font-size:16px;color:#333333;line-height:1.8;margin:15px 0;">正文内容...</p>
<blockquote style="border-left:3px solid #e8e8e8;background:#f9f9f9;padding:10px;margin:15px 0;">引用内容</blockquote>"""
            platform_desc = platform_guide
        elif platform == 'x':
            # X/Twitter detailed format guide
            platform_guide = """
X/Twitter格式要求（必须严格遵循）:
1. 最多280字符（中文140字符），精确计算
2. 开头hook必须吸引眼球，引发好奇
3. 使用2-4个相关hashtag（#标签）
4. 简洁有力的短句，避免冗长
5. 如有相关账号可@提及
6. 结尾可添加行动号召(CTA)
7. 提取最核心的观点和信息
8. 输出纯文本，不需要任何格式标签

输出格式：纯文本内容，长度严格控制在280字符以内"""
            platform_desc = platform_guide
        elif platform == 'linkedin':
            platform_guide = """
LinkedIn格式要求：
1. 专业风格，适合职场阅读
2. 首行要有吸引力（hook）
3. 添加2-5个专业话题标签（#话题）
4. 段落分明，每段不要太长
5. 可添加emoji增加可读性
6. 结尾添加行动号召或讨论引导
7. 输出纯文本格式"""
            platform_desc = platform_guide
        elif platform == 'xiaohongshu':
            platform_guide = """
小红书格式要求：
1. Emoji丰富，活泼有趣
2. 段落要短，每行不要太长
3. 添加话题标签（#标签）
4. 开头吸引人，有视觉感
5. 结尾要有互动引导（收藏、点赞等）
6. 输出纯文本格式"""
            platform_desc = platform_guide
        else:
            platform_desc = "通用格式"

        # Build the final prompt
        prompt = f"""将以下内容转换为适合{platform}平台发布的内容。

项目标题: {project.title or '无标题'}
项目类型: {project.project_type or '通用'}

{platform_desc}

原始内容:
{content_snippet}

请根据上述平台要求进行转换，输出转换后的内容："""

        return prompt

    def _parse_structural_suggestions(self, result: str) -> Dict[str, Any]:
        """Parse structural suggestions from LLM response"""
        import json
        import re

        # Try to extract JSON
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass

        # Fallback: return raw text as description
        return {
            'version_a': {'title': 'Version A', 'structure': result[:500], 'changes': []},
            'version_b': {'title': 'Version B', 'structure': 'Alternative structure', 'changes': []}
        }

    def _parse_titles(self, result: str, num_titles: int) -> List[Dict[str, str]]:
        """Parse titles from LLM response"""
        import json
        import re

        if not result:
            logger.warning("Empty result passed to _parse_titles")
            return []

        # Try to extract JSON array
        json_match = re.search(r'\[[\s\S]*\]', result)
        if json_match:
            try:
                titles = json.loads(json_match.group())
                logger.info(f"Successfully parsed {len(titles)} titles from JSON")
                return titles[:num_titles]
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse failed: {e}")

        # Try to parse as any JSON structure
        try:
            # Try to find JSON objects in the text
            obj_matches = re.findall(r'\{[^{}]*\}', result)
            titles = []
            for match in obj_matches:
                try:
                    obj = json.loads(match)
                    if 'title' in obj:
                        titles.append({
                            'type': obj.get('type', '常规'),
                            'title': obj.get('title', ''),
                            'reason': obj.get('reason', obj.get('reason', 'From AI suggestion'))
                        })
                except:
                    pass
            if titles:
                logger.info(f"Parsed {len(titles)} titles from objects")
                return titles[:num_titles]
        except Exception as e:
            logger.warning(f"Object extraction failed: {e}")

        # Fallback: parse line by line
        logger.info("Using line-by-line fallback parsing")
        titles = []
        for line in result.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('```'):
                # Try to extract title from various formats
                title = line.lstrip('0123456789.)-: ')
                if len(title) > 3:  # Minimum title length
                    titles.append({
                        'type': '常规',
                        'title': title,
                        'reason': 'From AI suggestion'
                    })

        return titles[:num_titles]

    def _get_platform_notes(self, platform: str) -> str:
        """Get formatting notes for platform"""
        notes = {
            'x': '✓ 最多280字符\n✓ 使用hashtag增加曝光\n✓ 简洁有力的开头hook\n✓ 可添加1-4张图片',
            'weixin': '✓ 标题使用h2/h3加粗\n✓ 段落添加行距和间距\n✓ 引用使用blockquote样式\n✓ 复制HTML可直接粘贴到微信编辑器',
            'linkedin': '✓ 添加专业话题标签\n✓ 首行要有吸引力\n✓ 建议添加图片',
            'xiaohongshu': '✓ Emoji要丰富\n✓ 段落要短\n✓ 结尾要有互动引导'
        }
        return notes.get(platform, '请根据平台特点调整')

    def _format_weixin_html(self, html_content: str) -> str:
        """
        Enhance WeChat HTML with beautiful warm beige theme styles
        Premium article styling with enhanced visual hierarchy

        Args:
            html_content: Raw HTML from Markdown conversion

        Returns:
            HTML with beautiful warm beige theme
        """
        import re

        # Clean up HTML content before processing
        # NOTE: Don't apply markdown transformations to HTML content - it breaks the structure!
        lines = html_content.split('\n')
        cleaned_lines = []
        for line in lines:
            # Strip leading whitespace
            line = line.lstrip()
            # Strip trailing whitespace
            line = line.rstrip()
            # Skip lines that are only whitespace
            if line.strip():
                cleaned_lines.append(line)
        # Join back and remove multiple consecutive blank lines
        html_content = '\n'.join(cleaned_lines)
        html_content = re.sub(r'\n{3,}', '\n\n', html_content)

        # NOTE: Post-processing of HTML content to convert titles to headings
        # has been disabled as it incorrectly matches content like "A:" and "Q:"

        # Color palette - warm beige theme with premium accents
        colors = {
            'bg': '#FAF8F5',              # Warm beige background
            'bg_light': '#F5F0E8',       # Lighter beige
            'text': '#2D2D2D',           # Near black for text
            'text_light': '#6B6B6B',     # Lighter text
            'accent': '#8B7355',         # Deep warm brown accent
            'accent_light': '#A69070',   # Light warm brown
            'border': '#E8E4DE',         # Subtle border
            'code_bg': '#F5F0E8',        # Light beige code background
            'code_text': '#2D2D2D',      # Code text color (dark)
            'code_keyword': '#D73A49',   # Code keyword (red)
            'code_string': '#22863A',    # Code string (green)
            'code_comment': '#6A737D',   # Code comment (gray)
            'code_number': '#005CC5',    # Code number (blue)
            'quote_border': '#8B7355',   # Quote border accent
            'link': '#3B5998',           # Classic blue link
            'h1_accent': '#D4C4B0',     # H1 accent color
        }

        # If no HTML tags, wrap in paragraphs
        if '<' not in html_content:
            paragraphs = html_content.split('\n\n')
            styled_parts = []
            for p in paragraphs:
                p = p.strip()
                if p:
                    styled_parts.append(
                        f'<p style="margin:12px 0;line-height:1.8;font-size:15px;color:{colors["text"]};">{p}</p>'
                    )
            return '\n'.join(styled_parts)

        result = html_content

        # ========== 1. Headers - Enhanced visual hierarchy ==========
        result = html_content

        # FIX: First clean up any malformed nested p tags that might exist
        # This fixes issues with double-wrapped paragraphs
        result = re.sub(r'<p[^>]*>\s*<p', '<p', result)
        result = re.sub(r'</p>\s*</p>', '</p>', result)
        for i in range(6, 0, -1):
            if i == 1:
                # h1 - Main title with gradient underline and left accent
                result = re.sub(
                    rf'<h{i}([^>]*)>(.*?)</h{i}>',
                    rf'''<h{i}\1 style="font-size:26px;font-weight:700;color:{colors["text"]};margin:28px 0 20px;line-height:1.3;position:relative;padding-left:16px;border-left:4px solid {colors["accent"]};">
<span style="display:block;margin-top:12px;border-bottom:2px solid transparent;background:linear-gradient(90deg,{colors["accent"]} 0%,{colors["h1_accent"]} 100%);height:2px;"></span>\2</h{i}>''',
                    result,
                    flags=re.IGNORECASE | re.DOTALL
                )
            elif i == 2:
                # h2 - Section title with left bar and background
                result = re.sub(
                    rf'<h{i}([^>]*)>(.*?)</h{i}>',
                    rf'''<h{i}\1 style="font-size:20px;font-weight:600;color:{colors["text"]};margin:24px 0 14px;line-height:1.4;position:relative;padding:10px 0 10px 14px;border-left:3px solid {colors["accent_light"]};background:linear-gradient(90deg,{colors["bg_light"]} 0%,transparent 100%);">\2</h{i}>''',
                    result,
                    flags=re.IGNORECASE | re.DOTALL
                )
            elif i == 3:
                # h3 - Subsection with left dot
                result = re.sub(
                    rf'<h{i}([^>]*)>(.*?)</h{i}>',
                    rf'''<h{i}\1 style="font-size:17px;font-weight:600;color:{colors["text"]};margin:20px 0 10px;line-height:1.4;padding-left:12px;position:relative;">
<span style="position:absolute;left:0;top:8px;width:6px;height:6px;background:{colors["accent"]};border-radius:50%;"></span>\2</h{i}>''',
                    result,
                    flags=re.IGNORECASE | re.DOTALL
                )
            else:
                # h4-h6
                result = re.sub(
                    rf'<h{i}([^>]*)>(.*?)</h{i}>',
                    rf'<h{i}\1 style="font-size:16px;font-weight:600;color:{colors["text"]};margin:16px 0 8px;">\2</h{i}>',
                    result,
                    flags=re.IGNORECASE | re.DOTALL
                )

        # 2. Paragraphs - clean and readable (skip if already has style)
        # Also clean up duplicate/malformed p tags first
        import sys

        # Remove p tags inside li (they create invalid nested blocks)
        result = re.sub(r'<li([^>]*)>(.*?)<p(.*?)>(.*?)</p>(.*?)</li>', r'<li\1>\2\4\5</li>', result, flags=re.IGNORECASE | re.DOTALL)

        # Clean up whitespace in list items
        result = re.sub(r'<li([^>]*)>\s+', r'<li\1>', result)
        result = re.sub(r'\s+</li>', r'</li>', result)

        result = re.sub(
            r'<p([^>]*)>(.*?)</p>',
            lambda m: f'<p{m.group(1)} style="margin:12px 0;line-height:1.8;font-size:15px;color:{colors["text"]};">{m.group(2)}</p>' if 'style=' not in m.group(1) else m.group(0),
            result,
            flags=re.IGNORECASE | re.DOTALL
        )

        # 3. Blockquotes - premium quote style with gradient and icon
        result = re.sub(
            r'<blockquote([^>]*)>',
            rf'''<blockquote\1 style="border-left:4px solid {colors["quote_border"]};background:linear-gradient(135deg,{colors["bg_light"]} 0%,#EDE8E0 100%);padding:16px 20px;margin:16px 0;color:{colors["text_light"]};line-height:1.8;font-size:14px;border-radius:0 8px 8px 0;position:relative;">
            <span style="position:absolute;top:8px;left:12px;font-size:24px;color:{colors["accent"]};opacity:0.3;font-family:Georgia,serif;">"</span>
            <span style="display:block;padding-left:16px;">''',
            result,
            flags=re.IGNORECASE
        )
        # Close the span tag before closing blockquote
        result = re.sub(
            r'</blockquote>',
            '</span></blockquote>',
            result,
            flags=re.IGNORECASE
        )

        # 4. Lists - enhanced with custom bullets
        # Only style actual list elements, don't add bullets to paragraphs
        result = re.sub(
            r'<ul([^>]*)>',
            rf'<ul\1 style="margin:12px 0;padding-left:20px;list-style:none;color:{colors["text"]};">',
            result,
            flags=re.IGNORECASE
        )
        result = re.sub(
            r'<ol([^>]*)>',
            rf'<ol\1 style="margin:12px 0;padding-left:20px;color:{colors["text"]};">',
            result,
            flags=re.IGNORECASE
        )

        # Style existing list items - use smaller bullet
        # Only apply to <li> elements that don't already have custom styling
        result = re.sub(
            r'<li([^>]*)>(.*?)</li>',
            rf'<li\1 style="margin:6px 0;line-height:1.8;font-size:15px;color:{colors["text"]};list-style:none;">\2</li>',
            result,
            flags=re.IGNORECASE | re.DOTALL
        )

        # 5. Strong and emphasis
        result = re.sub(
            r'<strong([^>]*)>',
            rf'<strong\1 style="font-weight:600;color:{colors["accent"]};">',
            result,
            flags=re.IGNORECASE
        )
        result = re.sub(
            r'<em([^>]*)>',
            rf'<em\1 style="font-style:italic;color:{colors["text_light"]};">',
            result,
            flags=re.IGNORECASE
        )

        # 6. Links
        result = re.sub(
            r'<a([^>]*)>',
            rf'<a\1 style="color:{colors["link"]};text-decoration:underline;text-decoration-color:{colors["link"]}40;">',
            result,
            flags=re.IGNORECASE
        )

        # 7. Images - clean and responsive with elegant styling
        result = re.sub(
            r'<img([^>]*)>',
            r'<img\1 style="max-width:100%;height:auto;margin:20px 0;border-radius:8px;display:block;box-shadow:0 2px 8px rgba(0,0,0,0.1);">',
            result,
            flags=re.IGNORECASE
        )

        # 8. Code - light theme (elegant and readable)
        # Inline code - warm background
        result = re.sub(
            r'<code([^>]*?)>(.*?)</code>',
            lambda m: f'<code{m.group(1)} style="background:{colors["bg_light"]};padding:3px 8px;border-radius:4px;font-family:SF Mono,Monaco,Menlo,monospace;font-size:13px;color:{colors["accent"]};border:1px solid {colors["border"]};">{m.group(2)}</code>' if '1E1E1E' not in m.group(1) and '#1E1E1E' not in m.group(1) else m.group(0),
            result,
            flags=re.IGNORECASE | re.DOTALL
        )
        # Code blocks with light theme - clean and elegant
        def replace_pre(m):
            attrs = m.group(1)
            code_content = m.group(2)

            # Extract language from inner <code class="language-xxx"> if present
            lang = 'code'
            code_lang_match = re.search(r'<code[^>]*class="[^"]*language-(\w+)', code_content, re.IGNORECASE)
            if code_lang_match:
                lang = code_lang_match.group(1)

            # Remove existing class and style attributes from pre
            attrs = re.sub(r'\s*class="[^"]*"', '', attrs)
            attrs = re.sub(r"\s*class='[^']*'", '', attrs)
            attrs = re.sub(r'\s*style="[^"]*"', '', attrs)
            attrs = re.sub(r"\s*style='[^']*'", '', attrs)

            # Remove language class from inner code (we'll re-add styling anyway)
            code_content = re.sub(r'class="[^"]*language-(\w+)[^"]*"', '', code_content)

            # Strip ALL whitespace from code content (including newlines within)
            code_content = code_content.strip()

            # Get language display name (map common names)
            lang_display = {
                'bash': 'bash',
                'python': 'python',
                'js': 'javascript',
                'javascript': 'javascript',
                'html': 'html',
                'css': 'css',
                'json': 'json',
                'sql': 'sql',
                'yaml': 'yaml',
                'go': 'go',
                'rust': 'rust',
                'java': 'java',
            }.get(lang.lower(), lang)

            return f'''<pre{attrs} style="background:{colors["code_bg"]};padding:0;border-radius:10px;margin:16px 0;overflow-x:auto;font-size:13px;line-height:1.7;border:1px solid {colors["border"]};position:relative;">
            <div style="background:{colors["accent_light"]};padding:8px 16px;border-radius:10px 10px 0 0;display:flex;align-items:center;gap:6px;">
            <span style="width:10px;height:10px;border-radius:50%;background:#FF5F56;"></span>
            <span style="width:10px;height:10px;border-radius:50%;background:#FFBD2E;"></span>
            <span style="width:10px;height:10px;border-radius:50%;background:#27CA40;"></span>
            <span style="margin-left:auto;color:#fff;font-size:11px;font-family:monospace;text-transform:uppercase;">{lang_display}</span>
            </div>
            <div style="padding:16px;color:{colors["code_text"]};overflow-x:auto;font-family:SF Mono,Monaco,Menlo,monospace;">{code_content}</div></pre>'''

        result = re.sub(
            r'<pre([^>]*)>(.*?)</pre>',
            replace_pre,
            result,
            flags=re.IGNORECASE | re.DOTALL
        )

        # 9. Horizontal rules (hr) - enhanced
        result = re.sub(
            r'<hr([^>]*)>',
            rf'''<hr\1 style="border:none;height:1px;background:linear-gradient(90deg,transparent 0%,{colors["border"]} 20%,{colors["border"]} 80%,transparent 100%);margin:28px 0;">''',
            result,
            flags=re.IGNORECASE
        )

        # 10. Tables - premium styling
        result = re.sub(
            r'<table([^>]*)>',
            rf'''<table\1 style="width:100%;border-collapse:separate;border-spacing:0;margin:16px 0;font-size:14px;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">''',
            result,
            flags=re.IGNORECASE
        )
        # Remove thead style and add it to th instead
        result = re.sub(
            r'<thead([^>]*)>.*?<tr>',
            r'<thead><tr>',
            result,
            flags=re.IGNORECASE | re.DOTALL
        )
        result = re.sub(
            r'<th([^>]*)>',
            rf'<th\1 style="background:{colors["accent"]};color:#fff;padding:12px 14px;border:none;text-align:left;font-weight:600;font-size:14px;">',
            result,
            flags=re.IGNORECASE
        )
        result = re.sub(
            r'<td([^>]*)>',
            rf'<td\1 style="padding:12px 14px;border:none;border-bottom:1px solid {colors["border"]};">',
            result,
            flags=re.IGNORECASE
        )
        # Add zebra striping - alternate row backgrounds
        # Find tbody and alternate row backgrounds
        def zebra_stripe(match):
            content = match.group(2)
            rows = content.split('</tr>')
            new_rows = []
            for i, row in enumerate(rows):
                if row.strip():
                    bg = '#FAFAFA' if i % 2 == 0 else '#FFFFFF'
                    row = re.sub(r'<tr([^>]*)>', rf'<tr\1 style="background:{bg};">', row)
                    new_rows.append(row)
            return match.group(1) + '</tr>'.join(new_rows) + match.group(3)

        result = re.sub(
            r'(<tbody>)(.*?)(</tbody>)',
            zebra_stripe,
            result,
            flags=re.IGNORECASE | re.DOTALL
        )

        # 11. Clean up empty and duplicate style attributes
        result = re.sub(r'style=""', '', result)
        result = re.sub(r'style=\'\'', '', result)
        # Remove duplicate style="..." patterns
        result = re.sub(r'\s*style="[^"]*"', lambda m: m.group(0).split('"')[-2] and m.group(0), result)
        result = re.sub(r'\sstyle="[^"]*"\s*style="([^"]*)"', r' style="\1"', result)

        # 12. Final cleanup - remove extra whitespace
        result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)  # Reduce multiple blank lines
        result = re.sub(r'>\s+<', '><', result)  # Remove whitespace between tags
        result = result.strip()  # Remove leading/trailing whitespace

        # 13. Wrap in container with warm beige background
        result = f'''<div style="width:100%;max-width:677px;margin:0 auto;padding:20px;background:{colors["bg"]};font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei','Helvetica Neue',sans-serif;font-size:15px;line-height:1.8;color:{colors["text"]};">
{result}
</div>'''

        return result

    # ============== Image Generation & Analysis Methods ==============

    def analyze_content_for_images(
        self,
        project_id: str,
        content: str = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Analyze content and identify sections that need images
        基于"配图"步骤，智能识别文章中需要配图的位置

        Args:
            project_id: Creation project ID
            content: The article content (if not provided, will use draft from project)

        Returns:
            List of image placement suggestions with reasons
        """
        from services.creation_service import CreationWorkshopService

        creation_service = CreationWorkshopService(self.db_path)
        project = creation_service.get_by_id(project_id)

        if not project:
            return None

        # Use provided content or get from project
        if not content:
            content = project.draft or ""

        if not content:
            return []

        # Split content into sections/paragraphs
        sections = self._split_content_into_sections(content)

        # Analyze each section for image needs
        image_suggestions = []

        for idx, section in enumerate(sections):
            analysis = self._analyze_section_for_image(section, idx, len(sections))
            if analysis['needs_image']:
                image_suggestions.append(analysis)

        return image_suggestions

    def _split_content_into_sections(self, content: str) -> List[Dict[str, Any]]:
        """Split content into analyzable sections"""
        import re

        sections = []
        # Split by headers or double newlines
        parts = re.split(r'\n(?=#|\n\n)', content)

        current_section = {
            'title': '引言',
            'content': '',
            'type': 'intro'
        }

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Check if it's a header
            if part.startswith('#'):
                # Save previous section
                if current_section['content']:
                    sections.append(current_section)

                # Extract header
                header_match = re.match(r'^(#{1,6})\s+(.+?)(?:\n|$)', part)
                if header_match:
                    header_text = header_match.group(2).strip()
                    content_after_header = part[header_match.end():].strip()

                    # Determine section type based on header
                    section_type = self._classify_section_type(header_text)

                    current_section = {
                        'title': header_text,
                        'content': content_after_header,
                        'type': section_type
                    }
                else:
                    current_section['content'] += '\n' + part
            else:
                current_section['content'] += '\n' + part

        # Add last section
        if current_section['content']:
            sections.append(current_section)

        # If no sections were created, treat whole content as one
        if not sections:
            sections = [{
                'title': '全文',
                'content': content,
                'type': 'body'
            }]

        return sections

    def _classify_section_type(self, title: str) -> str:
        """Classify section type based on title keywords"""
        title_lower = title.lower()

        if any(kw in title_lower for kw in ['引言', '前言', '介绍', '开场']):
            return 'intro'
        elif any(kw in title_lower for kw in ['总结', '结论', '结语', '收尾']):
            return 'conclusion'
        elif any(kw in title_lower for kw in ['问题', '背景', '现状']):
            return 'background'
        elif any(kw in title_lower for kw in ['方法', '方案', '步骤', '如何']):
            return 'howto'
        elif any(kw in title_lower for kw in ['例子', '案例', '示例']):
            return 'example'
        elif any(kw in title_lower for kw in ['对比', '比较', '优缺点']):
            return 'comparison'
        elif any(kw in title_lower for kw in ['数据', '统计', '研究']):
            return 'data'
        else:
            return 'body'

    def _analyze_section_for_image(
        self,
        section: Dict[str, Any],
        index: int,
        total_sections: int
    ) -> Dict[str, Any]:
        """Analyze if a section needs an image and generate prompt"""
        title = section.get('title', '')
        content = section.get('content', '')
        section_type = section.get('type', 'body')

        # Determine if image is needed based on section type and content
        needs_image = False
        reason = ""
        image_type = "general"
        suggested_prompt = ""

        # High priority for intro, conclusion, examples, comparisons
        high_priority_types = ['intro', 'conclusion', 'example', 'comparison', 'data']

        if section_type in high_priority_types:
            needs_image = True
            reason = f"章节类型「{section_type}」适合添加配图增强表现力"
        elif len(content) > 300:
            # Longer sections benefit from images
            needs_image = True
            reason = "较长内容，配图可以缓解阅读疲劳"
        elif any(kw in content.lower() for kw in ['例如', '比如', '如下', '如图']):
            needs_image = True
            reason = "内容提到具体示例或图表"

        if needs_image:
            # Generate image prompt based on section content
            image_prompt = self._generate_image_prompt(title, content, section_type)
            suggested_prompt = image_prompt['prompt']
            image_type = image_prompt['type']

        return {
            'section_index': index,
            'section_title': title,
            'section_type': section_type,
            'needs_image': needs_image,
            'reason': reason if needs_image else "该段落文字较少或为过渡内容，暂不需要配图",
            'image_type': image_type,
            'suggested_prompt': suggested_prompt,
            'position': 'above' if section_type == 'intro' else 'inline'
        }

    def _generate_image_prompt(
        self,
        title: str,
        content: str,
        section_type: str
    ) -> Dict[str, Any]:
        """Generate image generation prompt based on section content"""
        # Use LLM to generate a good image prompt
        prompt = f"""为以下文章章节生成一个适合AI绘图的中文提示词:

标题: {title}
内容摘要: {content[:200]}
类型: {section_type}

要求:
1. 简洁明确，15-30个词
2. 适合配图表现
3. 包含视觉风格描述
4. 输出JSON格式: {{"prompt": "提示词", "type": "类型"}}"""

        result = self._call_llm(prompt, max_tokens=200)

        if result:
            import json
            import re
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return {
                        'prompt': data.get('prompt', f'{title}相关配图'),
                        'type': data.get('type', 'general')
                    }
                except:
                    pass

        # Fallback: generate basic prompt
        return {
            'prompt': f'{title}，{section_type}类型配图，简洁现代风格',
            'type': 'general'
        }

    def generate_images(
        self,
        prompt: str,
        num_images: int = 3,
        size: str = "1024x1024",
        style: str = "modern",
        project_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """
        Generate images using OpenRouter (Google Gemini 2.5 Flash Image)
        and save to local file system

        Args:
            prompt: Image generation prompt (in Chinese)
            num_images: Number of images to generate
            size: Image size (1024x1024, 1792x1024, 1024x1792)
            style: Image style preference
            project_id: Project ID for organizing images in folder

        Returns:
            List of generated image data
        """
        import requests
        import uuid

        # Use OpenRouter API with chat/completions endpoint
        api_key = os.environ.get('OPENROUTER_API_KEY')
        api_url = 'https://openrouter.ai/api/v1/chat/completions'

        if not api_key:
            # Fallback to placeholder
            logger.warning("OPENROUTER_API_KEY not set, using placeholder images")
            return self._get_placeholder_images(prompt, num_images)

        images = []

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://linker-mind.local',
                'X-Title': 'Linker Mind'
            }

            # Use Google Gemini 2.5 Flash Image model via OpenRouter
            model = 'google/gemini-2.5-flash-image'

            # Build enhanced prompt for better results
            enhanced_prompt = f"{prompt}. High quality, detailed, beautiful composition."

            # Generate images one by one
            for i in range(num_images):
                payload = {
                    'model': model,
                    'messages': [
                        {'role': 'user', 'content': enhanced_prompt}
                    ],
                    'max_tokens': 4096
                }

                response = requests.post(
                    api_url,
                    headers=headers,
                    json=payload,
                    timeout=180
                )

                if response.status_code == 200:
                    data = response.json()
                    # Parse response to get base64 image
                    base64_data = self._parse_image_response(data)
                    if base64_data and base64_data.startswith('data:'):
                        # Save to local file
                        saved_url = self._save_image_to_file(base64_data, project_id)
                        if saved_url:
                            images.append({
                                'id': str(uuid.uuid4()),
                                'url': saved_url,
                                'prompt': prompt,
                                'size': size,
                                'style': style,
                                'index': i
                            })
                    elif base64_data:
                        # External URL
                        images.append({
                            'id': str(uuid.uuid4()),
                            'url': base64_data,
                            'prompt': prompt,
                            'size': size,
                            'style': style,
                            'index': i
                        })
                else:
                    logger.warning(f"Image generation failed: {response.status_code} - {response.text[:200]}")

        except Exception as e:
            logger.error(f"Error generating images: {e}")

        # If API failed, return placeholder
        if not images:
            return self._get_placeholder_images(prompt, num_images)

        return images

    def _parse_image_response(self, data: dict) -> Optional[str]:
        """Parse image from OpenRouter response (base64 or URL)"""
        try:
            if 'choices' in data and len(data['choices']) > 0:
                msg = data['choices'][0].get('message', {})
                images = msg.get('images', [])

                if images and len(images) > 0:
                    img_data = images[0]
                    img_url = img_data.get('image_url', {}).get('url', '')

                    if img_url.startswith('data:'):
                        # Already a data URL, return as is
                        return img_url
                    elif img_url.startswith('http'):
                        # Regular URL
                        return img_url

            return None
        except Exception as e:
            logger.error(f"Error parsing image response: {e}")
            return None

    def _save_image_to_file(self, base64_data: str, project_id: str) -> Optional[str]:
        """Save base64 image to local file and return URL"""
        import re
        import os
        import uuid

        try:
            # Extract base64 content and mime type
            match = re.match(r'data:([^;]+);base64,(.+)', base64_data)
            if not match:
                logger.warning("Invalid base64 image data")
                return None

            mime_type = match.group(1)
            b64_content = match.group(2)

            # Determine file extension
            ext_map = {
                'image/png': 'png',
                'image/jpeg': 'jpg',
                'image/jpg': 'jpg',
                'image/gif': 'gif',
                'image/webp': 'webp'
            }
            ext = ext_map.get(mime_type, 'png')

            # Create directory path
            upload_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'static', 'uploads', 'images', project_id
            )
            os.makedirs(upload_dir, exist_ok=True)

            # Generate filename
            filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(upload_dir, filename)

            # Decode and save
            import base64
            image_data = base64.b64decode(b64_content)
            with open(filepath, 'wb') as f:
                f.write(image_data)

            # Return relative URL
            return f"/uploads/images/{project_id}/{filename}"

        except Exception as e:
            logger.error(f"Error saving image to file: {e}")
            return None

    def _get_placeholder_images(
        self,
        prompt: str,
        num_images: int
    ) -> List[Dict[str, Any]]:
        """Get placeholder images when API is not available"""
        images = []
        # Use a placeholder service
        for i in range(num_images):
            images.append({
                'id': f'placeholder_{i}',
                'url': f'https://placehold.co/1024x1024/4A90E2/FFFFFF?text=AI+Generated+Image+{i+1}',
                'prompt': prompt,
                'size': '1024x1024',
                'style': 'placeholder',
                'index': i,
                'is_placeholder': True
            })
        return images

    def generate_cover_image(
        self,
        project_id: str,
        title: str = None,
        description: str = None,
        num_images: int = 3,
        style: str = "modern"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Generate cover images for the article

        Args:
            project_id: Creation project ID
            title: Article title (if not provided, will use from project)
            description: Article description/brief
            num_images: Number of cover options to generate
            style: Visual style preference

        Returns:
            List of generated cover images
        """
        from services.creation_service import CreationWorkshopService

        creation_service = CreationWorkshopService(self.db_path)
        project = creation_service.get_by_id(project_id)

        if not project:
            return None

        # Use provided title or get from project
        if not title:
            title = project.title or "文章封面"

        if not description:
            description = project.brief or ""

        # Build prompt for cover image
        cover_prompt = f"""为文章「{title}」生成封面图

文章简介: {description[:100]}
风格: {style}简约现代风格，适合社交媒体分享"""

        # Generate images
        images = self.generate_images(
            prompt=cover_prompt,
            num_images=num_images,
            size="1792x1024",  # 16:9 ratio for covers
            style=style,
            project_id=project_id
        )

        # Mark as cover images
        for img in images:
            img['type'] = 'cover'

        return images

    def generate_section_images(
        self,
        project_id: str,
        section_index: int,
        section_title: str,
        section_content: str,
        num_images: int = 2
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Generate images for a specific section

        Args:
            project_id: Creation project ID
            section_index: Section index in the article
            section_title: Section title
            section_content: Section content
            num_images: Number of images to generate

        Returns:
            List of generated images for the section
        """
        # Generate prompt based on section content
        image_prompt = self._generate_image_prompt(
            section_title,
            section_content,
            'body'
        )

        # Generate images
        images = self.generate_images(
            prompt=image_prompt['prompt'],
            num_images=num_images,
            size="1024x1024",
            project_id=project_id
        )

        # Add section info
        for img in images:
            img['type'] = 'section'
            img['section_index'] = section_index
            img['section_title'] = section_title

        return images

    def suggest_from_library(
        self,
        project_id: str,
        keywords: List[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Suggest images from the content library

        Args:
            project_id: Creation project ID
            keywords: Keywords to search for
            limit: Maximum number of suggestions

        Returns:
            List of suggested images from library
        """
        from services.creation_service import CreationWorkshopService
        from repositories.content_repository import ContentRepository

        creation_service = CreationWorkshopService(self.db_path)
        content_repo = ContentRepository(self.db_path)

        project = creation_service.get_by_id(project_id)
        if not project:
            return []

        # Get keywords from project if not provided
        if not keywords:
            # Extract from source materials
            keywords = self.suggest_keywords(project_id)

        # Search for images in content library
        suggestions = []

        # Get all source materials
        if project.source_materials:
            placeholders = ','.join(['%s'] * len(project.source_materials))
            query = f"""
                SELECT c.id, c.title, c.cover_image, c.metadata
                FROM contents c
                WHERE c.id IN ({placeholders})
                AND (c.cover_image IS NOT NULL OR c.metadata::text LIKE '%image%')
            """

            rows = self.db.fetchall(query, tuple(project.source_materials))

            for row in rows:
                cover = row.get('cover_image')
                metadata = row.get('metadata', {})

                if cover:
                    suggestions.append({
                        'id': row.get('id'),
                        'type': 'cover',
                        'url': cover,
                        'title': row.get('title'),
                        'source': 'content_cover'
                    })
                elif metadata:
                    # Check for images in metadata
                    images = metadata.get('images', [])
                    for img in images[:2]:
                        suggestions.append({
                            'id': f"{row.get('id')}_{img.get('id', '')}",
                            'type': 'content_image',
                            'url': img.get('url', ''),
                            'title': row.get('title'),
                            'source': 'content_metadata'
                        })

        # Also search by keywords in all content
        if keywords and len(suggestions) < limit:
            search_terms = ' OR '.join([f"%{kw}%" for kw in keywords[:5]])
            query = f"""
                SELECT id, title, cover_image, metadata
                FROM contents
                WHERE (title ILIKE ANY(ARRAY[{search_terms}])
                       OR summary ILIKE ANY(ARRAY[{search_terms}]))
                AND cover_image IS NOT NULL
                LIMIT {limit - len(suggestions)}
            """

            rows = self.db.fetchall(query)

            existing_ids = {s['id'] for s in suggestions}
            for row in rows:
                if row.get('id') not in existing_ids:
                    suggestions.append({
                        'id': row.get('id'),
                        'type': 'cover',
                        'url': row.get('cover_image'),
                        'title': row.get('title'),
                        'source': 'keyword_search'
                    })

        return suggestions[:limit]

    def generate_social_image(
        self,
        content: str,
        platform: str,
        num_images: int = 3,
        project_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """
        Generate images optimized for social media platforms

        Args:
            content: Content to generate image for
            platform: Target platform (x, weixin, xiaohongshu, linkedin)
            num_images: Number of images to generate
            project_id: Project ID for organizing images

        Returns:
            List of generated social media images
        """
        # Determine size based on platform
        platform_sizes = {
            'x': '1600x900',      # Twitter card
            'weixin': '1200x630', # WeChat article
            'xiaohongshu': '1242x1660', # Xiaohongshu portrait
            'linkedin': '1200x627' # LinkedIn share
        }

        size = platform_sizes.get(platform, '1200x630')

        # Extract key content for prompt
        title_match = content.split('\n')[0][:50] if content else "社交媒体配图"

        prompt = f"""生成社交媒体配图

平台: {platform}
内容主题: {title_match}
风格: 视觉吸引、专业简洁"""

        return self.generate_images(
            prompt=prompt,
            num_images=num_images,
            size=size,
            style='social',
            project_id=project_id
        )

    def save_project_images(
        self,
        project_id: str,
        images: List[Dict[str, Any]],
        image_type: str = 'section',
        section_index: int = None
    ) -> bool:
        """
        Save generated images to project

        Args:
            project_id: Creation project ID
            images: List of image data to save
            image_type: Type of images (cover, section, social)
            section_index: Section index for section images

        Returns:
            Success status
        """
        from services.creation_service import CreationWorkshopService

        creation_service = CreationWorkshopService(self.db_path)
        project = creation_service.get_by_id(project_id)

        if not project:
            return False

        # Get existing images
        existing_images = project.images or []

        # Add new images
        for img in images:
            img['saved_at'] = datetime.now().isoformat()
            img['project_id'] = project_id

            if image_type == 'cover':
                img['type'] = 'cover'
            elif image_type == 'section' and section_index is not None:
                img['section_index'] = section_index
                img['type'] = 'section'

            existing_images.append(img)

        # Update project
        creation_service.update(
            project_id,
            images=existing_images
        )

        return True

    # ============== Markdown & Inline Image Generation Methods ==============

    def parse_markdown(self, content: str) -> str:
        """
        Parse Markdown content and convert to HTML

        Args:
            content: Markdown content

        Returns:
            HTML string
        """
        if not content:
            return ""

        if not MARKDOWN_AVAILABLE:
            # Fallback: simple regex-based parsing
            return self._parse_markdown_fallback(content)

        try:
            md = markdown.Markdown(extensions=['extra', 'codehilite', 'tables', 'fenced_code'])
            html = md.convert(content)
            return html
        except Exception as e:
            logger.error(f"Error parsing markdown: {e}")
            return self._parse_markdown_fallback(content)

    def _parse_markdown_fallback(self, content: str) -> str:
        """Simple fallback markdown parser without the markdown library"""
        html = content

        # Headers
        for i in range(6, 0, -1):
            header_prefix = '#' * i + ' '
            html = html.replace(f'\n{header_prefix}', f'\n<h{i}>', 1)
            html = html.replace(f'\n{header_prefix}', f'\n<h{i}>')

        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'__(.+?)__', r'<strong>\1</strong>', html)

        # Italic
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'_(.+?)_', r'<em>\1</em>', html)

        # Code blocks
        html = re.sub(r'```(\w+)?\n([\s\S]*?)```', r'<pre><code class="language-\1">\2</code></pre>', html)
        html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)

        # Links
        html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', html)

        # Images - preserve for later processing
        # Note: Images with generate: syntax will be processed separately

        # Blockquotes
        html = re.sub(r'^&gt;\s*(.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)

        # Unordered lists
        html = re.sub(r'^\s*-\s+(.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', html)

        # Ordered lists
        html = re.sub(r'^\s*\d+\.\s+(.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)

        # Paragraphs
        html = re.sub(r'\n\n+', '</p><p>', html)
        html = '<p>' + html + '</p>'

        return html


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
