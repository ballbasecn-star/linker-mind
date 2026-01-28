"""
AI Analyzer Module - DeepSeek integration for content analysis
"""
import os
import json
from typing import Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

from content_processor import ProcessedContent

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Allow module to load without API key (AI features will be disabled)
if not DEEPSEEK_API_KEY:
    import warnings
    warnings.warn("DEEPSEEK_API_KEY not found in environment variables. AI analysis will be disabled.")


class AIAnalyzer:
    """
    AI-powered content analyzer using DeepSeek API
    """

    def __init__(self):
        self.enabled = bool(DEEPSEEK_API_KEY)
        if self.enabled:
            self.client = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com"
            )
        else:
            self.client = None

    def analyze(self, content: ProcessedContent) -> ProcessedContent:
        """
        Analyze processed content and enrich with AI insights

        Args:
            content: ProcessedContent object to analyze

        Returns:
            ProcessedContent with AI analysis added
        """
        # Skip analysis if disabled
        if not self.enabled:
            content.ai_analysis = {
                "key_points": [],
                "sentiment": "unknown",
                "topics": [],
                "actionable_items": [],
                "summary": "",
                "disabled": True,
                "reason": "DEEPSEEK_API_KEY not configured"
            }
            return content

        try:
            # Prepare analysis prompt based on content type
            prompt = self._build_analysis_prompt(content)

            # Call DeepSeek API
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={'type': 'json_object'},
                temperature=0.3
            )

            # Parse response
            analysis_result = json.loads(response.choices[0].message.content)

            # Update content with AI analysis
            content.ai_analysis = {
                "key_points": analysis_result.get("key_points", []),
                "sentiment": analysis_result.get("sentiment", "neutral"),
                "topics": analysis_result.get("topics", []),
                "actionable_items": analysis_result.get("actionable_items", []),
                "summary": analysis_result.get("summary", ""),
                "rating": analysis_result.get("rating", None),
                "model": "deepseek-chat",
                "analyzed_at": content.timestamp
            }

            # Update summary in content section
            if "summary" in analysis_result:
                content.content["summary"] = analysis_result["summary"]

            # Extract tags from topics
            if "topics" in analysis_result:
                content.content["metadata"]["tags"] = analysis_result["topics"]

        except Exception as e:
            print(f"⚠️  AI Analysis failed: {e}")
            content.ai_analysis = {
                "key_points": [],
                "sentiment": "unknown",
                "topics": [],
                "actionable_items": [],
                "error": str(e),
                "model": "deepseek-chat",
                "analyzed_at": content.timestamp
            }

        return content

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the AI"""
        return """你是一位专业的信息分析师，擅长内容提取和知识合成。

你的任务是分析提供的内容，并以 JSON 格式输出结构化分析结果，包含以下字段：

1. "summary": 内容的核心摘要，用中文撰写，2-3句话，简明扼要地概括主要内容
2. "key_points": 从内容中提取的 3-5 个关键要点，用中文表达，每点不超过 30 字
3. "sentiment": 内容的整体情感倾向（positive/neutral/negative）
4. "topics": 描述内容的 3-5 个相关主题标签，用中文表达
5. "actionable_items": 从内容中提取的可操作见解或建议
6. "rating": 内容质量/相关性评分，1-10 分（可选）

摘要撰写要求：
- 必须使用中文撰写，语言流畅自然
- 摘要应包含内容的核心观点和价值
- 优先提取具体信息和数据，而非泛泛而谈
- 对于技术内容，突出技术要点和实践价值
- 对于观点内容，提炼核心论点和立场
- 对于新闻内容，概括关键事实和影响
- 摘要长度控制在 100-200 字之间
- 避免使用"本文介绍了"、"文章讨论了"等套话，直接呈现核心内容

关键要点要求：
- 提取最具价值的信息点
- 每个要点独立完整，避免重复
- 使用精炼的语言表达
- 突出独特见解，而非表面观点

主题标签要求：
- 使用中文关键词
- 准确描述内容主题
- 2-4 个字为宜
- 便于检索和分类

输出格式示例（JSON）：
{
  "summary": "本文介绍了模块化架构在软件开发中的优势，包括提高代码可维护性、便于测试和扩展。通过实际案例展示了如何设计和实现插件系统，为开发者提供了可参考的架构模式。",
  "key_points": [
    "模块化设计显著提升代码可维护性",
    "关注点分离使单元测试更加高效",
    "插件架构支持功能的灵活扩展",
    "实际项目中的模块化实践案例"
  ],
  "sentiment": "positive",
  "topics": ["软件架构", "模块化设计", "插件系统", "代码质量"],
  "actionable_items": [
    "在下一个项目中考虑实现插件系统",
    "评估现有代码库的模块化改造机会"
  ],
  "rating": 8
}

重要提醒：
- 所有文本输出必须使用中文
- 输出必须是合法的 JSON 格式
- 对于英文内容，先用中文理解并总结，再输出中文摘要"""

    def _build_analysis_prompt(self, content: ProcessedContent) -> str:
        """Build analysis prompt based on content type"""
        prompt_parts = []

        # 添加内容类型和平台信息
        platform_names = {
            'web': '网页',
            'webpage': '网页',
            'bilibili': 'B站',
            'youtube': 'YouTube',
            'twitter': 'Twitter/X',
            'x': 'Twitter/X',
            'douyin': '抖音',
            'wechat': '微信公众号',
            'direct_video': '视频文件',
            'video': '视频'
        }

        platform_name = platform_names.get(content.platform, content.platform)
        prompt_parts.append(f"内容来源：{platform_name}")
        prompt_parts.append(f"内容类型：{content.source_type}")

        # 添加标题
        if content.content.get("title"):
            prompt_parts.append(f"标题：{content.content['title']}")

        # 添加主内容
        main_content = content.content.get("main_content", "")

        # 截断过长内容
        max_length = 10000
        if len(main_content) > max_length:
            main_content = main_content[:max_length] + "\n\n[内容因过长已截断...]"

        prompt_parts.append(f"\n请分析以下内容：\n\n{main_content}")

        # 添加元数据提示
        metadata = content.content.get("metadata", {})
        if metadata.get("author"):
            prompt_parts.append(f"\n作者：{metadata['author']}")
        if metadata.get("publish_date"):
            prompt_parts.append(f"发布时间：{metadata['publish_date']}")
        if metadata.get("duration"):
            prompt_parts.append(f"时长：{metadata['duration']}")

        # 添加字幕文本（如果有）
        if content.content.get("subtitle_text"):
            subtitle = content.content["subtitle_text"]
            if len(subtitle) > 3000:
                subtitle = subtitle[:3000] + "\n\n[字幕内容已截断...]"
            prompt_parts.append(f"\n视频字幕：\n{subtitle}")

        return "\n".join(prompt_parts)

    def batch_analyze(self, contents: list[ProcessedContent]) -> list[ProcessedContent]:
        """
        Analyze multiple contents in batch

        Args:
            contents: List of ProcessedContent objects

        Returns:
            List of ProcessedContent with AI analysis added
        """
        return [self.analyze(content) for content in contents]


class StorageManager:
    """
    Manages persistent storage of processed content
    """

    def __init__(self, storage_file: str = "linker_data.json"):
        self.storage_file = storage_file

    def save(self, content: ProcessedContent) -> bool:
        """
        Save processed content to JSON file

        Args:
            content: ProcessedContent to save

        Returns:
            True if successful, False otherwise
        """
        try:
            # Load existing data
            storage = []
            if os.path.exists(self.storage_file):
                try:
                    with open(self.storage_file, 'r', encoding='utf-8') as f:
                        storage = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    storage = []

            # Append new content
            storage.append(content.to_dict())

            # Write back to file
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(storage, f, ensure_ascii=False, indent=2)

            print(f"📁 Content saved to {self.storage_file} (ID: {content.id})")
            return True

        except Exception as e:
            print(f"❌ Failed to save content: {e}")
            return False

    def load_all(self) -> list[Dict[str, Any]]:
        """
        Load all stored content

        Returns:
            List of stored content dictionaries
        """
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"❌ Failed to load content: {e}")
            return []

    def search(self, query: str) -> list[Dict[str, Any]]:
        """
        Search stored content by query

        Args:
            query: Search query string

        Returns:
            List of matching content items
        """
        all_content = self.load_all()
        query_lower = query.lower()

        results = []
        for item in all_content:
            # Build searchable text from various fields
            searchable_parts = []

            # Handle title (old format: direct field, new format: nested in content)
            title = item.get("title", "")
            if not title:
                title = item.get("content", {}).get("title", "") if isinstance(item.get("content"), dict) else ""
            searchable_parts.append(title)

            # Handle content (old format: string, new format: dict with main_content)
            content_val = item.get("content", "")
            if isinstance(content_val, dict):
                searchable_parts.append(content_val.get("summary", ""))
                searchable_parts.append(content_val.get("main_content", ""))
            else:
                searchable_parts.append(str(content_val))

            # Handle AI analysis
            ai_analysis = item.get("ai_analysis", {})
            if isinstance(ai_analysis, dict):
                topics = ai_analysis.get("topics", [])
                if topics:
                    searchable_parts.append(" ".join(topics))
                key_points = ai_analysis.get("key_points", [])
                if key_points:
                    searchable_parts.append(" ".join(key_points))

            searchable_text = " ".join(searchable_parts).lower()

            if query_lower in searchable_text:
                results.append(item)

        return results

    def get_by_id(self, content_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific content by ID

        Args:
            content_id: Content ID to retrieve

        Returns:
            Content dictionary if found, None otherwise
        """
        all_content = self.load_all()
        for item in all_content:
            if item.get("id") == content_id:
                return item
        return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored content

        Returns:
            Dictionary with statistics
        """
        all_content = self.load_all()

        stats = {
            "total_items": len(all_content),
            "by_type": {},
            "by_platform": {},
            "with_media": 0,
            "avg_processing_time": 0
        }

        total_time = 0
        time_count = 0

        for item in all_content:
            # Count by type
            source_type = item.get("source_type", "unknown")
            stats["by_type"][source_type] = stats["by_type"].get(source_type, 0) + 1

            # Count by platform
            platform = item.get("platform", "unknown")
            stats["by_platform"][platform] = stats["by_platform"].get(platform, 0) + 1

            # Count media content
            media = item.get("media", {})
            if media.get("images") or media.get("videos"):
                stats["with_media"] += 1

            # Sum processing time
            proc_time = item.get("processing_info", {}).get("processing_time", 0)
            if proc_time > 0:
                total_time += proc_time
                time_count += 1

        if time_count > 0:
            stats["avg_processing_time"] = round(total_time / time_count, 2)

        return stats
