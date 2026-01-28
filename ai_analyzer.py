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

if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY not found in environment variables")


class AIAnalyzer:
    """
    AI-powered content analyzer using DeepSeek API
    """

    def __init__(self):
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com"
        )

    def analyze(self, content: ProcessedContent) -> ProcessedContent:
        """
        Analyze processed content and enrich with AI insights

        Args:
            content: ProcessedContent object to analyze

        Returns:
            ProcessedContent with AI analysis added
        """
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
        return """You are an expert information analyst specializing in content extraction and knowledge synthesis.

Your task is to analyze the provided content and output a structured JSON response with the following fields:

1. "summary": A concise 2-3 sentence summary of the main content
2. "key_points": An array of 3-5 key points extracted from the content (bullet-style, max 20 words each)
3. "sentiment": The overall sentiment of the content (positive/neutral/negative)
4. "topics": An array of 3-5 relevant topics/tags that describe the content
5. "actionable_items": An array of any actionable insights or recommendations derived from the content
6. "rating": A quality/relevance score from 1-10 (optional, based on content value)

Guidelines:
- Be concise and specific
- Focus on valuable, actionable information
- Extract unique insights, not just surface-level points
- Topics should be descriptive but concise (2-4 words each)
- For social media, capture the essence of the post
- For videos, focus on key themes and takeaways
- Output MUST be valid JSON

Example output format:
{
  "summary": "The article discusses the benefits of modular architecture in software development...",
  "key_points": [
    "Modular design improves code maintainability",
    "Separation of concerns enables better testing",
    "Plugin architecture allows easy feature extension"
  ],
  "sentiment": "positive",
  "topics": ["software architecture", "modularity", "design patterns", "code quality"],
  "actionable_items": [
    "Consider implementing a plugin system for your next project",
    "Evaluate current codebase for modularization opportunities"
  ],
  "rating": 8
}"""

    def _build_analysis_prompt(self, content: ProcessedContent) -> str:
        """Build analysis prompt based on content type"""
        prompt_parts = []

        # Add context about source type
        prompt_parts.append(f"Source Type: {content.source_type}")
        prompt_parts.append(f"Platform: {content.platform}")

        # Add title if available
        if content.content.get("title"):
            prompt_parts.append(f"Title: {content.content['title']}")

        # Add main content
        main_content = content.content.get("main_content", "")

        # Truncate content if too long (DeepSeek has context limits)
        max_length = 8000
        if len(main_content) > max_length:
            main_content = main_content[:max_length] + "\n\n[Content truncated...]"

        prompt_parts.append(f"\nContent to analyze:\n{main_content}")

        # Add metadata hints
        metadata = content.content.get("metadata", {})
        if metadata.get("author"):
            prompt_parts.append(f"\nAuthor: {metadata['author']}")
        if metadata.get("publish_date"):
            prompt_parts.append(f"Published: {metadata['publish_date']}")

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
