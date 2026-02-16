#!/usr/bin/env python3
"""
真实URL测试用例

使用真实可访问的URL测试内容提取系统
"""
import os
import sys
import json
import time
import unittest
from pathlib import Path
from typing import Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class RealURLTestResults:
    """测试结果收集器"""

    def __init__(self):
        self.results = {
            'douyin': [],
            'weixin': [],
            'youtube': [],
            'twitter': [],
            'webpage': [],
            'other': []
        }

    def add_result(self, platform: str, url: str, success: bool, time: float, error: str = ""):
        """添加测试结果"""
        self.results[platform].append({
            'url': url,
            'success': success,
            'time': time,
            'error': error,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
        })

    def get_summary(self) -> Dict:
        """获取结果摘要"""
        summary = {}
        for platform, results in self.results.items():
            if results:
                success_count = sum(1 for r in results if r['success'])
                total = len(results)
                avg_time = sum(r['time'] for r in results) / total

                summary[platform] = {
                    'total': total,
                    'success': success_count,
                    'success_rate': (success_count / total * 100) if total > 0 else 0,
                    'avg_time': avg_time
                }
        return summary

    def save_to_file(self, filename: str = 'real_url_test_results.json'):
        """保存结果到文件"""
        output = {
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'results': self.results,
            'summary': self.get_summary()
        }

        with open(filename, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"结果已保存到: {filename}")


# 真实测试URL（定期更新）
# 注意：这些URL应该真实存在且可访问
REAL_TEST_URLS = {
    'douyin': [
        # 示例抖音URL（需要替换为真实URL）
        # 'https://www.douyin.com/video/73064882387844925303',
    ],
    'weixin': [
        # 示例微信URL（需要替换为真实URL）
        # 'https://mp.weixin.qq.com/s/anWlLDAqJJYv99o9kY3qQ',
    ],
    'youtube': [
        # YouTube官方示例
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ',  # Rick Roll（经典测试视频）
    ],
    'twitter': [
        # Twitter/X示例
        'https://x.com/elonmusk/status/123456789012',  # 示例
    ],
    'webpage': [
        # 测试用的稳定网站
        'https://example.com',  # RFC 2606示例域名
        'https://httpbin.org/html',  # HTML测试页面
        'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/html/rfc2616/',  # W3C测试页面
        'https://www.wikipedia.org/wiki/HTTP',  # Wikipedia页面
    ]
}


class TestRealURLs:
    """真实URL测试类"""

    def __init__(self):
        self.collector = RealURLTestResults()
        self.max_retries = 3

    def test_single_url(self, platform: str, url: str) -> bool:
        """测试单个URL"""
        print(f"\n测试: {url}")

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                # 导入在这里进行，避免之前的导入错误
                from url_detector import detect_url
                from services.content_service import ContentService

                # 检测URL
                url_info = detect_url(url)
                if not url_info:
                    error = f"无法检测URL类型"
                    self.collector.add_result(platform, url, False, 0, error)
                    print(f"  ❌ {error}")
                    return False

                platform_name = url_info.url_type.value

                # 创建服务并提取
                service = ContentService()
                service.detector = url_detector.URLDetector()
                service.processor_factory = service.processor_factory

                processor = service.processor_factory.get_processor(url_info)
                if not processor:
                    error = f"未找到 {platform_name} 处理器"
                    self.collector.add_result(platform_name, url, False, 0, error)
                    print(f"  ❌ {error}")
                    return False

                # 执行提取
                processed = processor.extract(url_info)
                elapsed_time = time.time() - start_time

                # 检查结果
                success = processed.processing_info.get('success', False)
                errors = processed.processing_info.get('errors', [])

                if success:
                    self.collector.add_result(platform_name, url, True, elapsed_time)
                    print(f"  ✅ 成功 ({elapsed_time:.2f}s)")
                    print(f"     标题: {processed.content.get('title', 'N/A')[:50]}")
                    print(f"     内容长度: {len(processed.content.get('main_content', ''))} 字符")
                    return True
                else:
                    error = '; '.join(errors) if errors else '未知错误'
                    if attempt < self.max_retries - 1:
                        print(f"  ⚠️ 尝试 {attempt + 1}/{self.max_retries} 失败: {error}")
                        time.sleep(2 ** attempt)  # 指数退避
                    else:
                        self.collector.add_result(platform_name, url, False, elapsed_time, error)
                        print(f"  ❌ 失败: {error}")
                        return False

            except Exception as e:
                error = str(e)
                if attempt < self.max_retries - 1:
                    print(f"  ⚠️ 异常 (尝试 {attempt + 1}/{self.max_retries}): {error}")
                    time.sleep(2 ** attempt)
                else:
                    self.collector.add_result(platform, url, False, 0, error)
                    print(f"  ❌ 最终失败: {error}")
                    return False

        return False

    def test_platform(self, platform: str, limit: int = None):
        """测试单个平台"""
        urls = REAL_TEST_URLS.get(platform, [])
        if limit:
            urls = urls[:limit]

        print(f"\n{'='*60}")
        print(f"测试平台: {platform.upper()}")
        print(f"URL数量: {len(urls)}")
        print("="*60)

        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] {url}")
            self.test_single_url(platform, url)

    def test_all_platforms(self, limit: int = None):
        """测试所有平台"""
        print("\n" + "="*60)
        print("真实URL内容提取测试")
        print("="*60)
        print("注意：此测试使用真实URL，可能需要几分钟")
        print("="*60)

        for platform in REAL_TEST_URLS.keys():
            self.test_platform(platform, limit)

        # 打印总结
        self._print_summary()

        # 保存结果
        self.collector.save_to_file()

    def _print_summary(self):
        """打印测试总结"""
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)

        summary = self.collector.get_summary()

        for platform, stats in summary.items():
            print(f"\n{platform.upper()}:")
            print(f"  总数: {stats['total']}")
            print(f"  成功: {stats['success']}")
            print(f"  成功率: {stats['success_rate']:.1f}%")
            print(f"  平均耗时: {stats['avg_time']:.2f}s")

        # 计算总体统计
        total_urls = sum(s['total'] for s in summary.values())
        total_success = sum(s['success'] for s in summary.values())
        overall_rate = (total_success / total_urls * 100) if total_urls > 0 else 0

        print(f"\n总体:")
        print(f"  总URL数: {total_urls}")
        print(f"  总成功数: {total_success}")
        print(f"  总成功率: {overall_rate:.1f}%")
        print("="*60)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="真实URL内容提取测试")
    parser.add_argument("--platforms", nargs="+", help="测试指定平台")
    parser.add_argument("--limit", type=int, default=2, help="每个平台测试URL数量")
    parser.add_argument("--all", action="store_true", help="测试所有平台")

    args = parser.parse_args()

    tester = TestRealURLs()

    if args.all:
        tester.test_all_platforms(limit=args.limit)
    elif args.platforms:
        for platform in args.platforms:
            if platform in REAL_TEST_URLS:
                tester.test_platform(platform, limit=args.limit)
            else:
                print(f"警告: 未知平台 '{platform}'")
    else:
        print("请指定 --platforms 或使用 --all")
        print(f"可用平台: {', '.join(REAL_TEST_URLS.keys())}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
