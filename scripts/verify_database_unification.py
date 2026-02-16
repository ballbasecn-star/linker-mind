#!/usr/bin/env python3
"""
数据库统一验证脚本

验证所有模块是否正确使用PostgreSQL数据库接口
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_file_for_sqlite(file_path: Path) -> bool:
    """检查文件是否使用SQLite"""
    try:
        content = file_path.read_text()
        if 'import sqlite' in content.lower():
            return True
        if 'sqlite3.connect' in content:
            return True
        if 'sqlite3.Connection' in content:
            return True
    except:
        return False
    return False


def check_database_usage():
    """检查数据库使用情况"""
    print("="*60)
    print("数据库统一验证")
    print("="*60)

    # 检查所有Python文件
    py_files = list(Path('.').rglob('*.py'))
    py_files.extend(list(Path('.').rglob('**/*.py')))

    sqlite_files = []
    postgres_files = []
    unknown_files = []

    for py_file in py_files:
        # 跳过虚拟环境和node_modules
        if '.venv' in str(py_file) or 'node_modules' in str(py_file):
            continue

        content = py_file.read_text()

        # 检查SQLite使用
        if check_file_for_sqlite(py_file):
            sqlite_files.append(py_file)
        # 检查PostgreSQL使用
        elif 'db_interface' in content or 'get_connection' in content:
            postgres_files.append(py_file)
        else:
            unknown_files.append(py_file)

    # 打印结果
    print(f"\n检查的Python文件数: {len(py_files)}")
    print(f"使用PostgreSQL: {len(postgres_files)}")
    print(f"使用SQLite: {len(sqlite_files)}")

    if sqlite_files:
        print("\n❌ 发现SQLite使用:")
        for f in sqlite_files:
            print(f"  - {f}")

        return False
    else:
        print("\n✅ 无SQLite依赖发现")
        return True


def check_database_interface():
    """检查统一数据库接口"""
    print("\n" + "="*60)
    print("统一接口验证")
    print("="*60)

    try:
        from database.db_interface import get_connection, DatabaseConnectionInterface

        # 测试连接
        print("\n测试数据库连接...")
        db = get_connection()

        if db:
            print(f"✅ 数据库连接成功")
            print(f"   连接类型: {type(db).__name__}")

            # 测试查询
            print("\n测试基本查询...")
            tables = db.get_tables()
            print(f"✅ 表查询成功，找到 {len(tables)} 个表")

            # 关闭连接
            db.close()
            return True
        else:
            print("❌ 数据库连接失败")
            return False

    except Exception as e:
        print(f"❌ 接口测试失败: {e}")
        return False


def check_metrics_module():
    """检查监控模块"""
    print("\n" + "="*60)
    print("监控模块验证")
    print("="*60)

    try:
        from metrics.extraction_metrics import get_metrics_collector, init_metrics_collection

        # 测试初始化
        print("\n测试监控模块初始化...")
        success = init_metrics_collection()

        if success:
            collector = get_metrics_collector()
            print(f"✅ 监控模块初始化成功")

            if collector.conn:
                print(f"✅ 数据库连接类型: {type(collector.conn).__name__}")

                # 测试基本操作
                print("\n测试监控指标收集...")
                test_metric = {
                    'timestamp': '2024-01-01 12:00:00',
                    'platform': 'test',
                    'url_hash': 'test_hash',
                    'success': True,
                    'processing_time': 1.5,
                    'method': 'test_method'
                }

                collector.record_attempt(test_metric)
                print("✅ 测试指标记录成功")

                # 获取统计
                rate = collector.get_success_rate(platform='test', days=7)
                print(f"✅ 成功率查询: {rate}%")

                collector.close()
                return True
            else:
                print("❌ 监控模块无数据库连接")
                return False
        else:
            print("❌ 监控模块初始化失败")
            return False

    except Exception as e:
        print(f"❌ 监控模块测试失败: {e}")
        return False


def main():
    """主函数"""
    print("\n" + "="*60)
    print("PostgreSQL数据库统一验证")
    print("="*60)
    print()

    results = []

    # 1. 检查SQLite使用
    results.append(('SQLite检查', check_database_usage()))

    # 2. 验证统一接口
    results.append(('接口验证', check_database_interface()))

    # 3. 测试监控模块
    results.append(('监控模块', check_metrics_module()))

    # 打印总结
    print("\n" + "="*60)
    print("验证总结")
    print("="*60)

    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} - {name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "="*60)
    if all_passed:
        print("✅ 所有验证通过，数据库统一完成！")
        print("="*60)
        return 0
    else:
        print("❌ 部分验证失败，请检查上述问题")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
