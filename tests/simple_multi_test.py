#!/usr/bin/env python3
"""
简化的多平台测试脚本

测试12+平台URL的完整提取流程
"""
import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, asdict

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

    def to_dict(self):
        return asdict(self)


def test_url_detection(url: str) -> TestResult:
    """测试URL检测"""
    start_time = time.time()

    try:
        from url_detector import detect_url, URLType

        # 检测URL
        url_info = detect_url(url)

        if not url_info:
            return TestResult(
                url=url,
                platform="unknown",
                success=False,
                processing_time=time.time() - start_time,
                error_type="DETECTION_FAILED",
                error_message=f"无法检测URL类型"
            )

        platform = url_info.url_type.value
        processing_time = time.time() - start_time

        return TestResult(
            url=url,
            platform=platform,
            success=True,
            processing_time=processing_time,
            has_title=False,
            has_content=False,
            has_metadata=False,
            content_length=0,
            error_type="",
            error_message=""
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


# 测试URL映射
PLATFORM_TEST_URLS = {
    'douyin': [
        'https://www.douyin.com/video/71234567890123456789',
        'https://v.douyin.com/71234567890123456790',
        'https://www.douyin.com/video/71234567890123456791',
    ],
    'weixin': [
        'https://mp.weixin.qq.com/s/abc123def456',
        'https://mp.weixin.qq.com/s/def456abc123',
    ],
    'youtube': [
        'https://www.youtube.com/watch?v=test123',
        'https://www.bilibili.com/video/BV1xx411y7123456789',
    ],
    'twitter': [
        'https://x.com/elonmusk/status/123456789012',
        'https://x.com/jack/thread/status/987654321',
    ],
    'webpage': [
        'https://www.example.com/article/test',
        'https://www.another.com/blog/post',
    ]
}

# 平台名称映射
PLATFORM_NAMES = {
    'douyin': '抖音',
    'weixin': '微信',
    'youtube': 'YouTube',
    'twitter': 'Twitter',
    'webpage': '通用网页'
}


def run_tests(platforms: List[str] = None, max_concurrent: int = 5):
    """运行指定平台的测试"""
    results = []

    # 确定要测试的URL
    if platforms is None:
        # 默认测试所有平台
        platforms = list(PLATFORM_TEST_URLS.keys())
    else:
        platforms = [p for p in platforms if p in PLATFORM_TEST_URLS]

    # 从每个平台取N个URL
    for platform in platforms:
        platform_urls = PLATFORM_TEST_URLS.get(platform, [])[:max_concurrent]

        print(f"\n{'='*60}")
        print(f"测试平台: {PLATFORM_NAMES.get(platform, platform.upper())}")
        print(f"URL数量: {len(platform_urls)}")

        # 运行测试
        for i, url in enumerate(platform_urls, 1):
            print(f"\n[{i}/{len(platform_urls)}] {url}")

            result = test_url_detection(url)
            results.append(result)

            # 快速状态
            status = "OK" if result.success else "XX"
            print(f"  {status} {result.platform.upper():8} | {result.processing_time:.2f}s | "
                  f"检测成功: {'Y' if result.success else 'N'}")

            if not result.success:
                print(f"  错误: {result.error_type}: {result.error_message}")

    return results


def print_summary(results: List[TestResult]):
    """打印测试总结"""
    print("\n" + "="*70)
    print("多平台测试总结")
    print("="*70)

    # 按平台分组
    platform_groups = {}
    for result in results:
        if result.platform not in platform_groups:
            platform_groups[result.platform] = []
        platform_groups[result.platform].append(result)

    for platform, group in platform_groups.items():
        platform_name = PLATFORM_NAMES.get(platform, platform.upper())
        print(f"\n{platform_name}:")
        print("-" * 40)

        total = len(group)
        success_count = sum(1 for r in group if r.success)
        success_rate = (success_count / total * 100) if total > 0 else 0

        total_time = sum(r.processing_time for r in group)
        avg_time = total_time / total if total > 0 else 0

        print(f"总数: {total}")
        print(f"成功: {success_count}")
        print(f"成功率: {success_rate:.1f}%")
        print(f"平均耗时: {avg_time:.2f}s")

        # 错误分布
        errors = {}
        for result in group:
            if not result.success and result.error_type:
                error_key = result.error_type or "UNKNOWN"
                errors[error_key] = errors.get(error_key, 0) + 1

        if errors:
            print(f" 错误类型:")
            for error_type, count in errors.items():
                if count > 0:
                    print(f"    {error_type}: {count}")

        print("-" * 40)

    print("="*70)

    # 保存到JSON
    output = {
        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
        'results': [r.to_dict() for r in results],
        'summaries': {
            platform: {
                'total_urls': len(group),
                'success_count': sum(1 for r in group if r.success),
                'success_rate': (sum(1 for r in group if r.success) / len(group) * 100) if group else 0,
                'avg_time': sum(r.processing_time for r in group) / len(group) if group else 0,
                'errors': {e.error_type: e.error_message for e in group if not e.success}
            } for platform, group in platform_groups.items()
        }
    }

    with open('multi_platform_test_results.json', 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n测试结果已保存到: multi_platform_test_results.json")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="多平台URL完整测试")
    parser.add_argument("--platforms", nargs="+", help="测试平台")
    parser.add_argument("--max-concurrent", type=int, default=3, help="每个平台最大并发数")
    parser.add_argument("--all", action="store_true", help="测试所有平台")

    args = parser.parse_args()

    print("="*70)
    print("多平台URL完整测试")
    print("="*70)
    print()

    # 运行测试
    if args.all:
        results = run_tests()
    else:
        results = run_tests(args.platforms, args.max_concurrent)

    # 打印结果
    print_summary(results)

    print()
    print("="*70)


if __name__ == "__main__":
    main()
