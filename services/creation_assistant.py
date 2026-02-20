"""
AI Creation Assistant Service Module - AI-powered creative support

This module provides AI assistance for creative projects:
- Outline generation from source materials
- Content gap analysis
- Section expansion
- Connection suggestions
- Citation management
- AI Writing Workflow (based on LawrenceW_Zen's 最小可闭环的AI写作工作流)

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
"""
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import logging
from dotenv import load_dotenv

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
            return None

        # Build prompt for title generation
        prompt = self._build_title_prompt(project, content, num_titles)

        # Call LLM
        result = self._call_llm(prompt)

        if result:
            titles = self._parse_titles(result, num_titles)
            return titles

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
            logger.warning("No LLM client available")
            return None

        try:
            # Use deepseek or openai
            model = os.environ.get('LLM_MODEL', 'deepseek-chat')

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a professional writing assistant. Help users with their creative writing projects. Respond in Chinese if the user's context is in Chinese."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
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
        prompt = f"""基于以下内容，生成{num_titles}个标题建议。

项目类型: {project.project_type}

内容摘要:
{content[:2000]}

请生成以下类型的标题:
1. 常规标题 (中性、描述性)
2. 钩子型标题 (引起好奇)
3. 标题党风格 (有争议/夸张)
4. 问答型标题 (提问引发思考)
5. 数字型标题 (使用数据和列表)

请用JSON格式回复:
[{{"type": "常规", "title": "标题内容", "reason": "为什么好"}}, ...]"""

        return prompt

    def _build_platform_prompt(
        self,
        project: Any,
        content: str,
        platform: str
    ) -> str:
        """Build prompt for platform conversion"""
        platform_info = {
            'x': 'X/Twitter: 最多280字符，支持hashtag和@提及，使用简洁有力的表达',
            'weixin': '微信公众号: 支持富文本，可添加图片和链接，标题吸引人',
            'linkedin': 'LinkedIn: 专业风格，可添加话题标签，注重个人品牌',
            'xiaohongshu': '小红书: Emoji丰富，段落短，图文结合'
        }

        platform_desc = platform_info.get(platform, '通用格式')

        prompt = f"""将以下内容转换为{platform}格式。

平台特点: {platform_desc}

原始内容:
{content[:3000]}

请转换为适合{platform}平台的格式，保留核心内容但调整表达方式。"""

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

        # Try to extract JSON array
        json_match = re.search(r'\[[\s\S]*\]', result)
        if json_match:
            try:
                titles = json.loads(json_match.group())
                return titles[:num_titles]
            except:
                pass

        # Fallback: parse line by line
        titles = []
        for line in result.split('\n'):
            if line.strip() and not line.startswith('#'):
                titles.append({
                    'type': '常规',
                    'title': line.strip().lstrip('0123456789. '),
                    'reason': 'From AI suggestion'
                })

        return titles[:num_titles]

    def _get_platform_notes(self, platform: str) -> str:
        """Get formatting notes for platform"""
        notes = {
            'x': '✓ 最少280字符\n✓ 使用hashtag增加曝光\n✓ 可添加1-4张图片',
            'weixin': '✓ 标题越吸引越好\n✓ 摘要要有吸引力\n✓ 可添加原文链接',
            'linkedin': '✓ 添加专业话题标签\n✓ 首行要有吸引力\n✓ 建议添加图片',
            'xiaohongsho': '✓ Emoji要丰富\n✓ 段落要短\n✓ 结尾要有互动引导'
        }
        return notes.get(platform, '请根据平台特点调整')


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
