"""
抖音处理器 - 增强版
改进：
1. 增强script数据提取，6种方法优化为更健壮的3层策略
2. 添加Cookie管理、Referer等反爬措施
3. 统一错误处理和重试机制
4. 数据完整性验证
5. 支持MCP WebReader优先级
"""
import re
import json
import time
import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from content_processor import ContentProcessor, ProcessedContent
from url_detector import URLInfo

logger = logging.getLogger(__name__)


@dataclass
class ExtractionError(Exception):
    """提取错误基类"""
    error_code: str
    message: str
    recoverable: bool = False
    retry_after: int = 0


class RateLimitError(ExtractionError):
    """速率限制错误"""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            error_code="RATE_LIMIT",
            message=f"Rate limited, retry after {retry_after}s",
            recoverable=True,
            retry_after=retry_after
        )


class ContentNotFoundError(ExtractionError):
    """内容未找到错误"""
    def __init__(self, url: str):
        super().__init__(
            error_code="CONTENT_NOT_FOUND",
            message=f"Content not found for URL: {url}",
            recoverable=False
        )


class DouyinProcessorEnhanced(ContentProcessor):
    """
    增强版抖音处理器

    改进点：
    1. 更健壮的script数据提取（3层策略）
    2. 增强requests方法（Cookie、Referer）
    3. 统一错误处理和重试机制
    4. 数据完整性验证
    5. 更好的降级顺序
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

        # MCP WebReader（优先级最高）
        self.mcp_webreader_available = False
        self.mcp_webreader = None

        # Video Analysis Service（深度分析）
        self._video_analysis_service = None

        # Cookie管理
        self._cookies = {}
        self._last_cookie_update = 0
        self._cookie_ttl = 3600  # 1小时

        # 代理支持（可选）
        self._proxies = []
        self._current_proxy_index = 0

    def set_mcp_tools(self, mcp_webreader):
        """设置MCP工具"""
        self.mcp_webreader = mcp_webreader
        self.mcp_webreader_available = mcp_webreader is not None

    def set_proxies(self, proxies: List[str]):
        """设置代理池"""
        self._proxies = proxies

    def _get_video_analysis_service(self):
        """获取或创建视频分析服务"""
        if self._video_analysis_service is None:
            try:
                from services.video_analysis_service import VideoAnalysisService
                self._video_analysis_service = VideoAnalysisService()
            except ImportError:
                pass
        return self._video_analysis_service

    def can_process(self, url_info: URLInfo) -> bool:
        """判断是否可以处理抖音URL"""
        return url_info.url_type.value == "douyin"

    def extract(self, url_info: URLInfo, deep_analysis: bool = False,
              max_retries: int = 3, remote_video_info: dict = None) -> ProcessedContent:
        """
        提取抖音视频内容

        Args:
            url_info: URL信息
            deep_analysis: 是否进行深度分析
            max_retries: 最大重试次数
            remote_video_info: 从远程服务获取的视频信息

        Returns:
            ProcessedContent对象
        """
        self._start_timer()
        result = self._create_base_content(url_info)

        # 如果有远程视频信息，先填充基本字段
        if remote_video_info:
            logger.info(f"使用远程视频信息: {remote_video_info}")
            if remote_video_info.get('title'):
                result.content['title'] = remote_video_info.get('title')
            if remote_video_info.get('description'):
                result.content['description'] = remote_video_info.get('description')
            if remote_video_info.get('cover_url'):
                result.content['cover_url'] = remote_video_info.get('cover_url')
            if remote_video_info.get('video_id'):
                result.content['video_id'] = remote_video_info.get('video_id')

        # 展开短链接
        expanded_url = self._expand_short_url(url_info.url)
        if expanded_url != url_info.url:
            result.processing_info["url_expanded"] = True
            result.processing_info["original_url"] = url_info.url

        last_error = None

        # 尝试提取（带重试）
        for attempt in range(max_retries):
            try:
                content = None

                # 优先级1: MCP WebReader（如果可用）
                if self.mcp_webreader_available and attempt == 0:
                    content = self._extract_with_mcp(expanded_url)
                    result.processing_info["extraction_method"] = "mcp_webreader"

                # 优先级2: 增强requests
                elif self.requests_available:
                    content = self._extract_with_requests_enhanced(expanded_url)
                    result.processing_info["extraction_method"] = "requests_enhanced"

                # 优先级3: Firecrawl（最后降级）
                if not content:
                    content = self._extract_with_firecrawl(expanded_url)
                    result.processing_info["extraction_method"] = "firecrawl"

                # 验证提取结果
                if not content or not content.get("title"):
                    raise ContentNotFoundError(expanded_url)

                # 更新结果
                result.content.update(content)
                result.media = self._build_media_info(content)

                # 深度分析（如果请求）
                if deep_analysis:
                    video_analysis = self._perform_deep_analysis(expanded_url, content)
                    if video_analysis:
                        result.content['transcript'] = video_analysis.get('transcript', '')
                        result.content['transcript_summary'] = video_analysis.get('summary', '')
                        result.content['key_points'] = video_analysis.get('key_points', [])
                        result.processing_info['video_analysis'] = video_analysis
                        result.processing_info['deep_analysis'] = True

                result.processing_info.update({
                    "processing_time": self._end_timer(),
                    "success": True,
                    "errors": []
                })

                return result

            except RateLimitError as e:
                last_error = e
                if attempt < max_retries - 1 and e.recoverable:
                    logger.warning(f"Rate limited, waiting {e.retry_after}s before retry")
                    time.sleep(e.retry_after)
                    continue
                raise

            except ContentNotFoundError as e:
                last_error = e
                raise  # 不可恢复，直接抛出

            except ExtractionError as e:
                last_error = e
                if attempt < max_retries - 1 and e.recoverable:
                    logger.warning(f"Extraction error (recoverable): {e.message}, retrying...")
                    time.sleep(1)
                    continue
                raise

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error during extraction: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                raise ExtractionError(
                    error_code="UNKNOWN_ERROR",
                    message=str(e),
                    recoverable=True
                )

        # 所有重试都失败
        result.processing_info.update({
            "processing_time": self._end_timer(),
            "success": False,
            "errors": [last_error.message if last_error else "Unknown error"]
        })
        raise last_error or ExtractionError(
            error_code="EXTRACTION_FAILED",
            message="Failed to extract content after all retries"
        )

    def _extract_with_requests_enhanced(self, url: str) -> Dict[str, Any]:
        """
        增强的requests提取方法

        改进点：
        1. 添加Cookie管理
        2. 添加Referer
        3. 更完整的User-Agent
        4. 更新Cookie
        """
        if not self.requests_available:
            raise ValueError("requests not available")

        headers = {
            'User-Agent': 'com.ss.android.ugc.aweme/280102 (Linux; U; Android 12; zh_CN; V2205001; Build/280102; Cronet/80107000; Device/samsung; Model/SM-G981B; Account Kit/3.13; Width/1080; Rotate/0; Univ/CN; Launch/3; Adjust/0; Touch/0; Mu/0; Support/abs; GPU Adreno/640; Locale/zh_CN; opengl/3; Region/CN; Conteng/1; Mode/01; Height/2400; AndroidOS/12; Neck/0; Wv/0; UseEs/0; B/name/Chrome; M/Baddress; L/CN; O/CN; RI/0; RS/0; Im/0; C/douyin; A/0; Sp/0; S/0; SF/0; SV/0; GV/1; V/0; F/0; FP/0; SH/0; ST/0; IL/0; Pack/1; Ad/1; Brand/; Crash/0; PD/1; EV/0; FP/0; F/1; CO/0; CN/1)',
            'Accept': 'application/json, text/plain, application/x-javascript',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.douyin.com/',
            # 添加Cookie
            'Cookie': self._get_cookies(),
        }

        session = self.requests.Session()

        try:
            # 第一次请求获取Cookie
            response = session.head(url, headers=headers, timeout=10, allow_redirects=True)

            # 更新Cookie
            if 'Set-Cookie' in response.headers:
                session.cookies.update(response.cookies)
                self._update_cookies_from_response(response)

            # 第二次请求获取内容
            response = session.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = self.bs4(response.content, 'html.parser')

            # 使用增强的script提取
            script_data = self._extract_script_data_robust(soup)

            # 构建结果
            return self._build_content_from_script_data(
                url, soup, script_data
            )

        except self.requests.exceptions.RequestException as e:
            raise ExtractionError(
                error_code="NETWORK_ERROR",
                message=f"Network error: {e}",
                recoverable=True,
                retry_after=5
            )
        except Exception as e:
            raise ExtractionError(
                error_code="UNKNOWN_ERROR",
                message=f"Request extraction failed: {e}",
                recoverable=True
            )

    def _extract_script_data_robust(self, soup) -> Dict[str, Any]:
        """
        健壮的script数据提取方法

        3层策略：
        1. 优先使用最可靠的数据源（videoId、desc直接匹配）
        2. 尝试完整JSON解析
        3. 使用URL参数作为最后降级
        """
        result = {}

        # 方法1: 直接查找最可靠的数据
        for script in soup.find_all('script'):
            if not script.string:
                continue

            # 直接匹配videoId
            video_match = re.search(r'"videoId":"(\d+)"', script.string)
            if video_match:
                result['video_id'] = video_match.group(1)

            # 直接匹配desc
            desc_match = re.search(r'"desc":"([^"]+)"', script.string)
            if desc_match:
                result['desc'] = desc_match.group(1)

        # 方法2: 如果基本数据找到了，尝试完整解析
        if 'video_id' in result or 'desc' in result:
            for script in soup.find_all('script'):
                if not script.string:
                    continue

                try:
                    # 查找JSON块
                    json_start = script.string.find('{')
                    json_end = script.string.rfind('}') + 1

                    if json_start >= 0 and json_end > json_start:
                        json_str = script.string[json_start:json_end]
                        data = json.loads(json_str)

                        # 标准化字段
                        normalized = self._normalize_douyin_data(data)
                        result.update(normalized)

                        # 验证数据完整性
                        if 'desc' in normalized or 'video_id' in normalized:
                            return result

                except (json.JSONDecodeError, ValueError, TypeError):
                    continue

        # 方法3: 最后降级到URL参数
        if 'video_id' not in result:
            from urllib.parse import urlparse, parse_qs
            try:
                parsed = urlparse(soup.find('meta', property='og:url')['content'])
                query = parse_qs(parsed.query)

                if 'video_id' in query:
                    result['video_id'] = query['video_id'][0]
                elif 'vid' in query:
                    result['video_id'] = query['vid'][0]
            except Exception:
                pass

        return result

    def _normalize_douyin_data(self, data: Dict) -> Dict:
        """
        标准化抖音数据字段
        """
        normalized = {}

        # 字段映射
        field_mappings = {
            'desc': 'description',
            'aweme_id': 'author_id',
            'nickname': 'author_name',
            'diggCount': 'likes',
            'commentCount': 'comments',
            'shareCount': 'shares',
            'playCount': 'play_count',
        }

        for old_field, new_field in field_mappings.items():
            if old_field in data:
                normalized[new_field] = data[old_field]

        # 处理嵌套的video对象
        if 'video' in data and isinstance(data['video'], dict):
            video = data['video']

            # duration
            if 'duration' in video:
                normalized['duration'] = video['duration']

            # cover
            if 'cover' in video:
                if isinstance(video['cover'], dict):
                    cover_list = video['cover'].get('url_list', [])
                    if cover_list:
                        normalized['cover_url'] = cover_list[0].get('url', '')
                elif isinstance(video['cover'], str):
                    normalized['cover_url'] = video['cover']

            # play_addr
            if 'play_addr' in video:
                if isinstance(video['play_addr'], dict):
                    url_list = video['play_addr'].get('url_list', [])
                    if url_list:
                        normalized['video_url'] = url_list[0].get('url', '')

        # 处理statistics对象
        if 'statistics' in data and isinstance(data['statistics'], dict):
            stats = data['statistics']
            for field in ['diggCount', 'commentCount', 'shareCount', 'playCount']:
                if field in stats:
                    normalized[field] = stats[field]

        # 处理author对象
        if 'author' in data and isinstance(data['author'], dict):
            author = data['author']
            if 'nickname' in author:
                normalized['author_name'] = author['nickname']
            if 'unique_id' in author:
                normalized['author_id'] = author['unique_id']

        # 处理text_extra（hashtags）
        if 'text_extra' in data and isinstance(data['text_extra'], list):
            hashtags = []
            for extra in data['text_extra']:
                if isinstance(extra, dict) and extra.get('type') == 1:
                    hashtag = extra.get('hashtag_name', '')
                    if hashtag:
                        hashtags.append(f"#{hashtag}")

            if hashtags:
                normalized['hashtags'] = hashtags

        return normalized

    def _build_content_from_script_data(self, url: str, soup,
                                     script_data: Dict) -> Dict[str, Any]:
        """
        从script数据构建内容
        """
        # 从HTML提取备用数据
        title_tag = soup.find('title')
        title = title_tag.text if title_tag else "抖音视频"

        # 移除常见后缀
        title = re.sub(r'\s*[-_]\s*抖音\s*$', '', title).strip()

        # 构建完整结果
        return {
            "title": script_data.get('description', title)[:100] or title,
            "url": url,
            "main_content": script_data.get('description', ''),
            "html": str(soup),
            "metadata": {
                "platform": "douyin",
                "author": script_data.get('author_name', ''),
                "author_id": script_data.get('author_id', ''),
                "description": script_data.get('description', ''),
                "likes": script_data.get('likes', 0),
                "comments": script_data.get('comments', 0),
                "shares": script_data.get('shares', 0),
                "play_count": script_data.get('play_count', 0),
                "tags": script_data.get('hashtags', []),
                "hashtags": script_data.get('hashtags', []),
                "publish_date": "",
                "video_id": script_data.get('video_id', ''),
                "duration": script_data.get('duration', 0),
                "duration_formatted": self._format_duration(
                    script_data.get('duration', 0)
                ) if script_data.get('duration') else ""
            },
            "extracted_data": {
                "source": "requests_enhanced",
                "cover_image": script_data.get('cover_url', ''),
                "video_url": script_data.get('video_url', ''),
                "script_data": script_data
            }
        }

    def _format_duration(self, milliseconds: int) -> str:
        """格式化时长"""
        if not milliseconds:
            return "00:00"

        seconds = milliseconds // 1000
        minutes, secs = divmod(seconds, 60)
        return f"{int(minutes):02d}:{int(secs):02d}"

    def _expand_short_url(self, url: str) -> str:
        """展开短链接"""
        if not self.requests_available:
            return url

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }

            response = self.requests.head(url, headers=headers, timeout=5, allow_redirects=True)
            return response.url

        except Exception:
            return url

    def _get_cookies(self) -> str:
        """获取或生成Cookie"""
        # 更新Cookie（如果过期）
        if time.time() - self._last_cookie_update > self._cookie_ttl:
            self._refresh_cookies()

        return self._format_cookies()

    def _format_cookies(self) -> str:
        """格式化Cookie"""
        if not self._cookies:
            # 默认Cookie
            return "ttwid=1%7C2r%7Cw%7Cq%7Cp%7Cz%7Cr%7Cs%7Ct%7Cu%7Cv%7Cw%7Cx%7Cy%7Cz"

        # 构建Cookie字符串
        cookie_parts = []
        for name, value in self._cookies.items():
            cookie_parts.append(f"{name}={value}")

        return "; ".join(cookie_parts)

    def _update_cookies_from_response(self, response):
        """从响应更新Cookie"""
        if 'Set-Cookie' in response.headers:
            set_cookie = response.headers['Set-Cookie']
            # 简单解析Cookie（实际应该更复杂）
            if 'ttwid=' in set_cookie:
                # 提取ttwid值
                match = re.search(r'ttwid=([^;]+)', set_cookie)
                if match:
                    self._cookies['ttwid'] = match.group(1)

    def _refresh_cookies(self):
        """刷新Cookie"""
        # 实际应该从抖音API或网页获取新Cookie
        # 这里简化为更新时间戳
        self._last_cookie_update = time.time()

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
            "title": getattr(result, 'title', '') or "抖音视频",
            "url": url,
            "main_content": markdown,
            "html": getattr(result, 'html', '') if hasattr(result, 'html') else '',
            "metadata": {
                "platform": "douyin",
                "author": self._extract_author(markdown),
                "description": self._extract_description(markdown),
                "tags": self._extract_tags(markdown),
                "publish_date": "",
                "video_id": self._extract_video_id(url)
            }
        }

    def _extract_with_firecrawl(self, url: str) -> Dict[str, Any]:
        """使用Firecrawl提取"""
        try:
            from firecrawl import Firecrawl
            import os
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("FIRECRAWL_API_KEY")
            if not api_key:
                raise ValueError("FIRECRAWL_API_KEY not configured")
            firecrawl = Firecrawl(api_key=api_key)
        except Exception as e:
            raise ValueError(f"Firecrawl not available: {e}")

        scrape_result = firecrawl.scrape(
            url,
            formats={'markdown': True, 'html': True},
            only_main_content=True,
            wait_for=3000,
            headers={
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'
            }
        )

        title = getattr(scrape_result, 'title', '') or "抖音视频"
        markdown = getattr(scrape_result, 'markdown', '')

        return {
            "title": title,
            "url": url,
            "main_content": markdown,
            "html": getattr(scrape_result, 'html', ''),
            "metadata": {
                "platform": "douyin",
                "author": self._extract_author(markdown),
                "description": self._extract_description(markdown),
                "tags": self._extract_tags(markdown)
            }
        }

    def _perform_deep_analysis(self, url: str, basic_content: Dict) -> Optional[Dict]:
        """执行深度分析"""
        video_service = self._get_video_analysis_service()
        if not video_service:
            return None

        try:
            metadata = {
                'title': basic_content.get('title', ''),
                'author': basic_content.get('metadata', {}).get('author', ''),
                'description': basic_content.get('metadata', {}).get('description', '')
            }

            result = video_service.analyze(
                url=url,
                enable_transcription=True,
                enable_keyframes=True,
                num_keyframes=5,
                video_metadata=metadata
            )

            if not result.success:
                return None

            return {
                'transcript': result.transcript or '',
                'transcript_length': len(result.transcript) if result.transcript else 0,
                'summary': result.summary or '',
                'key_points': result.key_points or [],
                'topics': result.topics or [],
                'duration': result.duration,
                'duration_formatted': self._format_duration(result.duration * 1000) if result.duration else '',
                'key_frames': result.key_frames or [],
                'processing_time': result.processing_time
            }

        except Exception as e:
            logger.error(f"Deep video analysis error: {e}")
            return None

    def _extract_author(self, markdown: str) -> str:
        """提取作者名"""
        patterns = [
            r'@([^\s@]+)',
            r'作者[：:]\s*([^\s@]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, markdown[:2000])
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

    def _extract_tags(self, markdown: str) -> list:
        """提取标签"""
        hashtag_pattern = r'#([^\s#]+)'
        tags = re.findall(hashtag_pattern, markdown)
        return tags[:10]

    def _extract_video_id(self, url: str) -> str:
        """从URL提取视频ID"""
        match = re.search(r'/video/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'/note/(\d+)', url)
        if match:
            return match.group(1)
        return ""

    def _build_media_info(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """构建媒体信息"""
        media = {
            "type": "video",
            "cover_image": "",
            "images": [],
            "videos": [],
            "thumbnails": []
        }

        extracted_data = content.get("extracted_data", {})
        if extracted_data:
            cover_url = extracted_data.get("cover_image", "")
            if cover_url:
                media["cover_image"] = cover_url
                media["thumbnails"] = [cover_url]

            video_url = extracted_data.get("video_url", "")
            if video_url:
                media["videos"] = [video_url]

        return media
