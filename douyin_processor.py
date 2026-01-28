"""
Douyin Processor Module - Extract content from Douyin (TikTok China) videos
"""
import re
import json
import time
from typing import Optional, Dict, Any

from content_processor import ContentProcessor, ProcessedContent
from url_detector import URLInfo


class DouyinProcessor(ContentProcessor):
    """
    Processor for Douyin (抖音) video content
    Uses web scraping to extract video metadata
    """

    def __init__(self):
        super().__init__()
        # Try to import required dependencies
        try:
            import requests
            from bs4 import BeautifulSoup
            self.requests = requests
            self.bs4 = BeautifulSoup
            self.requests_available = True
        except ImportError:
            self.requests_available = False

        # Check if Firecrawl is available
        try:
            from firecrawl import Firecrawl
            import os
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("FIRECRAWL_API_KEY")
            if api_key:
                self.firecrawl = Firecrawl(api_key=api_key)
                self.firecrawl_available = True
            else:
                self.firecrawl_available = False
        except ImportError:
            self.firecrawl_available = False

    def can_process(self, url_info: URLInfo) -> bool:
        """Can process Douyin URLs"""
        return url_info.url_type.value == "douyin"

    def extract(self, url_info: URLInfo) -> ProcessedContent:
        """Extract Douyin video content"""
        self._start_timer()
        result = self._create_base_content(url_info)

        try:
            # Prefer Firecrawl if available
            if self.firecrawl_available:
                content = self._extract_with_firecrawl(url_info.url)
            elif self.requests_available:
                content = self._extract_with_requests(url_info)
            else:
                raise ValueError("Both Firecrawl and requests unavailable. Install dependencies.")

            # Update result with extracted content
            result.content.update(content)
            result.media = self._build_media_info(content)
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": True,
                "errors": []
            })

        except Exception as e:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [str(e)]
            })
            raise

        return result

    def _extract_with_firecrawl(self, url: str) -> Dict[str, Any]:
        """Extract using Firecrawl API"""
        scrape_result = self.firecrawl.scrape(
            url,
            formats={'markdown': True, 'html': True},
            only_main_content=True,
            wait_for=3000,  # Douyin may need more time to load
            headers={
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
            }
        )

        # Extract metadata from scraped content
        title = getattr(scrape_result, 'title', '') or "抖音视频"
        markdown = getattr(scrape_result, 'markdown', '')
        html = getattr(scrape_result, 'html', '')

        # Try to extract additional info from HTML/markdown
        author = self._extract_author(markdown, html)
        description = self._extract_description(markdown)
        likes = self._extract_stats(markdown, 'likes')
        comments = self._extract_stats(markdown, 'comments')

        return {
            "title": title,
            "url": url,
            "main_content": markdown,
            "html": html,
            "metadata": {
                "platform": "douyin",
                "author": author,
                "description": description,
                "likes": likes,
                "comments": comments,
                "shares": self._extract_stats(markdown, 'shares'),
                "tags": self._extract_tags(markdown),
                "publish_date": "",
                "video_id": self._extract_video_id(url)
            },
            "extracted_data": {
                "source": "firecrawl"
            }
        }

    def _extract_with_requests(self, url_info: URLInfo) -> Dict[str, Any]:
        """Extract using requests + BeautifulSoup (fallback)"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }

        response = self.requests.get(url_info.url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = self.bs4(response.content, 'html.parser')

        # Try to extract from script tags (Douyin stores data in JSON)
        script_data = self._extract_script_data(soup)

        title = script_data.get('title', '') or soup.find('title')
        title = title.text if hasattr(title, 'text') else str(title)

        return {
            "title": title or "抖音视频",
            "url": url_info.url,
            "main_content": script_data.get('desc', ''),
            "html": str(soup),
            "metadata": {
                "platform": "douyin",
                "author": script_data.get('author', ''),
                "description": script_data.get('desc', ''),
                "likes": script_data.get('statistics', {}).get('digg_count', 0),
                "comments": script_data.get('statistics', {}).get('comment_count', 0),
                "shares": script_data.get('statistics', {}).get('share_count', 0),
                "tags": script_data.get('text_extra', []),
                "publish_date": "",
                "video_id": url_info.extracted_id
            },
            "extracted_data": {
                "source": "requests",
                "raw_data": script_data
            }
        }

    def _extract_author(self, markdown: str, html: str) -> str:
        """Extract author name from content"""
        # Try various patterns
        patterns = [
            r'@([^\s@]+)',
            r'作者[：:]\s*([^\n@]+)',
            r'Author[：:]\s*([^\n@]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, markdown[:2000])  # Search in first 2000 chars
            if match:
                return match.group(1).strip()
        return ""

    def _extract_description(self, markdown: str) -> str:
        """Extract video description"""
        # Usually the first paragraph or line
        lines = markdown.split('\n')
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('!'):
                return line[:500]
        return ""

    def _extract_stats(self, markdown: str, stat_type: str) -> int:
        """Extract engagement statistics"""
        patterns = {
            'likes': r'(\d+(?:\.\d+)?[kKwW万]?)\s*(?:点赞|likes?|like)',
            'comments': r'(\d+(?:\.\d+)?[kKwW万]?)\s*(?:评论|comments?)',
            'shares': r'(\d+(?:\.\d+)?[kKwW万]?)\s*(?:分享|转发|shares?)',
        }

        pattern = patterns.get(stat_type, '')
        if not pattern:
            return 0

        match = re.search(pattern, markdown, re.IGNORECASE)
        if match:
            num_str = match.group(1)
            return self._parse_number(num_str)
        return 0

    def _parse_number(self, num_str: str) -> int:
        """Parse number with k/w/万 suffix"""
        num_str = num_str.lower().strip()
        multipliers = {
            'k': 1000,
            'w': 10000,
            '万': 10000,
        }

        for suffix, mult in multipliers.items():
            if num_str.endswith(suffix):
                try:
                    return int(float(num_str[:-1]) * mult)
                except ValueError:
                    return 0

        try:
            return int(float(num_str))
        except ValueError:
            return 0

    def _extract_tags(self, markdown: str) -> list:
        """Extract hashtags from content"""
        hashtag_pattern = r'#([^\s#]+)'
        tags = re.findall(hashtag_pattern, markdown)
        return tags[:10]  # Limit to 10 tags

    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from URL"""
        match = re.search(r'/video/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'/note/(\d+)', url)
        if match:
            return match.group(1)
        return ""

    def _extract_script_data(self, soup) -> Dict[str, Any]:
        """Extract JSON data from script tags"""
        for script in soup.find_all('script'):
            if script.string:
                # Look for common Douyin data patterns
                if 'videoData' in script.string or 'window.__INITIAL_STATE__' in script.string:
                    try:
                        # Extract JSON from script
                        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', script.string)
                        if match:
                            return json.loads(match.group(1))
                    except (json.JSONDecodeError, ValueError):
                        pass
        return {}

    def _build_media_info(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Build media information from content"""
        media = {
            "type": "video",
            "images": [],
            "videos": [],
            "thumbnails": []
        }

        # Extract images from markdown
        markdown = content.get("main_content", "")
        img_pattern = r'!\[.*?\]\((.*?)\)'
        images = re.findall(img_pattern, markdown)
        media["images"] = images[:10]
        media["thumbnails"] = images[:5]  # First few images as thumbnails

        return media
