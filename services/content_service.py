"""
Content Service

处理内容CRUD和搜索的业务逻辑
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from database.db_interface import get_connection
from url_detector import URLDetector, URLInfo
from content_processor import ProcessorFactory, ProcessedContent
from ai_analyzer import AIAnalyzer

logger = logging.getLogger(__name__)


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
            url: URL地址
            enable_ai: 是否启用AI分析
            deep_analysis: 是否进行深度分析（仅对视频有效，包括转录和关键帧）

        Returns:
            创建的内容或None
        """
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

        # Inject MCP tools for specialized processors
        processor_class_name = processor.__class__.__name__

        # For DouyinProcessor, enable deep_analysis if requested
        if processor_class_name == "DouyinProcessor" and deep_analysis:
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
            use_deep_analysis = deep_analysis and processor_class_name == "DouyinProcessor"
        else:
            use_deep_analysis = False

        if processor_class_name == "TwitterProcessor" and self._web_reader_func:
            processor.web_reader_func = self._web_reader_func
        elif processor_class_name == "DouyinProcessor" and self._web_reader_func:
            processor.set_mcp_tools(self._web_reader_func)

        # 提取内容
        extract_kwargs = {}
        if use_deep_analysis:
            extract_kwargs['deep_analysis'] = True

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
        return self.create(
            source_type=processed.source_type,
            content_type=self._determine_content_type(processed),
            url=url,
            title=processed.content.get('title', ''),
            raw_content=processed.raw_content or processed.content.get('main_content', ''),
            summary=processed.content.get('summary', ''),
            ai_analysis=processed.ai_analysis,
            metadata=processed.processing_info,
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
        from database.connection import json_dumps

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
        from database.connection import json_dumps

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
        from database.connection import json_loads

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
