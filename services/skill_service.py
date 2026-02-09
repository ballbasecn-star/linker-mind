"""
Skill Service

处理技能树和学习的业务逻辑
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from database.db_interface import get_connection

logger = logging.getLogger(__name__)


class SkillLevel:
    """技能等级常量"""
    BEGINNER = 'BEGINNER'
    INTERMEDIATE = 'INTERMEDIATE'
    ADVANCED = 'ADVANCED'
    EXPERT = 'EXPERT'


class SkillService:
    """技能服务 - 处理技能树和学习路径"""

    def __init__(self):
        self.db = get_connection()

    def list_skills(
        self,
        category: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        列出技能

        Args:
            category: 技能分类
            level: 技能等级
            limit: 返回数量

        Returns:
            技能列表
        """
        sql = "SELECT * FROM skills WHERE 1=1"
        params = []

        if category:
            sql += " AND category = ?"
            params.append(category)

        if level:
            sql += " AND level = ?"
            params.append(level)

        sql += " ORDER BY category, skill_name LIMIT ?"
        params.append(limit)

        rows = self.db.fetchall(sql, tuple(params))
        return [self._parse_skill_row(dict(row)) for row in rows]

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """获取单个技能"""
        row = self.db.fetchone(
            "SELECT * FROM skills WHERE id = ?",
            (skill_id,)
        )

        if not row:
            return None

        skill = self._parse_skill_row(dict(row))

        # 获取技能的学习资源
        resources = self.db.fetchall("""
            SELECT sr.*, c.title, c.content_type, c.summary, c.url
            FROM skill_contents sr
            JOIN contents c ON sr.content_id = c.id
            WHERE sr.skill_id = ?
            ORDER BY sr.order_index ASC
        """, (skill_id,))

        skill['resources'] = [dict(row) for row in resources]
        skill['resource_count'] = len(resources)
        skill['completed_count'] = sum(1 for r in resources if r.get('completed'))

        return skill

    def create_skill(
        self,
        skill_name: str,
        category: str = 'General',
        level: str = SkillLevel.BEGINNER,
        parent_ids: Optional[List[str]] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建技能

        Args:
            skill_name: 技能名称
            category: 分类
            level: 等级
            parent_ids: 父技能ID列表
            description: 描述

        Returns:
            创建的技能
        """
        import time
        from database.connection import json_dumps

        skill_id = f"skill_{int(time.time() * 1000)}"

        skill_data = {
            'id': skill_id,
            'skill_name': skill_name,
            'category': category,
            'level': level,
            'parent_ids': json_dumps(parent_ids or []),
            'description': description,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

        self.db.insert('skills', skill_data)

        return self.get_skill(skill_id)

    def update_skill(
        self,
        skill_id: str,
        skill_name: Optional[str] = None,
        category: Optional[str] = None,
        level: Optional[str] = None,
        parent_ids: Optional[List[str]] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """更新技能"""
        updates = {}
        from database.connection import json_dumps

        if skill_name is not None:
            updates['skill_name'] = skill_name

        if category is not None:
            updates['category'] = category

        if level is not None:
            updates['level'] = level

        if parent_ids is not None:
            updates['parent_ids'] = json_dumps(parent_ids)

        if description is not None:
            updates['description'] = description

        if updates:
            updates['updated_at'] = datetime.now().isoformat()

        rows = self.db.update(
            'skills',
            updates,
            'id = ?',
            (skill_id,)
        )

        if rows == 0:
            return None

        return self.get_skill(skill_id)

    def delete_skill(self, skill_id: str) -> bool:
        """删除技能"""
        # 先删除关联的资源
        self.db.delete(
            'skill_contents',
            'skill_id = ?',
            (skill_id,)
        )

        # 删除技能
        rows = self.db.delete(
            'skills',
            'id = ?',
            (skill_id,)
        )

        return rows > 0

    def add_content_to_skill(
        self,
        skill_id: str,
        content_id: str,
        order_index: Optional[int] = None
    ) -> bool:
        """
        添加学习内容到技能

        Args:
            skill_id: 技能ID
            content_id: 内容ID
            order_index: 学习顺序

        Returns:
            是否成功
        """
        # 检查技能是否存在
        skill = self.db.fetchone(
            "SELECT id FROM skills WHERE id = ?",
            (skill_id,)
        )

        if not skill:
            return False

        # 检查是否已添加
        existing = self.db.fetchone(
            "SELECT * FROM skill_contents WHERE skill_id = ? AND content_id = ?",
            (skill_id, content_id)
        )

        if existing:
            return False

        # 获取最大 order_index
        if order_index is None:
            max_order = self.db.fetchval(
                "SELECT MAX(order_index) FROM skill_contents WHERE skill_id = ?",
                (skill_id,)
            ) or 0
            order_index = max_order + 1

        self.db.insert('skill_contents', {
            'skill_id': skill_id,
            'content_id': content_id,
            'order_index': order_index,
            'completed': 0,
            'added_at': datetime.now().isoformat()
        })

        return True

    def remove_content_from_skill(self, skill_id: str, content_id: str) -> bool:
        """从技能中移除内容"""
        rows = self.db.delete(
            'skill_contents',
            'skill_id = ? AND content_id = ?',
            (skill_id, content_id)
        )
        return rows > 0

    def update_resource_progress(
        self,
        skill_id: str,
        content_id: str,
        completed: bool = True
    ) -> bool:
        """更新学习资源的完成状态"""
        from database.connection import json_dumps

        updates = {
            'completed': 1 if completed else 0
        }

        if completed:
            updates['completed_at'] = datetime.now().isoformat()

        rows = self.db.update(
            'skill_contents',
            updates,
            'skill_id = ? AND content_id = ?',
            (skill_id, content_id)
        )

        return rows > 0

    def get_skill_tree(self) -> List[Dict[str, Any]]:
        """
        获取技能树结构

        Returns:
            技能树（根节点列表）
        """
        skills = self.list_skills(limit=1000)

        # 构建技能映射
        skill_map = {}
        for skill in skills:
            skill['children'] = []
            skill_map[skill['id']] = skill

        # 构建树结构
        tree_roots = []
        for skill_id, skill in skill_map.items():
            parent_ids = skill.get('parent_ids', [])
            if not parent_ids:
                tree_roots.append(skill)
            else:
                for parent_id in parent_ids:
                    if parent_id in skill_map:
                        skill_map[parent_id]['children'].append(skill)

        return tree_roots

    def get_learning_path(self, skill_id: str) -> Dict[str, Any]:
        """
        获取学习路径

        Args:
            skill_id: 技能ID

        Returns:
            学习路径数据
        """
        resources = self.db.fetchall("""
            SELECT sr.*, c.title, c.content_type, c.summary, c.url
            FROM skill_contents sr
            JOIN contents c ON sr.content_id = c.id
            WHERE sr.skill_id = ?
            ORDER BY sr.order_index ASC
        """, (skill_id,))

        path = {
            'skill_id': skill_id,
            'total_resources': len(list(resources)),
            'completed_resources': 0,
            'next_up': None,
            'resources': []
        }

        for i, row in enumerate(resources):
            r = dict(row)
            r['order'] = i + 1

            if r.get('completed'):
                path['completed_resources'] += 1
            elif not path['next_up']:
                path['next_up'] = r

            path['resources'].append(r)

        # 计算进度
        if path['total_resources'] > 0:
            path['progress_percent'] = round(
                path['completed_resources'] / path['total_resources'] * 100, 1
            )
        else:
            path['progress_percent'] = 0

        return path

    def get_categories(self) -> List[Dict[str, Any]]:
        """获取所有技能分类"""
        categories = self.db.fetchall("""
            SELECT category, COUNT(*) as count,
                   MIN(level) as min_level, MAX(level) as max_level
            FROM skills
            GROUP BY category
            ORDER BY count DESC
        """)

        return [dict(row) for row in categories]

    def get_stats(self) -> Dict[str, Any]:
        """获取技能统计"""
        total = self.db.fetchval("SELECT COUNT(*) FROM skills") or 0

        # 按分类统计
        by_category = self.db.fetchall("""
            SELECT category, COUNT(*) as count
            FROM skills
            GROUP BY category
            ORDER BY count DESC
        """)

        # 按等级统计
        by_level = self.db.fetchall("""
            SELECT level, COUNT(*) as count
            FROM skills
            GROUP BY level
            ORDER BY
                CASE level
                    WHEN 'BEGINNER' THEN 1
                    WHEN 'INTERMEDIATE' THEN 2
                    WHEN 'ADVANCED' THEN 3
                    WHEN 'EXPERT' THEN 4
                END
        """)

        # 资源统计
        total_resources = self.db.fetchval("SELECT COUNT(*) FROM skill_contents") or 0
        completed_resources = self.db.fetchval("SELECT COUNT(*) FROM skill_contents WHERE completed = 1") or 0

        return {
            'total_skills': total,
            'by_category': {row['category']: row['count'] for row in by_category},
            'by_level': {row['level']: row['count'] for row in by_level},
            'total_resources': total_resources,
            'completed_resources': completed_resources,
            'completion_rate': round(completed_resources / total_resources * 100, 1) if total_resources > 0 else 0
        }

    def _parse_skill_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """解析技能行数据"""
        from database.connection import json_list

        if row.get('parent_ids'):
            row['parent_ids'] = json_list(row['parent_ids'])

        return row


__all__ = ['SkillService', 'SkillLevel']
