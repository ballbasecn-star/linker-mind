"""
Content Service

处理内容CRUD和搜索的业务逻辑
"""
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from database.db_interface import get_connection
from url_detector import URLDetector, URLInfo
from content_processor import ProcessorFactory, ProcessedContent
from ai_analyzer import AIAnalyzer

logger = logging.getLogger(__name__)


def extract_url_from_text(text: str) -> Optional[str]:
    """
    从包含URL的文本中提取出URL

    支持的格式：
    - https://example.com
    - http://example.com
    - 带描述的文本：xxx https://example.com 复制此链接...
    """
    if not text:
        return None

    # 去除首尾空白
    text = text.strip()

    # 直接以http/https开头，说明是纯URL
    if text.startswith('http://') or text.startswith('https://'):
        return text

    # 从文本中提取URL（匹配http或https开头的链接）
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    match = re.search(url_pattern, text)
    if match:
        return match.group(0)

    return None


class ContentService:
    """内容服务 - 处理内容CRUD和搜索"""

    def __init__(self):
        self.db = get_connection()
        self.detector = URLDetector()
        self.processor_factory = ProcessorFactory.create_default()
        self.analyzer = None

        # MCP tool references (injected if available)
        self._web_reader_func = None
        self._video_analyzer_func = None

        # 延迟初始化AI分析器
        try:
            import os
            if os.getenv('DEEPSEEK_API_KEY'):
                self.analyzer = AIAnalyzer()
        except Exception as e:
            logger.warning(f"AI Analyzer not available: {e}")

    def set_mcp_tools(self, web_reader_func=None, video_analyzer_func=None):
        """Set MCP tool functions for enhanced processing"""
        self._web_reader_func = web_reader_func
        self._video_analyzer_func = video_analyzer_func

    def list_contents(
        self,
        content_type: Optional[str] = None,
        source_type: Optional[str] = None,
        tag: Optional[str] = None,
        favorited: Optional[bool] = None,
        archived: bool = False,
        sort_by: str = 'created_at',
        sort_order: str = 'DESC',
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出内容

        Args:
            content_type: 内容类型过滤
            source_type: 来源类型过滤
            tag: 标签过滤
            favorited: 只显示收藏
            archived: 包含归档
            sort_by: 排序字段
            sort_order: 排序方向
            limit: 返回数量
            offset: 偏移量

        Returns:
            内容列表
        """
        sql = "SELECT * FROM contents WHERE 1=1"
        params = []

        if content_type:
            sql += " AND content_type = ?"
            params.append(content_type)

        if source_type:
            sql += " AND source_type = ?"
            params.append(source_type)

        if tag:
            # JSON标签搜索
            tag_pattern = f'%"{tag}"%'
            sql += " AND (tags LIKE ? OR ai_analysis LIKE ?)"
            params.extend([tag_pattern, tag_pattern])

        if favorited:
            sql += " AND favorited = TRUE"

        if not archived:
            sql += " AND archived = FALSE"

        # 排序
        sql += f" ORDER BY {sort_by} {sort_order}"

        # 分页
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.db.fetchall(sql, tuple(params))
        return [self._parse_content_row(dict(row)) for row in rows]

    def get_content(self, content_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个内容

        Args:
            content_id: 内容ID

        Returns:
            内容数据或None
        """
        row = self.db.fetchone(
            "SELECT * FROM contents WHERE id = ?",
            (content_id,)
        )

        if not row:
            return None

        return self._parse_content_row(dict(row))

    def create_from_url(
        self,
        url: str,
        enable_ai: bool = True,
        deep_analysis: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        从URL创建内容

        Args:
            url: URL地址（可以是纯URL或包含URL的文本）
            enable_ai: 是否启用AI分析
            deep_analysis: 是否进行深度分析（仅对视频有效，包括转录和关键帧）

        Returns:
            创建的内容或None
        """
        # 从文本中提取URL（支持用户复制粘贴的包含URL的文本）
        extracted_url = extract_url_from_text(url)
        if extracted_url and extracted_url != url:
            logger.info(f"从文本中提取出URL: {extracted_url}")
            url = extracted_url

        # 检测URL类型
        url_info = self.detector.detect(url)
        if not url_info:
            logger.error(f"Could not detect URL type: {url}")
            return None

        # 获取处理器
        processor = self.processor_factory.get_processor(url_info)
        if not processor:
            logger.error(f"No processor available for URL type: {url_info.url_type.value}")
            return None

        # Debug: 记录使用的处理器
        processor_class_name = processor.__class__.__name__
        logger.info(f"🔍 使用处理器: {processor_class_name} for URL: {url}")

        # 对抖音视频，尝试使用远程服务获取更多信息
        remote_video_info = None
        remote_cookies = None
        if "DouyinProcessor" in processor_class_name:
            try:
                from services.douyin_remote_client import get_douyin_remote_client
                remote_client = get_douyin_remote_client()
                logger.info("尝试从远程服务获取抖音视频信息...")
                remote_result = remote_client.get_video_info(url)
                if remote_result and remote_result.get('success'):
                    remote_video_info = remote_result.get('video_info', {})
                    remote_cookies = remote_result.get('cookies', '')
                    logger.info(f"远程获取成功: {remote_video_info}")

                    # 如果有video_id，尝试调用API获取更完整的信息
                    video_id = remote_video_info.get('video_id') if remote_video_info else None
                    if video_id and remote_cookies:
                        logger.info(f"尝试通过API获取完整视频信息 (video_id: {video_id})...")
                        api_video_info = remote_client.fetch_video_info_from_api(video_id, remote_cookies)
                        if api_video_info and api_video_info.get('title'):
                            logger.info(f"API获取成功: {api_video_info.get('title')[:30]}...")
                            # 合并API返回的更完整信息
                            remote_video_info = {**remote_video_info, **api_video_info}
                        else:
                            logger.warning("API获取视频信息失败或无标题")

            except Exception as e:
                logger.warning(f"远程服务调用失败: {e}")

        # Inject MCP tools for specialized processors

        # For DouyinProcessor (including Enhanced), enable deep_analysis if requested
        if "DouyinProcessor" in processor_class_name and deep_analysis:
            # Check if video analysis service is available
            if hasattr(processor, '_get_video_analysis_service'):
                service = processor._get_video_analysis_service()
                if service:
                    logger.info("Enabling deep video analysis with transcription")
                else:
                    logger.warning("VideoAnalysisService not available, falling back to basic extraction")

        # Check if processor supports deep_analysis parameter
        import inspect
        sig = inspect.signature(processor.extract)
        if 'deep_analysis' in sig.parameters:
            # 现在已解决 cookies 问题，可以启用抖音深度分析
            use_deep_analysis = deep_analysis
            logger.info(f"deep_analysis 参数: {deep_analysis}, 处理器: {processor_class_name}")
            if deep_analysis and "DouyinProcessor" in processor_class_name:
                logger.info("启用抖音视频深度分析（转录 + 关键帧 + LLM分析）")
        else:
            use_deep_analysis = False
            logger.warning(f"处理器 {processor_class_name} 不支持 deep_analysis 参数")

        if processor_class_name == "TwitterProcessor" and self._web_reader_func:
            processor.web_reader_func = self._web_reader_func
        elif "DouyinProcessor" in processor_class_name and self._web_reader_func:
            processor.set_mcp_tools(self._web_reader_func)

        # 提取内容
        extract_kwargs = {}
        if use_deep_analysis:
            extract_kwargs['deep_analysis'] = True
        if remote_video_info:
            extract_kwargs['remote_video_info'] = remote_video_info
            logger.info(f"传递远程视频信息给处理器: {remote_video_info.get('video_id', 'unknown')}")

        processed = processor.extract(url_info, **extract_kwargs)
        if not processed:
            logger.error("Failed to extract content")
            return None

        # AI分析
        if enable_ai and self.analyzer:
            try:
                ai_result = self.analyzer.analyze(processed)
                if ai_result:
                    # Extract just the AI analysis dict, not the whole ProcessedContent object
                    processed.ai_analysis = ai_result.ai_analysis if hasattr(ai_result, 'ai_analysis') else ai_result
            except Exception as e:
                logger.warning(f"AI analysis failed: {e}")

        # 保存到数据库
        # 从 processed.content 中提取深度分析数据
        transcript = processed.content.get('transcript', '')
        transcript_summary = processed.content.get('transcript_summary', '')

        # 将深度分析数据添加到 metadata 中
        metadata = processed.processing_info or {}

        # 从 processed.content 中提取视频数据指标（从远程服务获取）
        video_stats = processed.content.get('video_stats', {})
        if video_stats:
            metadata.update(video_stats)

        if transcript:
            metadata['transcript'] = transcript
        if transcript_summary:
            metadata['transcript_summary'] = transcript_summary

        return self.create(
            source_type=processed.source_type,
            content_type=self._determine_content_type(processed),
            url=url,
            title=processed.content.get('title', ''),
            raw_content=processed.raw_content or processed.content.get('main_content', ''),
            summary=processed.content.get('summary', ''),
            ai_analysis=processed.ai_analysis,
            metadata=metadata,
            media=processed.media
        )

    def create(
        self,
        source_type: str,
        content_type: str,
        url: Optional[str] = None,
        title: str = '',
        raw_content: str = '',
        summary: str = '',
        ai_analysis: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        media: Optional[Dict] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        创建内容

        Args:
            source_type: 来源类型
            content_type: 内容类型
            url: URL地址
            title: 标题
            raw_content: 原始内容
            summary: 摘要
            ai_analysis: AI分析结果
            metadata: 元数据
            media: 媒体信息（图片、视频等）
            tags: 标签列表

        Returns:
            创建的内容
        """
        import time
        from database import json_dumps

        content_id = f"content_{int(time.time() * 1000)}"

        # 从AI分析中提取标签
        if ai_analysis and isinstance(ai_analysis, dict):
            extracted_tags = ai_analysis.get('topics', [])
            if tags:
                extracted_tags.extend(tags)
            tags = extracted_tags

        # Both PostgreSQL JSONB and SQLite TEXT need JSON strings
        # psycopg2 will handle the JSONB conversion from JSON string
        content_data = {
            'id': content_id,
            'source_type': source_type,
            'content_type': content_type,
            'url': url,
            'title': title,
            'raw_content': raw_content,
            'summary': summary,
            'main_content': raw_content[:1000],  # 前1000字符
            'ai_analysis': json_dumps(ai_analysis or {}),
            'metadata': json_dumps(metadata or {}),
            'media': json_dumps(media or {}),
            'tags': json_dumps(tags or []),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'archived': False,
            'favorited': False,
            'reading_progress': 0
        }

        self.db.insert('contents', content_data)

        return self.get_content(content_id)

    def update(
        self,
        content_id: str,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        raw_content: Optional[str] = None,
        tags: Optional[List[str]] = None,
        favorited: Optional[bool] = None,
        archived: Optional[bool] = None,
        reading_progress: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """更新内容"""
        updates = {}
        from database import json_dumps

        if title is not None:
            updates['title'] = title

        if summary is not None:
            updates['summary'] = summary

        if raw_content is not None:
            updates['raw_content'] = raw_content
            updates['main_content'] = raw_content[:1000]

        if tags is not None:
            updates['tags'] = json_dumps(tags)

        if favorited is not None:
            updates['favorited'] = favorited

        if archived is not None:
            updates['archived'] = archived

        if reading_progress is not None:
            updates['reading_progress'] = max(0, min(100, reading_progress))

        if updates:
            updates['updated_at'] = datetime.now().isoformat()

        rows = self.db.update(
            'contents',
            updates,
            'id = ?',
            (content_id,)
        )

        if rows == 0:
            return None

        return self.get_content(content_id)

    def delete(self, content_id: str) -> bool:
        """删除内容"""
        rows = self.db.delete(
            'contents',
            'id = ?',
            (content_id,)
        )
        return rows > 0

    def toggle_favorite(self, content_id: str) -> Optional[Dict[str, Any]]:
        """切换收藏状态"""
        content = self.get_content(content_id)
        if not content:
            return None

        return self.update(
            content_id,
            favorited=not content.get('favorited', False)
        )

    def toggle_archive(self, content_id: str) -> Optional[Dict[str, Any]]:
        """切换归档状态"""
        content = self.get_content(content_id)
        if not content:
            return None

        return self.update(
            content_id,
            archived=not content.get('archived', False)
        )

    def update_reading_progress(
        self,
        content_id: str,
        progress: int
    ) -> Optional[Dict[str, Any]]:
        """
        更新阅读进度

        Args:
            content_id: 内容ID
            progress: 进度 (0-100)

        Returns:
            更新后的内容
        """
        return self.update(content_id, reading_progress=progress)

    def search(
        self,
        query: str,
        content_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        搜索内容

        Args:
            query: 搜索关键词
            content_types: 内容类型过滤
            tags: 标签过滤
            limit: 返回数量

        Returns:
            搜索结果
        """
        search_pattern = f'%{query}%'

        sql = """
            SELECT * FROM contents
            WHERE archived = FALSE
            AND (title LIKE ? OR summary LIKE ? OR raw_content LIKE ?)
        """
        params = [search_pattern, search_pattern, search_pattern]

        if content_types:
            placeholders = ','.join(['?' for _ in content_types])
            sql += f" AND content_type IN ({placeholders})"
            params.extend(content_types)

        if tags:
            for tag in tags:
                tag_pattern = f'%"{tag}"%'
                sql += " AND tags LIKE ?"
                params.append(tag_pattern)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.db.fetchall(sql, tuple(params))
        results = [self._parse_content_row(dict(row)) for row in rows]

        # 计算相关性分数
        for item in results:
            query_lower = query.lower()
            title_lower = (item.get('title') or '').lower()
            summary_lower = (item.get('summary') or '').lower()

            if query_lower in title_lower:
                item['relevance_score'] = 1.0
            elif query_lower in summary_lower:
                item['relevance_score'] = 0.7
            else:
                item['relevance_score'] = 0.5

        # 按相关性排序
        results.sort(key=lambda x: x['relevance_score'], reverse=True)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取内容统计"""
        total = self.db.fetchval("SELECT COUNT(*) FROM contents") or 0
        favorited = self.db.fetchval("SELECT COUNT(*) FROM contents WHERE favorited = TRUE") or 0
        archived = self.db.fetchval("SELECT COUNT(*) FROM contents WHERE archived = TRUE") or 0

        # 按类型统计
        by_type = self.db.fetchall("""
            SELECT content_type, COUNT(*) as count
            FROM contents
            WHERE archived = FALSE
            GROUP BY content_type
            ORDER BY count DESC
        """)

        # 按来源统计
        by_source = self.db.fetchall("""
            SELECT source_type, COUNT(*) as count
            FROM contents
            WHERE archived = FALSE
            GROUP BY source_type
            ORDER BY count DESC
        """)

        return {
            'total': total,
            'favorited': favorited,
            'archived': archived,
            'active': total - archived,
            'by_type': {row['content_type']: row['count'] for row in by_type},
            'by_source': {row['source_type']: row['count'] for row in by_source}
        }

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的内容"""
        return self.list_contents(
            archived=False,
            sort_by='created_at',
            sort_order='DESC',
            limit=limit
        )

    def download_video(self, content_id: str) -> Optional[Dict[str, Any]]:
        """
        下载抖音视频

        Args:
            content_id: 内容ID

        Returns:
            包含下载信息的字典
        """
        content = self.get_content(content_id)
        if not content:
            return None

        if content.get('source_type') != 'douyin':
            return {"success": False, "error": "仅支持抖音视频下载"}

        try:
            from services.douyin_downloader import DouYinDownloader
            from services.douyin_remote_client import get_douyin_remote_client

            # 获取 cookies
            remote_client = get_douyin_remote_client()
            cookies_result = remote_client.get_cookies_only()
            if not cookies_result or not cookies_result.get('success'):
                return {"success": False, "error": "无法获取cookies"}

            cookies = cookies_result.get('cookies', '')
            url = content.get('url', '')

            if not url:
                return {"success": False, "error": "没有视频URL"}

            # 使用下载器获取视频信息
            downloader = DouYinDownloader(cookies=cookies)
            downloader.parse(url)

            video_url = downloader.get_video_url()
            title = downloader.get_title()
            cover_url = downloader.get_cover_url()

            if not video_url:
                return {"success": False, "error": "无法获取视频地址"}

            # 下载视频
            import os
            import requests

            video_dir = os.path.join(os.getcwd(), 'downloads', 'videos')
            os.makedirs(video_dir, exist_ok=True)

            # 清理文件名
            import re
            remove_chars = r"[\/\\\:\*\?\"\<\>\|]"
            clean_title = re.sub(remove_chars, "_", title or f"video_{content_id}")
            filename = f"{clean_title}.mp4"
            filepath = os.path.join(video_dir, filename)

            # 下载
            response = requests.get(video_url, headers=downloader.headers, timeout=120)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)

                logger.info(f"视频下载成功: {filepath}")

                return {
                    "success": True,
                    "filepath": filepath,
                    "filename": filename,
                    "title": title,
                    "cover_url": cover_url,
                    "video_url": video_url
                }
            else:
                return {"success": False, "error": f"下载失败: {response.status_code}"}

        except Exception as e:
            logger.error(f"视频下载失败: {e}")
            return {"success": False, "error": str(e)}

    def _determine_content_type(self, processed: ProcessedContent) -> str:
        """根据处理后的内容确定内容类型"""
        source_type = processed.source_type.lower()

        type_mapping = {
            'article': 'article',
            'blog': 'article',
            'video': 'video',
            'youtube': 'video',
            'bilibili': 'video',
            'twitter': 'tweet',
            'weibo': 'tweet',
            'weixin': 'post',
            'text': 'note',
            'image': 'image',
            'pdf': 'document',
            'book': 'book'
        }

        return type_mapping.get(source_type, 'article')

    def _parse_content_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """解析内容行数据

        Handles both:
        - SQLite: JSON strings that need parsing
        - PostgreSQL JSONB: already parsed as dict/list
        - PostgreSQL: datetime objects need ISO conversion
        """
        from database import json_loads

        # Convert datetime fields to ISO strings for PostgreSQL
        for key in ['created_at', 'updated_at']:
            if key in row and row[key] is not None:
                if isinstance(row[key], datetime):
                    row[key] = row[key].isoformat()

        # Parse tags - could be JSON string (SQLite) or already a list (PostgreSQL)
        if row.get('tags'):
            if isinstance(row['tags'], str):
                row['tags'] = json_loads(row['tags']) or []
            # If already a list, keep as-is

        # Parse ai_analysis - could be JSON string (SQLite) or already a dict (PostgreSQL JSONB)
        if row.get('ai_analysis'):
            if isinstance(row['ai_analysis'], str):
                row['ai_analysis'] = json_loads(row['ai_analysis']) or {}
            # If already a dict, keep as-is

        # Parse metadata - could be JSON string (SQLite) or already a dict (PostgreSQL JSONB)
        if row.get('metadata'):
            if isinstance(row['metadata'], str):
                row['metadata'] = json_loads(row['metadata']) or {}
            # If already a dict, keep as-is

        return row


__all__ = ['ContentService']
