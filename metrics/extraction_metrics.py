#!/usr/bin/env python3
"""
内容提取监控指标收集

记录和分析内容提取系统的性能指标

使用统一数据库接口（PostgreSQL）
"""
import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 使用统一的数据库接口
from database.db_interface import get_connection, DatabaseConnectionInterface


@dataclass
class ExtractionMetric:
    """单次提取指标"""
    timestamp: str
    platform: str
    url_hash: str  # URL的hash，保护隐私
    success: bool
    processing_time: float
    method: str  # 提取方法（firecrawl, beautifulsoup等）
    error_type: str = ""
    error_message: str = ""
    content_length: int = 0
    has_title: bool = False

    def to_dict(self):
        return asdict(self)


class ExtractionMetrics:
    """提取指标收集器（使用PostgreSQL）"""

    def __init__(self):
        """初始化指标收集器"""
        self.conn: Optional[DatabaseConnectionInterface] = None
        self._init_database()

    def _init_database(self):
        """初始化PostgreSQL数据库连接"""
        self.conn = get_connection()
        if not self.conn:
            raise RuntimeError("无法获取数据库连接")

        # 创建metrics表（如果不存在）
        self._create_metrics_table()

    def _create_metrics_table(self):
        """创建metrics表"""
        if not self.conn.table_exists('metrics'):
            create_sql = '''
                CREATE TABLE metrics (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                    platform VARCHAR(50) NOT NULL,
                    url_hash VARCHAR(64) NOT NULL,
                    success BOOLEAN NOT NULL DEFAULT FALSE,
                    processing_time REAL NOT NULL DEFAULT 0,
                    method VARCHAR(50),
                    error_type VARCHAR(100),
                    error_message TEXT,
                    content_length INTEGER DEFAULT 0,
                    has_title BOOLEAN DEFAULT FALSE
                )
            '''
            self.conn.execute(create_sql)

            # 创建索引
            index_sqls = [
                'CREATE INDEX idx_metrics_platform ON metrics(platform)',
                'CREATE INDEX idx_metrics_timestamp ON metrics(timestamp)',
                'CREATE INDEX idx_metrics_success ON metrics(success)',
                'CREATE INDEX idx_metrics_platform_timestamp ON metrics(platform, timestamp)'
            ]
            for index_sql in index_sqls:
                try:
                    self.conn.execute(index_sql)
                except:
                    pass  # 索引可能已存在

    def record_attempt(self, metric: ExtractionMetric):
        """记录一次提取尝试"""
        data = {
            'timestamp': metric.timestamp,
            'platform': metric.platform,
            'url_hash': metric.url_hash,
            'success': metric.success,
            'processing_time': metric.processing_time,
            'method': metric.method,
            'error_type': metric.error_type,
            'error_message': metric.error_message,
            'content_length': metric.content_length,
            'has_title': metric.has_title
        }
        self.conn.insert('metrics', data)

    def get_success_rate(self, platform: str = None, days: int = 7) -> float:
        """获取成功率"""
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        if platform:
            sql = "SELECT COUNT(*) FILTER (WHERE success = true) * 100.0 / COUNT(*) as rate FROM metrics WHERE platform = %s AND timestamp >= %s"
            params = [platform, since_date]
            result = self.conn.fetchone(sql, params)
        else:
            sql = "SELECT COUNT(*) FILTER (WHERE success = true) * 100.0 / COUNT(*) as rate FROM metrics WHERE timestamp >= %s"
            params = [since_date]
            result = self.conn.fetchone(sql, params)

        return result['rate'] if result else 0.0

    def get_avg_time(self, platform: str = None, days: int = 7) -> float:
        """获取平均处理时间"""
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        if platform:
            sql = "SELECT AVG(processing_time) as avg_time FROM metrics WHERE platform = %s AND timestamp >= %s AND success = true"
            params = [platform, since_date]
            result = self.conn.fetchone(sql, params)
        else:
            sql = "SELECT AVG(processing_time) as avg_time FROM metrics WHERE timestamp >= %s AND success = true"
            params = [since_date]
            result = self.conn.fetchone(sql, params)

        return result['avg_time'] if result and result['avg_time'] else 0.0

    def get_error_distribution(self, platform: str = None, days: int = 7) -> Dict[str, int]:
        """获取错误分布"""
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        if platform:
            sql = "SELECT error_type, COUNT(*) as count FROM metrics WHERE platform = %s AND timestamp >= %s AND success = false GROUP BY error_type ORDER BY count DESC"
            params = [platform, since_date]
        else:
            sql = "SELECT error_type, COUNT(*) as count FROM metrics WHERE timestamp >= %s AND success = false GROUP BY error_type ORDER BY count DESC"
            params = [since_date]

        results = self.conn.fetchall(sql, params)
        return {row['error_type'] or 'UNKNOWN': row['count'] for row in results}

    def get_platform_stats(self, platform: str, days: int = 7) -> Dict[str, Any]:
        """获取单个平台的统计信息"""
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        sql = '''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as success_count,
                AVG(CASE WHEN success = true THEN processing_time END) as avg_time,
                SUM(CASE WHEN success = true THEN content_length ELSE 0 END) * 1.0 / SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as avg_content_length
            FROM metrics
            WHERE platform = %s AND timestamp >= %s
        '''
        params = [platform, since_date]
        row = self.conn.fetchone(sql, params)

        return {
            'platform': platform,
            'total': row['total'],
            'success_count': row['success_count'],
            'success_rate': (row['success_count'] / row['total'] * 100) if row['total'] > 0 else 0,
            'avg_time': row['avg_time'] or 0,
            'avg_content_length': row['avg_content_length'] or 0
        }

    def get_daily_stats(self, days: int = 30) -> List[Dict]:
        """获取每日统计"""
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        sql = '''
            SELECT
                DATE(timestamp) as date,
                COUNT(*) as total,
                SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as success_count,
                AVG(processing_time) as avg_time
            FROM metrics
            WHERE timestamp >= %s
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        '''
        results = self.conn.fetchall(sql, [since_date])
        return [dict(row) for row in results]

    def export_to_json(self, filename: str = 'metrics_export.json'):
        """导出指标到JSON文件"""
        sql = 'SELECT * FROM metrics ORDER BY timestamp DESC LIMIT 10000'
        results = self.conn.fetchall(sql)

        # 转换为字典列表
        metrics = []
        for row in results:
            row_dict = dict(row)
            row_dict['success'] = bool(row_dict['success'])
            if 'has_title' in row_dict:
                row_dict['has_title'] = bool(row_dict['has_title'])
            metrics.append(row_dict)

        output = {
            'export_time': datetime.now().isoformat(),
            'total_records': len(metrics),
            'metrics': metrics
        }

        with open(filename, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"✅ 指标已导出到: {filename}")

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None


def get_metrics_collector() -> ExtractionMetrics:
    """获取指标收集器实例（单例）"""
    if not hasattr(get_metrics_collector, '_instance'):
        get_metrics_collector._instance = ExtractionMetrics()
    return get_metrics_collector._instance


# 在应用启动时初始化指标收集器
def init_metrics_collection():
    """初始化指标收集（在应用启动时调用）"""
    try:
        collector = get_metrics_collector()
        print("✅ 监控指标收集器已初始化（使用PostgreSQL）")
        return True
    except Exception as e:
        print(f"⚠️ 指标收集器初始化失败: {e}")
        return False


def main():
    """主函数 - 测试和演示"""
    import argparse

    parser = argparse.ArgumentParser(description="内容提取指标收集")
    parser.add_argument("--action", choices=['record', 'stats', 'export'], help="操作类型")
    parser.add_argument("--platform", help="平台名称")
    parser.add_argument("--days", type=int, default=7, help="统计天数")
    parser.add_argument("--db", help="数据库路径")

    args = parser.parse_args()

    metrics = ExtractionMetrics(args.db) if args.db else ExtractionMetrics()

    try:
        if args.action == 'record':
            # 记录测试指标
            print("记录测试指标...")
            metric = ExtractionMetric(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                platform=args.platform or 'test',
                url_hash='test_url_hash',
                success=True,
                processing_time=1.5,
                method='test_method'
            )
            metrics.record_attempt(metric)
            print("✅ 测试指标已记录")

        elif args.action == 'stats':
            # 显示统计信息
            print("\n" + "="*60)
            print("提取性能统计")
            print("="*60)

            if args.platform:
                # 单平台统计
                stats = metrics.get_platform_stats(args.platform, args.days)
                print(f"\n平台: {stats['platform']}")
                print(f"总提取数: {stats['total']}")
                print(f"成功数: {stats['success_count']}")
                print(f"成功率: {stats['success_rate']:.1f}%")
                print(f"平均时间: {stats['avg_time']:.2f}s")
                print(f"平均内容长度: {stats['avg_content_length']:.0f}字符")

                # 错误分布
                errors = metrics.get_error_distribution(args.platform, args.days)
                if errors:
                    print(f"\n错误分布:")
                    for error_type, count in errors.items():
                        print(f"  {error_type}: {count}")
            else:
                # 总体统计
                overall_rate = metrics.get_success_rate(days=args.days)
                overall_time = metrics.get_avg_time(days=args.days)
                print(f"\n总体成功率 ({args.days}天): {overall_rate:.1f}%")
                print(f"总体平均时间: {overall_time:.2f}s")

                # 各平台统计
                print("\n各平台统计:")
                for platform in ['douyin', 'weixin', 'youtube', 'twitter', 'webpage']:
                    stats = metrics.get_platform_stats(platform, args.days)
                    print(f"  {platform.upper():8} - 成功率: {stats['success_rate']:5.1f}% | "
                          f"平均时间: {stats['avg_time']:5.2f}s")

        elif args.action == 'export':
            # 导出指标
            metrics.export_to_json()

        print("="*60)

    finally:
        metrics.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
