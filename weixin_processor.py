"""
Weixin Processor Module - Extract content from WeChat Official Account articles
"""
import re
import time
from typing import Optional, Dict, Any

from content_processor import ContentProcessor, ProcessedContent
from url_detector import URLInfo


class WeixinProcessor(ContentProcessor):
    """
    Processor for WeChat (微信公众号) articles
    Uses web scraping to extract article content
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
        """Can process WeChat article URLs"""
        return url_info.url_type.value == "wechat"

    def extract(self, url_info: URLInfo) -> ProcessedContent:
        """Extract WeChat article content"""
        self._start_timer()
        result = self._create_base_content(url_info)

        try:
            # Prefer Firecrawl if available
            if self.firecrawl_available:
                content = self._extract_with_firecrawl(url_info.url)
            elif self.requests_available:
                content = self._extract_with_requests(url_info.url)
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
            wait_for=2000,
            headers={
                'User-Agent': 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Mobile Safari/537.36 MicroMessenger/8.0.0.1840'
            }
        )

        # Extract metadata from scraped content
        title = getattr(scrape_result, 'title', '') or "微信文章"
        markdown = getattr(scrape_result, 'markdown', '')
        html = getattr(scrape_result, 'html', '')
        description = getattr(scrape_result, 'description', '')

        # Extract additional metadata
        author = self._extract_author(markdown, html)
        publish_date = self._extract_publish_date(markdown, html)
        account_name = self._extract_account_name(markdown, html)

        return {
            "title": title,
            "url": url,
            "main_content": markdown,
            "html": html,
            "summary": description or self._generate_summary(markdown),
            "metadata": {
                "platform": "wechat",
                "author": author,
                "account_name": account_name,
                "publish_date": publish_date,
                "article_id": self._extract_article_id(url),
                "tags": self._extract_tags(markdown),
                "read_count": self._extract_read_count(markdown),
                "like_count": self._extract_like_count(markdown),
            },
            "extracted_data": {
                "source": "firecrawl"
            }
        }

    def _extract_with_requests(self, url: str) -> Dict[str, Any]:
        """Extract using requests + BeautifulSoup (fallback)"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Mobile Safari/537.36 MicroMessenger/8.0.0.1840',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }

        response = self.requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = self.bs4(response.content, 'html.parser')

        # Extract basic metadata
        title = soup.find('meta', property='og:title')
        title = title.get('content', '') if title else (soup.find('title') or '').text

        description = soup.find('meta', property='og:description')
        description = description.get('content', '') if description else ''

        author = soup.find('meta', property='og:article:author')
        author = author.get('content', '') if author else ''

        publish_time = soup.find('meta', property='article:published_time')
        publish_time = publish_time.get('content', '') if publish_time else ''

        # Extract article content
        article_body = soup.find('div', class_='rich_media_content') or soup.find('div', id='js_content')
        main_content = article_body.get_text('\n', strip=True) if article_body else ''

        # Extract account name
        account_name_elem = soup.find('a', class_='account_name') or soup.find('span', class_='rich_meta_title')
        account_name = account_name_elem.get_text(strip=True) if account_name_elem else ''

        return {
            "title": title or "微信文章",
            "url": url,
            "main_content": main_content or soup.get_text('\n', strip=True)[:5000],
            "html": str(soup),
            "summary": description or self._generate_summary(main_content),
            "metadata": {
                "platform": "wechat",
                "author": author,
                "account_name": account_name,
                "publish_date": publish_time,
                "article_id": self._extract_article_id(url),
                "tags": [],
                "read_count": 0,
                "like_count": 0,
            },
            "extracted_data": {
                "source": "requests"
            }
        }

    def _extract_author(self, markdown: str, html: str) -> str:
        """Extract author name from content"""
        # Try common patterns
        patterns = [
            r'作者[：:]\s*([^\n@]+)',
            r'Author[：:]\s*([^\n@]+)',
            r'<meta\s+property=["\']article:author["\']\s+content=["\']([^"\']+)["\']',
        ]

        text_to_search = markdown[:3000] + " " + html[:3000]
        for pattern in patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_publish_date(self, markdown: str, html: str) -> str:
        """Extract publish date"""
        patterns = [
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{4}年\d{1,2}月\d{1,2}日)',
            r'<meta\s+property=["\']article:published_time["\']\s+content=["\']([^"\']+)["\']',
        ]

        text_to_search = markdown[:3000] + " " + html[:3000]
        for pattern in patterns:
            match = re.search(pattern, text_to_search)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_account_name(self, markdown: str, html: str) -> str:
        """Extract WeChat account name"""
        patterns = [
            r'公众号[：:]\s*([^\n@]+)',
            r'来自[:\s]+([^\n@]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, markdown[:2000])
            if match:
                return match.group(1).strip()
        return ""

    def _extract_article_id(self, url: str) -> str:
        """Extract article ID from URL"""
        match = re.search(r'/s/([A-Za-z0-9_-]+)', url)
        if match:
            return match.group(1)
        return ""

    def _extract_tags(self, markdown: str) -> list:
        """Extract tags from content"""
        # Look for hashtags or keywords
        hashtag_pattern = r'#([^\s#]+)'
        tags = re.findall(hashtag_pattern, markdown)
        return tags[:10]

    def _extract_read_count(self, markdown: str) -> int:
        """Extract read count if available"""
        pattern = r'阅读\s*(\d+(?:\.\d+)?[kKwW万]?)'
        match = re.search(pattern, markdown)
        if match:
            return self._parse_number(match.group(1))
        return 0

    def _extract_like_count(self, markdown: str) -> int:
        """Extract like count if available"""
        pattern = r'(?:点赞|喜欢)\s*(\d+(?:\.\d+)?[kKwW万]?)'
        match = re.search(pattern, markdown)
        if match:
            return self._parse_number(match.group(1))
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

    def _generate_summary(self, content: str) -> str:
        """Generate a summary from content"""
        # Take first few meaningful sentences
        sentences = re.split(r'[。！？\n]', content)
        summary_sentences = []

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 10 and not sentence.startswith('#'):
                summary_sentences.append(sentence)
                if len(''.join(summary_sentences)) > 200:
                    break

        summary = '。'.join(summary_sentences[:3])
        if summary and not summary.endswith('。'):
            summary += '。'

        return summary or content[:200]

    def _build_media_info(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Build media information from content"""
        media = {
            "type": "article",
            "images": [],
            "videos": [],
            "thumbnails": []
        }

        # Extract images from markdown
        markdown = content.get("main_content", "")
        img_pattern = r'!\[.*?\]\((.*?)\)'
        images = re.findall(img_pattern, markdown)
        media["images"] = images[:20]
        media["thumbnails"] = images[:5]  # First few images as thumbnails

        # Check for videos
        if '<video' in content.get("html", "") or 'mp4' in markdown.lower():
            media["type"] = "mixed"

        return media
