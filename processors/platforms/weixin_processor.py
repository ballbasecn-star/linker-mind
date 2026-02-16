"""
微信处理器 - 增强版
改进：
1. 添加MCP WebReader支持（优先级最高）
2. 增强requests方法（更多降级策略）
3. 添加script数据提取（微信公众号文章通常在script中）
4. 统一错误处理
5. 数据完整性验证
"""
import re
import json
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from processors.content_processor import ContentProcessor, ProcessedContent
from url_detector import URLInfo

logger = logging.getLogger(__name__)


@dataclass
class ExtractionError(Exception):
    """提取错误基类"""
    error_code: str
    message: str
    recoverable: bool = False
    retry_after: int = 0


class WeixinProcessorEnhanced(ContentProcessor):
    """
    增强版微信处理器

    改进点：
    1. 支持MCP WebReader
    2. 增强requests方法
    3. 添加script数据提取
    4. 统一错误处理
    5. 数据完整性验证
    """

    def __init__(self):
        super().__init__()

        # 基础依赖
        try:
            import requests
            from bs4 import BeautifulSoup
            self.requests = requests
            self.bs4 = BeautifulSoup
            self.requests_available = True
        except ImportError:
            self.requests_available = False

        # Firecrawl支持
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

        # MCP WebReader（优先级最高）
        self.mcp_webreader_available = False
        self.mcp_webreader = None

    def set_mcp_tools(self, mcp_webreader):
        """设置MCP工具"""
        self.mcp_webreader = mcp_webreader
        self.mcp_webreader_available = mcp_webreader is not None

    def can_process(self, url_info: URLInfo) -> bool:
        """判断是否可以处理微信URL"""
        return url_info.url_type.value in ("weixin", "wechat")

    def extract(self, url_info: URLInfo, max_retries: int = 3) -> ProcessedContent:
        """
        提取微信文章内容

        改进的降级顺序：
        MCP WebReader → Firecrawl → 增强requests
        """
        self._start_timer()
        result = self._create_base_content(url_info)

        last_error = None

        for attempt in range(max_retries):
            try:
                content = None

                # 优先级1: MCP WebReader（如果可用）
                if self.mcp_webreader_available and attempt == 0:
                    try:
                        content = self._extract_with_mcp(url_info.url)
                        result.processing_info["extraction_method"] = "mcp_webreader"
                    except Exception as e:
                        result.processing_info["mcp_error"] = str(e)

                # 优先级2: Firecrawl
                if not content and self.firecrawl_available:
                    try:
                        content = self._extract_with_firecrawl(url_info.url)
                        result.processing_info["extraction_method"] = "firecrawl"
                    except Exception as e:
                        result.processing_info["firecrawl_error"] = str(e)

                # 优先级3: 增强requests
                if not content and self.requests_available:
                    content = self._extract_with_requests_enhanced(url_info.url)
                    result.processing_info["extraction_method"] = "requests_enhanced"

                # 验证提取结果
                if not content:
                    raise ValueError("Failed to extract content from all methods")

                if not content.get("main_content") or len(content.get("main_content", "")) < 50:
                    logger.warning(f"Extracted content too short for {url_info.url}")

                # 更新结果
                result.content.update(content)
                result.media = self._build_media_info(content)

                result.processing_info.update({
                    "processing_time": self._end_timer(),
                    "success": True,
                    "errors": []
                })

                return result

            except ValueError as e:
                last_error = e
                raise

            except Exception as e:
                last_error = e
                logger.error(f"Extraction error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                raise

        result.processing_info.update({
            "processing_time": self._end_timer(),
            "success": False,
            "errors": [str(last_error)]
        })
        raise last_error

    def _extract_with_mcp(self, url: str) -> Dict[str, Any]:
        """使用MCP WebReader提取"""
        if not self.mcp_webreader:
            raise ValueError("MCP WebReader not available")

        result = self.mcp_webreader(
            url=url,
            return_format="markdown",
            timeout=30,
            retain_images=True
        )

        markdown = getattr(result, 'markdown', '') or str(result)

        return {
            "title": self._extract_title_from_markdown(markdown),
            "url": url,
            "main_content": markdown,
            "html": getattr(result, 'html', '') if hasattr(result, 'html') else '',
            "metadata": {
                "platform": "wechat",
                "author": self._extract_author(markdown),
                "description": self._extract_description(markdown),
                "article_id": self._extract_article_id(url),
                "tags": self._extract_tags(markdown)
            }
        }

    def _extract_with_firecrawl(self, url: str) -> Dict[str, Any]:
        """使用Firecrawl提取"""
        scrape_result = self.firecrawl.scrape(
            url,
            formats={'markdown': True, 'html': True},
            only_main_content=True,
            wait_for=2000,
            headers={
                'User-Agent': 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Mobile Safari/537.36'
            }
        )

        title = getattr(scrape_result, 'title', '') or "微信文章"
        markdown = getattr(scrape_result, 'markdown', '')
        html = getattr(scrape_result, 'html', '')

        return {
            "title": title,
            "url": url,
            "main_content": markdown,
            "html": html,
            "metadata": {
                "platform": "wechat",
                "author": self._extract_author(markdown, html),
                "description": self._extract_description(markdown, html),
                "article_id": self._extract_article_id(url),
                "tags": self._extract_tags(markdown),
                "account_name": self._extract_account_name(markdown, html)
            }
        }

    def _extract_with_requests_enhanced(self, url: str) -> Dict[str, Any]:
        """
        增强的requests提取方法

        改进点：
        1. 添加script数据提取
        2. 多层降级策略
        3. 更完整的headers
        """
        if not self.requests_available:
            raise ValueError("requests not available")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'https://mp.weixin.qq.com/',
        }

        response = self.requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = self.bs4(response.content, 'html.parser')

        content = {}

        # 优先级1: 提取script数据（新增）
        script_data = self._extract_script_data(soup)
        if script_data:
            content.update(script_data)

        # 优先级2: 提取meta标签
        if not content.get('title') or not content.get('main_content'):
            meta_data = self._extract_meta_tags(soup)
            content.update(meta_data)

        # 优先级3: 提取HTML结构
        if not content.get('main_content'):
            html_data = self._extract_html_structure(soup)
            content.update(html_data)

        # 验证提取结果
        if not content.get('title'):
            content['title'] = soup.find('title').text if soup.find('title') else "微信文章"

        if not content.get('main_content'):
            content['main_content'] = soup.get_text('\n', strip=True)[:5000]

        return {
            "title": content.get('title', ''),
            "url": url,
            "main_content": content.get('main_content', ''),
            "html": str(soup),
            "metadata": {
                "platform": "wechat",
                "author": content.get('author', ''),
                "account_name": content.get('account_name', ''),
                "description": content.get('description', ''),
                "article_id": content.get('article_id', self._extract_article_id(url)),
                "tags": content.get('tags', []),
                "publish_date": content.get('publish_date', '')
            },
            "extracted_data": {
                "source": "requests_enhanced",
                "script_data": content.get('script_data', {}),
                "meta_data": content.get('meta_data', {}),
                "html_data": content.get('html_data', {})
            }
        }

    def _extract_script_data(self, soup) -> Dict[str, Any]:
        """
        提取script数据

        微信文章通常在script标签中有msg数据
        """
        for script in soup.find_all('script'):
            if not script.string:
                continue

            # 查找msg变量
            msg_match = re.search(r'var msg = ({.+?});', script.string)
            if msg_match:
                try:
                    msg_data = json.loads(msg_match.group(1))
                    if isinstance(msg_data, dict):
                        return self._normalize_weixin_msg_data(msg_data)
                except Exception:
                    pass

            # 查找其他常见格式
            for pattern in [
                r'window\.msg\s*=\s*({.+?});',
                r'ct\s*=\s*({.+?});',
            ]:
                match = re.search(pattern, script.string)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        if isinstance(data, dict):
                            return self._normalize_weixin_msg_data(data)
                    except Exception:
                        pass

        return {}

    def _normalize_weixin_msg_data(self, data: Dict) -> Dict:
        """标准化微信msg数据"""
        normalized = {}

        # 标题
        if 'title' in data:
            normalized['title'] = data['title']

        # 内容
        if 'content' in data:
            normalized['main_content'] = data['content']

        # 作者信息
        if 'author' in data and isinstance(data['author'], dict):
            author = data['author']
            if 'nickname' in author:
                normalized['author'] = author['nickname']
            if 'public_name' in author:
                normalized['account_name'] = author['public_name']

        # 发布时间
        if 'publish_time' in data:
            normalized['publish_date'] = data['publish_time']
        elif 'create_time' in data:
            normalized['publish_date'] = data['create_time']

        # 文章ID
        if 'article_id' in data:
            normalized['article_id'] = data['article_id']
        elif 'itemid' in data:
            normalized['article_id'] = data['itemid']

        # 封面图
        if 'cover' in data:
            normalized['cover_image'] = data['cover']
        elif 'cdn_url' in data:
            normalized['cover_image'] = data['cdn_url']

        return normalized

    def _extract_meta_tags(self, soup) -> Dict[str, Any]:
        """提取meta标签"""
        meta_data = {}

        # 标题
        for meta_name in ['og:title', 'twitter:title']:
            meta = soup.find('meta', property=meta_name)
            if meta and meta.get('content'):
                meta_data['title'] = meta.get('content')
                break

        # 描述
        for meta_name in ['og:description', 'twitter:description', 'description']:
            meta = soup.find('meta', property=meta_name)
            if meta and meta.get('content'):
                meta_data['description'] = meta.get('content')
                break

        # 作者
        for meta_name in ['og:article:author', 'article:author', 'author']:
            meta = soup.find('meta', property=meta_name)
            if meta and meta.get('content'):
                meta_data['author'] = meta.get('content')
                break

        # 公众号名称
        for meta_name in ['og:article:author', 'weixin:account_nickname']:
            meta = soup.find('meta', property=meta_name)
            if meta and meta.get('content'):
                meta_data['account_name'] = meta.get('content')
                break

        # 封面图
        for meta_name in ['og:image', 'twitter:image']:
            meta = soup.find('meta', property=meta_name)
            if meta and meta.get('content'):
                meta_data['cover_image'] = meta.get('content')
                break

        # 发布时间
        for meta_name in ['og:article:published_time', 'article:published_time']:
            meta = soup.find('meta', property=meta_name)
            if meta and meta.get('content'):
                meta_data['publish_date'] = meta.get('content')
                break

        return meta_data

    def _extract_html_structure(self, soup) -> Dict[str, Any]:
        """提取HTML结构"""
        html_data = {}

        # 多个可能的class名
        content_classes = [
            'rich_media_content',
            'rich_media_area',
            'wx_rich_media_content',
            'js_content',
            'article-content',
            'weui-msg'
        ]

        for class_name in content_classes:
            elem = soup.find('div', class_=class_name)
            if elem:
                html_data['main_content'] = elem.get_text('\n', strip=True)
                break

        # 尝试id选择器
        if not html_data.get('main_content'):
            for elem_id in ['js_content', 'content', 'article-content']:
                elem = soup.find('div', id=elem_id)
                if elem:
                    html_data['main_content'] = elem.get_text('\n', strip=True)
                    break

        # 公众号名称
        account_classes = ['account_name', 'rich_meta_title', 'wx_account_name']
        for class_name in account_classes:
            elem = soup.find('a', class_=class_name) or soup.find('span', class_=class_name)
            if elem:
                html_data['account_name'] = elem.get_text(strip=True)
                break

        return html_data

    def _extract_author(self, markdown: str, html: str = "") -> str:
        """提取作者"""
        patterns = [
            r'作者[：:]\s*([^\s@]+)',
            r'Author[：:]\s*([^\s@]+)',
        ]

        text_to_search = markdown[:3000] + " " + html[:3000]
        for pattern in patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_description(self, markdown: str) -> str:
        """提取描述"""
        lines = markdown.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if line and not line.startswith('#'):
                return line[:500]
        return ""

    def _extract_account_name(self, markdown: str, html: str = "") -> str:
        """提取公众号名称"""
        patterns = [
            r'公众号[：:]\s*([^\s@]+)',
            r'来自[:\s]+([^\s@]+)',
        ]

        text_to_search = markdown[:2000]
        for pattern in patterns:
            match = re.search(pattern, text_to_search)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_article_id(self, url: str) -> str:
        """从URL提取文章ID"""
        match = re.search(r'/s/([A-Za-z0-9_-]+)', url)
        if match:
            return match.group(1)
        return ""

    def _extract_tags(self, markdown: str) -> list:
        """提取标签"""
        hashtag_pattern = r'#([^\s#]+)'
        tags = re.findall(hashtag_pattern, markdown)
        return tags[:10]

    def _extract_title_from_markdown(self, markdown: str) -> str:
        """从markdown提取标题"""
        # 通常第一行或第一个markdown标题
        lines = markdown.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if line.startswith('#'):
                # 移除#标记
                title = line.lstrip('#').strip()
                if len(title) > 3 and len(title) < 200:
                    return title
            elif len(line) > 3 and len(line) < 200:
                return line
        return ""

    def _build_media_info(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """构建媒体信息"""
        media = {
            "type": "article",
            "cover_image": "",
            "images": [],
            "videos": [],
            "thumbnails": []
        }

        # 提取图片
        markdown = content.get("main_content", "")
        img_pattern = r'!\[.*?\]\((.*?)\)'
        images = re.findall(img_pattern, markdown)
        if images:
            media["images"] = images[:20]
            media["thumbnails"] = images[:5]

        # 提取封面图
        extracted_data = content.get("extracted_data", {})
        if extracted_data.get("cover_image"):
            media["cover_image"] = extracted_data["cover_image"]
            media["thumbnails"] = [extracted_data["cover_image"]]

        # 检查是否有视频
        if '<video' in content.get("html", "") or 'mp4' in markdown.lower():
            media["type"] = "mixed"

        return media
