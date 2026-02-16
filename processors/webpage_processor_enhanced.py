"""
增强的网页处理器

实现多层Fallback策略：
1. Firecrawl API（首选，高成功率）
2. 增强的requests + BeautifulSoup（备用）
3. 简单的requests获取（最后fallback）
"""
import os
import logging
import requests
from bs4 import BeautifulSoup
from content_processor import ContentProcessor, ProcessedContent, URLInfo
from typing import Optional

logger = logging.getLogger(__name__)


class EnhancedWebPageProcessor(ContentProcessor):
    """
    增强的网页处理器

    实现多层Fallback策略确保高可用性
    """

    def __init__(self):
        super().__init__()
        self.enabled = bool(os.getenv('FIRECRAWL_API_KEY'))
        self.firecrawl = None
        self.session = None

        # 初始化Firecrawl（如果可用）
        if self.enabled:
            try:
                from firecrawl import Firecrawl
                self.firecrawl = Firecrawl(api_key=os.getenv('FIRECRAWL_API_KEY'))
                logger.info("✅ Firecrawl初始化成功")
            except Exception as e:
                logger.warning(f"⚠️ Firecrawl初始化失败: {e}")
                self.enabled = False

        # 初始化requests会话
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def can_process(self, url_info: URLInfo) -> bool:
        """Can process any webpage URL"""
        return url_info.url_type.value == "webpage"

    def extract(self, url_info: URLInfo) -> ProcessedContent:
        """
        提取网页内容

        Fallback策略：
        1. Firecrawl API（如果可用）
        2. BeautifulSoup解析
        3. 简单HTML获取
        """
        self._start_timer()
        result = self._create_base_content(url_info)

        # 方法1: Firecrawl（如果已启用）
        if self.enabled and self.firecrawl:
            try:
                logger.info(f"使用Firecrawl提取: {url_info.url}")
                return self._extract_with_firecrawl(url_info)
            except Exception as e:
                logger.warning(f"Firecrawl提取失败: {e}，尝试Fallback")
                result.processing_info['fallback_reason'] = f'Firecrawl失败: {str(e)}'

        # 方法2: BeautifulSoup解析
        try:
            logger.info(f"使用BeautifulSoup解析: {url_info.url}")
            return self._extract_with_beautifulsoup(url_info)
        except Exception as e:
            logger.warning(f"BeautifulSoup解析失败: {e}，尝试Fallback")
            result.processing_info['fallback_reason'] = f'BeautifulSoup失败: {str(e)}'

        # 方法3: 简单获取
        try:
            logger.info(f"使用简单HTML获取: {url_info.url}")
            return self._extract_simple(url_info)
        except Exception as e:
            logger.error(f"所有提取方法失败: {e}")
            result.processing_info['success'] = False
            result.processing_info['errors'].append(f'All extraction methods failed: {str(e)}')

        result.processing_info['processing_time'] = self._end_timer()
        return result

    def _extract_with_firecrawl(self, url_info: URLInfo) -> ProcessedContent:
        """使用Firecrawl API提取内容"""
        scrape_result = self.firecrawl.scrape(
            url_info.url,
            formats=['markdown', 'html'],
            only_main_content=True,  # 修复：使用snake_case
            wait_for=2000,  # 修复：使用snake_case
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
        )

        result = self._create_base_content(url_info)

        # 提取内容
        if hasattr(scrape_result, 'markdown'):
            result.content['main_content'] = scrape_result.markdown
            result.content['raw_content'] = scrape_result.markdown

        if hasattr(scrape_result, 'html'):
            soup = BeautifulSoup(scrape_result.html, 'html.parser')
            result.content['title'] = self._extract_title(soup)
            result.content['metadata']['html'] = scrape_result.html

        result.processing_info['method'] = 'firecrawl'
        result.processing_info['success'] = True
        return result

    def _extract_with_beautifulsoup(self, url_info: URLInfo) -> ProcessedContent:
        """使用BeautifulSoup解析网页"""
        response = self.session.get(url_info.url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        result = self._create_base_content(url_info)

        # 提取标题
        result.content['title'] = self._extract_title(soup)

        # 提取主要内容
        main_content = self._extract_main_content(soup)
        result.content['main_content'] = main_content
        result.content['raw_content'] = response.text

        # 提取元数据
        result.content['metadata'] = self._extract_metadata(soup, response)
        result.processing_info['method'] = 'beautifulsoup'
        result.processing_info['success'] = bool(main_content)

        if not main_content:
            result.processing_info['errors'].append('No main content found')

        return result

    def _extract_simple(self, url_info: URLInfo) -> ProcessedContent:
        """简单HTML获取（最后fallback）"""
        response = self.session.get(url_info.url, timeout=5)
        response.raise_for_status()

        result = self._create_base_content(url_info)
        result.content['title'] = url_info.url  # 使用URL作为标题
        result.content['main_content'] = response.text[:5000]  # 限制长度
        result.content['raw_content'] = response.text
        result.content['metadata'] = {
            'status_code': response.status_code,
            'content_length': len(response.text)
        }
        result.processing_info['method'] = 'simple'
        result.processing_info['success'] = True
        result.processing_info['warnings'].append('Using simple extraction, content may be incomplete')

        return result

    def _extract_title(self, soup) -> str:
        """提取页面标题"""
        # 尝试多种方法获取标题
        title_methods = [
            lambda: soup.find('h1').get_text(strip=True),
            lambda: soup.find('title').get_text(strip=True),
            lambda: soup.find('meta', property='og:title').get('content', ''),
            lambda: soup.find('h2').get_text(strip=True)
        ]

        for method in title_methods:
            try:
                title = method()
                if title:
                    return title[:200]  # 限制标题长度
            except:
                continue

        return ''

    def _extract_main_content(self, soup) -> str:
        """提取主要内容"""
        # 常见的主要内容选择器（按优先级）
        content_selectors = [
            ('article', {}),
            ('main', {}),
            ('.content', {}),
            ('.post-content', {}),
            ('#content', {}),
            ('.article-body', {}),
            ('.entry-content', {}),
        ]

        for selector, kwargs in content_selectors:
            element = soup.select_one(selector)
            if element:
                # 清理内容
                for tag in element.find_all(['script', 'style', 'nav', 'footer', 'header']):
                    tag.decompose()

                text = element.get_text(separator='\n', strip=True)
                if len(text) > 100:  # 至少100字符
                    return text

        # Fallback到body
        body = soup.find('body')
        if body:
            return body.get_text(separator='\n', strip=True)[:5000]

        return ''

    def _extract_metadata(self, soup, response) -> dict:
        """提取页面元数据"""
        metadata = {}

        # 基础信息
        metadata['status_code'] = response.status_code
        metadata['content_length'] = len(response.text)

        # Meta标签
        meta_tags = {
            'description': soup.find('meta', attrs={'name': 'description'}),
            'keywords': soup.find('meta', attrs={'name': 'keywords'}),
            'author': soup.find('meta', attrs={'name': 'author'}),
            'og:title': soup.find('meta', property='og:title'),
            'og:description': soup.find('meta', property='og:description'),
            'og:image': soup.find('meta', property='og:image'),
        }

        for key, tag in meta_tags.items():
            if tag:
                metadata[key] = tag.get('content', '')

        # 结构化数据
        if soup.find('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(soup.find('script', type='application/ld+json').string)
                metadata['structured_data'] = data
            except:
                pass

        return metadata

    def _create_error_result(self, url_info: URLInfo, error_message: str) -> ProcessedContent:
        """创建错误结果"""
        result = self._create_base_content(url_info)
        result.processing_info['success'] = False
        result.processing_info['errors'].append(error_message)
        result.processing_info['processing_time'] = self._end_timer()
        return result


# 导出
def create_enhanced_webpage_processor() -> EnhancedWebPageProcessor:
    """工厂函数：创建增强的网页处理器"""
    return EnhancedWebPageProcessor()


if __name__ == "__main__":
    import sys
    from url_detector import detect_url

    if len(sys.argv) > 1:
        url = sys.argv[1]
        url_info = detect_url(url)

        if url_info:
            processor = EnhancedWebPageProcessor()
            result = processor.extract(url_info)

            print(f"URL: {url}")
            print(f"成功: {result.processing_info.get('success')}")
            print(f"方法: {result.processing_info.get('method')}")
            print(f"标题: {result.content.get('title', 'N/A')}")
            print(f"内容长度: {len(result.content.get('main_content', ''))}")
