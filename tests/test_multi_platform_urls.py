#!/usr/bin/env python3
"""
多平台URL完整测试套件

测试12+平台的内容采集系统，验证：
- URL检测准确率
- 内容提取成功率
- 数据完整性
- 错误处理机制
- 性能指标（处理时间）
"""
import os
import sys
import time
import json
import unittest
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class TestResult:
    """单个测试结果"""
    url: str
    platform: str
    success: bool
    processing_time: float
    has_title: bool = False
    has_content: bool = False
    has_metadata: bool = False
    content_length: int = 0
    error_type: str = ""
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'url': self.url,
            'platform': self.platform,
            'success': self.success,
            'processing_time': round(self.processing_time, 2),
            'has_title': self.has_title,
            'has_content': self.has_content,
            'has_metadata': self.has_metadata,
            'content_length': self.content_length,
            'error_type': self.error_type,
            'error_message': self.error_message
        }


@dataclass
class PlatformTestSummary:
    """平台测试汇总"""
    platform: str
    total_urls: int
    success_count: int
    total_time: float
    avg_time: float
    success_rate: float
    errors: Dict[str, int]  {}  # error_type -> count

    def calculate_metrics(self):
        """计算指标"""
        if self.total_urls > 0:
            self.success_rate = (self.success_count / self.total_urls) * 100
            self.avg_time = self.total_time / self.total_urls
        else:
            self.success_rate = 0
            self.avg_time = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'platform': self.platform,
            'total_urls': self.total_urls,
            'success_count': self.success_count,
            'success_rate': round(self.success_rate, 1),
            'avg_time': round(self.avg_time, 2),
            'errors': self.errors
        }


class MultiPlatformTester:
    """多平台测试器"""

    def __init__(self):
        self.results: List[TestResult] = []
        self.summaries: Dict[str, PlatformTestSummary] = {}

        # 测试URL样本
        self.test_urls = {
            'douyin': [
                'https://www.douyin.com/video/71234567890123456789',
                'https://v.douyin.com/71234567890123456790',
                'https://www.douyin.com/video/71234567890123456791'
            ],
            'weixin': [
                'https://mp.weixin.qq.com/s/abc123def456',
                'https://mp.weixin.qq.com/s/def456abc123',
            ],
            'youtube': [
                'https://www.youtube.com/watch?v=test123',
                'https://www.bilibili.com/video/BV1xx411x7y4123456789',
            ],
            'twitter': [
                'https://x.com/elonmusk/status/123456789012',
            ],
            'webpage': [
                'https://example.com/article/test',
                'https://www.another.com/blog/post',
            ],
            'video': [
                'https://example.com/video/sample.mp4',
            ],
            'pdf': [
                'https://example.com/document.pdf',
            ],
            'image': [
                'https://example.com/image.jpg',
            ],
        }

        # 设置
        self.timeout = 30  # 每个URL的超时时间（秒）
        self.max_concurrent = 5 5  # 并发测试数量

    def test_url(self, url: str) -> TestResult:
        """测试单个URL"""
        start_time = time.time()

        try:
            # 检测URL类型
            from url_detector import detect_url
            url_info = detect_url(url)

            if not url_info:
                return TestResult(
                    url=url,
                    platform="unknown",
                    success=False,
                    processing_time=time.time() - start_time,
                    error_type="DETECTION_FAILED",
                    error_message=f"无法检测URL类型: {url}"
                )

            platform = url_info.url_type.value

            # 获取处理器
            from processors.content_processor import ProcessorFactory
            factory = ProcessorFactory.create_default()
            processor = factory.get_processor(url_info)

            if not processor:
                return TestResult(
                    url=url,
                    platform=platform,
                    success=False,
                    processing_time=time.time() - start_time,
                    error_type="NO_PROCESSOR",
                    error_message=f"没有找到 {platform}平台的处理器"
                )

            # 提取内容
            processed = processor.extract(url_info)

            # 验证结果
            processing_time = time.time() - start_time
            success = processed.processing_info.get('success', False)
            error_type = processed.processing_info.get('errors', [''])[0] if processed.processing_info.get('errors') else ''
            error_message = '; '.join(processed.processing_info.get('errors', [])) if processed.processing_info.get('errors') else ''

            # 检查数据完整性
            content = processed.content
            has_title = bool(content.get('title', ''))
            has_content = bool(content.get('main_content', ''))
            has_metadata = bool(content.get('metadata', {}))
            content_length = len(content.get('main_content', ''))

            return TestResult(
                url=url,
                platform=platform,
                success=success,
                processing_time=processing_time,
                has_title=has_title,
                has_content=has_content,
                has_metadata=has_metadata,
                content_length=content_length,
                error_type=error_type,
                error_message=error_message
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return TestResult(
                url=url,
                platform="unknown",
                success=False,
                processing_time=processing_time,
                error_type=type(e).__name__,
                error_message=str(e)
            )

    def test_platform(self, platform: str, urls: List[str], max_concurrent: int = 5) -> PlatformTestSummary:
        """测试单个平台"""
        print(f"\n{'='*60}")
        print(f"测试平台: {platform.upper()}")
        print(f"{'='*60}")

        # 限制并发数
        results = []

        for i, url in enumerate(urls[:max_concurrent], 1):
            print(f"\n[{i+1}/{min(len(urls), max_concurrent)}] {url}")

            result = self.test_url(url)
            results.append(result)

            # 显示快速结果
            status = "✅" if result.success else "❌"
            print(f"  {status} {result.platform.upper()} | "
                  f"{'Time: {result.processing_time:.1f}s "
                  f"Title: {'Y' if result.has_title else 'N'} "
                  f"Content: {result.content_length} chars")

            if not result.success:
                print(f"  错误: {result.error_type}: {result.error_message}")

        # 计算汇总
        summary = PlatformTestSummary(platform=platform)
        summary.total_urls = len(results)
        summary.success_count = sum(1 for r in results if r.success)
        summary.total_time = sum(r.processing_time for r in results)
        summary.errors = {}

        for result in results:
            if not result.success:
                error_type = result.error_type or "UNKNOWN"
                summary.errors[error_type] = summary.errors.get(error_type, 0) + 1

        summary.calculate_metrics()

        # 保存到汇总
        self.summaries[platform] = summary

        return summary

    def test_all_platforms(self, max_concurrent: int = 5) -> Dict[str, PlatformTestSummary]:
        """测试所有平台"""
        print("\n" + "="*70)
        print("多平台URL测试")
        print("="*70)

        all_summaries = {}

        for platform, urls in self.test_urls.items():
            print(f"\n测试平台: {platform.upper()}")
            summary = self.test_platform(platform, urls, max_concurrent)
            all_summaries[platform] = summary

        # 生成总体报告
        self._print_final_report(all_summaries)

        return all_summaries

    def _print_final_report(self, summaries: Dict[str, PlatformTestSummary]):
        """生成最终报告"""
        print("\n" + "="*70)
        print("测试总结报告")
        print("="*70)

        total_urls = sum(s.total_urls for s in summaries.values())
        total_success = sum(s.success_count for s in summaries.values())
        total_avg_time = sum(s.total_time for s in summaries.values()) / len(summaries)

        print(f"\n总URL数: {total_urls}")
        print(f"成功提取: {total_success}/{total_urls} ({total_success/total_urls*100:.1f}%)")

        print(f"\n各平台详情:")

        for platform, summary in summaries.items():
            print(f"\n{platform.upper()}:")
            print(f"  成功率: {summary.success_rate:.1f}% ({summary.success_count}/{summary.total_urls})")
            print(f"  平均耗时: {summary.avg_time:.1f}s")
            if summary.errors:
                print(f"  错误分布:")
                for error_type, count in summary.errors.items():
                    if count > 0:
                        print(f"    - {error_type}: {count}")

        print("\n" + "="*70)

        # 保存到JSON
        output = {
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'summaries': {
                platform: {
                    'total_urls': s.total_urls,
                    'success_count': s.success_count,
                    'success_rate': s.success_rate,
                    'avg_time': s.avg_time,
                    'errors': s.errors
                } for platform, s in summaries.items()
            }
        }

        with open('multi_platform_test_results.json', 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 测试结果已保存到: multi_platform_test_results.json")

    def run_tests(self, platforms: List[str] = None, max_concurrent: int = 5):
        """运行测试"""
        if platforms is None:
            platforms = list(self.test_urls.keys())

        print(f"\n将测试 {len(platforms)} 个平台: {', '.join(platforms)}")

        summaries = self.test_all_platforms(max_concurrent)

        # 返回结果
        return {
            'success': True,
            'summaries': summaries,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
        }


def main():
    """主函数"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="多平台URL完整测试")
    parser.add_argument("--platforms", nargs="+", help="测试平台 (douyin, weixin, youtube, twitter, webpage, video)")
    parser.add_argument("--max-concurrent", type=int, default=5, help="每个平台的最大并发数")
    parser.add_argument("--all", action="store_true", help="测试所有平台")

    args = parser.parse_args()

    tester = MultiPlatformTester()

    if args.all:
        # 测试所有平台
        result = tester.run_tests()
    elif args.platforms:
        # 测试指定平台
        result = tester.run_tests(platforms=args.platforms, max_concurrent=args.max_concurrent)

        # 打印报告
        if result.get('success'):
            print("\n✅ 测试完成")
        else:
            print(f"\n❌ 测试失败")
            sys.exit(1)


if __name__ == '__main__':
    main()
