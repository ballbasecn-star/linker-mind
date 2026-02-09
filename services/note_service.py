"""
Note Service

处理笔记和渐进式总结的业务逻辑
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from database.db_interface import get_connection

logger = logging.getLogger(__name__)


class NoteType:
    """笔记类型常量"""
    LEARNING = 'learning'
    INSPIRATION = 'inspiration'
    QUOTE = 'quote'
    ACTIONABLE = 'actionable'
    QUESTION = 'question'
    LINKED = 'linked'
    DEEP_DIVE = 'deep_dive'


class SummaryLayer:
    """渐进式总结层次"""
    HIGHLIGHT = 1      # 高亮要点
    BOLDED = 2         # 加粗重点
    SUPERNOTE = 3      # 超级笔记
    OWN_WORDS = 4      # 自己总结
    INSIGHT = 5        # 深度思考


class NoteService:
    """笔记服务 - 处理笔记和渐进式总结"""

    def __init__(self):
        self.db = get_connection()

    def list_notes(
        self,
        content_id: Optional[str] = None,
        node_id: Optional[str] = None,
        note_type: Optional[str] = None,
        summary_layer: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出笔记

        Args:
            content_id: 关联的内容ID
            node_id: 关联的节点ID
            note_type: 笔记类型
            summary_layer: 总结层次
            limit: 返回数量
            offset: 偏移量

        Returns:
            笔记列表
        """
        sql = "SELECT * FROM notes WHERE 1=1"
        params = []

        if content_id:
            sql += " AND content_id = ?"
            params.append(content_id)

        if node_id:
            sql += " AND node_id = ?"
            params.append(node_id)

        if note_type:
            sql += " AND note_type = ?"
            params.append(note_type)

        if summary_layer is not None:
            sql += " AND summary_layer = ?"
            params.append(int(summary_layer))

        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.db.fetchall(sql, tuple(params))
        return [self._parse_note_row(dict(row)) for row in rows]

    def get_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        """获取单个笔记"""
        row = self.db.fetchone(
            "SELECT * FROM notes WHERE id = ?",
            (note_id,)
        )

        if not row:
            return None

        return self._parse_note_row(dict(row))

    def create_note(
        self,
        content: str,
        content_id: Optional[str] = None,
        node_id: Optional[str] = None,
        note_type: str = NoteType.LEARNING,
        summary_layer: int = 0,
        highlights: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        创建笔记

        Args:
            content: 笔记内容
            content_id: 关联的内容ID
            node_id: 关联的节点ID
            note_type: 笔记类型
            summary_layer: 总结层次
            highlights: 高亮列表

        Returns:
            创建的笔记
        """
        import time
        from database.connection import json_dumps

        note_id = f"note_{int(time.time() * 1000)}"

        note_data = {
            'id': note_id,
            'content_id': content_id,
            'note_type': note_type,
            'content': content,
            'summary_layer': summary_layer,
            'highlights': json_dumps(highlights or []),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

        self.db.insert('notes', note_data)

        return self.get_note(note_id)

    def update_note(
        self,
        note_id: str,
        content: Optional[str] = None,
        note_type: Optional[str] = None,
        summary_layer: Optional[int] = None,
        highlights: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """更新笔记"""
        updates = {}
        from database.connection import json_dumps

        if content is not None:
            updates['content'] = content

        if note_type is not None:
            updates['note_type'] = note_type

        if summary_layer is not None:
            updates['summary_layer'] = summary_layer

        if highlights is not None:
            updates['highlights'] = json_dumps(highlights)

        if updates:
            updates['updated_at'] = datetime.now().isoformat()

        rows = self.db.update(
            'notes',
            updates,
            'id = ?',
            (note_id,)
        )

        if rows == 0:
            return None

        return self.get_note(note_id)

    def delete_note(self, note_id: str) -> bool:
        """删除笔记"""
        rows = self.db.delete(
            'notes',
            'id = ?',
            (note_id,)
        )
        return rows > 0

    def get_content_summary(self, content_id: str) -> Dict[str, Any]:
        """
        获取内容的渐进式总结

        Args:
            content_id: 内容ID

        Returns:
            渐进式总结数据
        """
        notes = self.list_notes(
            content_id=content_id,
            limit=1000
        )

        # 按层次分组
        summary = {
            'content_id': content_id,
            'layers': {
                1: [],  # 高亮
                2: [],  # 加粗
                3: [],  # 超级笔记
                4: [],  # 自己总结
                5: []   # 深度思考
            },
            'total_notes': len(notes)
        }

        for note in notes:
            layer = note.get('summary_layer', 0)
            if layer in summary['layers']:
                summary['layers'][layer].append(note)

        return summary

    def add_highlight(
        self,
        content_id: str,
        text: str,
        color: str = 'yellow'
    ) -> Dict[str, Any]:
        """
        添加高亮 (Layer 1)

        Args:
            content_id: 内容ID
            text: 高亮文本
            color: 颜色

        Returns:
            创建的笔记
        """
        return self.create_note(
            content=text,
            content_id=content_id,
            note_type=NoteType.LEARNING,
            summary_layer=SummaryLayer.HIGHLIGHT,
            highlights=[{'text': text, 'color': color}]
        )

    def add_bolded(self, content_id: str, text: str) -> Dict[str, Any]:
        """添加加粗重点 (Layer 2)"""
        return self.create_note(
            content=text,
            content_id=content_id,
            note_type=NoteType.LEARNING,
            summary_layer=SummaryLayer.BOLDED
        )

    def add_supernote(self, content_id: str, text: str) -> Dict[str, Any]:
        """添加超级笔记 (Layer 3)"""
        return self.create_note(
            content=text,
            content_id=content_id,
            note_type=NoteType.LEARNING,
            summary_layer=SummaryLayer.SUPERNOTE
        )

    def add_own_words(self, content_id: str, text: str) -> Dict[str, Any]:
        """添加自己的总结 (Layer 4)"""
        return self.create_note(
            content=text,
            content_id=content_id,
            note_type=NoteType.LEARNING,
            summary_layer=SummaryLayer.OWN_WORDS
        )

    def add_insight(self, content_id: str, text: str) -> Dict[str, Any]:
        """添加深度思考 (Layer 5)"""
        return self.create_note(
            content=text,
            content_id=content_id,
            note_type=NoteType.DEEP_DIVE,
            summary_layer=SummaryLayer.INSIGHT
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取笔记统计"""
        total = self.db.fetchval("SELECT COUNT(*) FROM notes") or 0

        # 按类型统计
        by_type = self.db.fetchall("""
            SELECT note_type, COUNT(*) as count
            FROM notes
            GROUP BY note_type
            ORDER BY count DESC
        """)

        # 按层次统计
        by_layer = self.db.fetchall("""
            SELECT summary_layer, COUNT(*) as count
            FROM notes
            WHERE summary_layer > 0
            GROUP BY summary_layer
            ORDER BY summary_layer
        """)

        return {
            'total': total,
            'by_type': {row['note_type']: row['count'] for row in by_type},
            'by_layer': {row['summary_layer']: row['count'] for row in by_layer}
        }

    def _parse_note_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """解析笔记行数据"""
        from database.connection import json_list

        if row.get('highlights'):
            row['highlights'] = json_list(row['highlights'])

        return row


__all__ = ['NoteService', 'NoteType', 'SummaryLayer']
