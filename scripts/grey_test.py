#!/usr/bin/env python3
"""
Grey Testing Script for Enhanced Processors

Tests both old and new processors with sample URLs to compare:
- Success rates
- Processing times
- Data completeness
- Error rates
"""
import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class TestResult:
    """Single test result"""
    url: str
    processor: str
    success: bool
    processing_time: float
    has_title: bool
    has_content: bool
    has_metadata: bool
    content_length: int
    error_type: str = ""
    error_message: str = ""


@dataclass
class GreyTestSummary:
    """Summary of grey testing"""
    total_urls: int
    old_success_count: int
    new_success_count: int
    old_avg_time: float
    new_avg_time: float
    old_data_complete: int
    new_data_complete: int
    improvement: Dict[str, Any]


class GreyTester:
    """Grey testing class"""

    def __init__(self):
        self.results: List[TestResult] = []

    def load_sample_urls(self) -> List[str]:
        """Load sample URLs for testing"""
        # Check if sample file exists
        sample_file = project_root / "tests" / "sample_urls.json"

        if sample_file.exists():
            with open(sample_file) as f:
                data = json.load(f)
                return data.get('urls', [])

        # Default sample URLs if no file
        return [
            "https://www.douyin.com/video/71234567890123456789",
            "https://www.douyin.com/video/71234567890123456790",
            "https://mp.weixin.qq.com/s/abc123def456",
            "https://mp.weixin.qq.com/s/def456abc123",
        ]

    def test_old_processor(self, url: str) -> TestResult:
        """Test with old processor"""
        start_time = time.time()

        try:
            from url_detector import detect_url
            from douyin_processor import DouyinProcessor
            from weixin_processor import WeixinProcessor

            url_info = detect_url(url)
            if not url_info:
                return TestResult(
                    url=url,
                    processor="old",
                    success=False,
                    processing_time=time.time() - start_time,
                    has_title=False,
                    has_content=False,
                    has_metadata=False,
                    content_length=0,
                    error_type="detection_failed"
                )

            # Choose processor
            if url_info.url_type.value == "douyin":
                processor = DouyinProcessor()
            elif url_info.url_type.value == "wechat":
                processor = WeixinProcessor()
            else:
                return TestResult(
                    url=url,
                    processor="old",
                    success=False,
                    processing_time=time.time() - start_time,
                    has_title=False,
                    has_content=False,
                    has_metadata=False,
                    content_length=0,
                    error_type="unsupported_type"
                )

            content = processor.extract(url_info)
            elapsed = time.time() - start_time

            return TestResult(
                url=url,
                processor="old",
                success=content.processing_info.get('success', False),
                processing_time=elapsed,
                has_title=bool(content.content.get('title')),
                has_content=bool(content.content.get('main_content')),
                has_metadata=bool(content.content.get('metadata')),
                content_length=len(content.content.get('main_content', '')),
                error_type="",
                error_message=""
            )

        except Exception as e:
            return TestResult(
                url=url,
                processor="old",
                success=False,
                processing_time=time.time() - start_time,
                has_title=False,
                has_content=False,
                has_metadata=False,
                content_length=0,
                error_type=type(e).__name__,
                error_message=str(e)
            )

    def test_new_processor(self, url: str) -> TestResult:
        """Test with enhanced processor"""
        start_time = time.time()

        try:
            from url_detector import detect_url
            from douyin_processor_enhanced import DouyinProcessorEnhanced
            from weixin_processor_enhanced import WeixinProcessorEnhanced

            url_info = detect_url(url)
            if not url_info:
                return TestResult(
                    url=url,
                    processor="enhanced",
                    success=False,
                    processing_time=time.time() - start_time,
                    has_title=False,
                    has_content=False,
                    has_metadata=False,
                    content_length=0,
                    error_type="detection_failed"
                )

            # Choose processor
            if url_info.url_type.value == "douyin":
                processor = DouyinProcessorEnhanced()
            elif url_info.url_type.value == "wechat":
                processor = WeixinProcessorEnhanced()
            else:
                return TestResult(
                    url=url,
                    processor="enhanced",
                    success=False,
                    processing_time=time.time() - start_time,
                    has_title=False,
                    has_content=False,
                    has_metadata=False,
                    content_length=0,
                    error_type="unsupported_type"
                )

            content = processor.extract(url_info)
            elapsed = time.time() - start_time

            return TestResult(
                url=url,
                processor="enhanced",
                success=content.processing_info.get('success', False),
                processing_time=elapsed,
                has_title=bool(content.content.get('title')),
                has_content=bool(content.content.get('main_content')),
                has_metadata=bool(content.content.get('metadata')),
                content_length=len(content.content.get('main_content', '')),
                error_type="",
                error_message=""
            )

        except Exception as e:
            return TestResult(
                url=url,
                processor="enhanced",
                success=False,
                processing_time=time.time() - start_time,
                has_title=False,
                has_content=False,
                has_metadata=False,
                content_length=0,
                error_type=type(e).__name__,
                error_message=str(e)
            )

    def run_grey_test(self, urls: List[str]) -> GreyTestSummary:
        """Run grey test with given URLs"""
        print(f"\n{'='*60}")
        print(f"Grey Testing {len(urls)} URLs")
        print(f"{'='*60}")

        old_results = []
        new_results = []

        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] Testing: {url}")

            # Test old processor
            print("  Testing old processor...")
            old_result = self.test_old_processor(url)
            old_results.append(old_result)
            print(f"    Success: {old_result.success}, Time: {old_result.processing_time:.2f}s")

            # Wait to avoid rate limiting
            time.sleep(2)

            # Test new processor
            print("  Testing enhanced processor...")
            new_result = self.test_new_processor(url)
            new_results.append(new_result)
            print(f"    Success: {new_result.success}, Time: {new_result.processing_time:.2f}s")

        # Calculate summary
        summary = self._calculate_summary(old_results, new_results)
        self._print_summary(summary)

        # Save results
        self._save_results(old_results, new_results)

        return summary

    def _calculate_summary(self, old_results: List[TestResult],
                             new_results: List[TestResult]) -> GreyTestSummary:
        """Calculate test summary"""

        old_success = sum(1 for r in old_results if r.success)
        new_success = sum(1 for r in new_results if r.success)

        old_time = sum(r.processing_time for r in old_results) / len(old_results)
        new_time = sum(r.processing_time for r in new_results) / len(new_results)

        old_complete = sum(1 for r in old_results if r.has_title and r.has_content and r.has_metadata)
        new_complete = sum(1 for r in new_results if r.has_title and r.has_content and r.has_metadata)

        # Calculate improvements
        success_rate_improvement = ((new_success - old_success) / len(old_results)) * 100
        time_improvement = ((old_time - new_time) / old_time) * 100 if old_time > 0 else 0
        completeness_improvement = ((new_complete - old_complete) / len(old_results)) * 100

        return GreyTestSummary(
            total_urls=len(old_results),
            old_success_count=old_success,
            new_success_count=new_success,
            old_avg_time=old_time,
            new_avg_time=new_time,
            old_data_complete=old_complete,
            new_data_complete=new_complete,
            improvement={
                "success_rate": f"{success_rate_improvement:+.1f}%",
                "processing_time": f"{time_improvement:+.1f}%",
                "data_completeness": f"{completeness_improvement:+.1f}%"
            }
        )

    def _print_summary(self, summary: GreyTestSummary):
        """Print test summary"""
        print("\n" + "="*70)
        print("GREY TEST SUMMARY")
        print("="*70)

        print(f"\nTotal URLs tested: {summary.total_urls}")
        print(f"\nSuccess Rate:")
        print(f"  Old Processor: {summary.old_success_count}/{summary.total_urls} ({summary.old_success_count/summary.total_urls*100:.1f}%)")
        print(f"  New Processor: {summary.new_success_count}/{summary.total_urls} ({summary.new_success_count/summary.total_urls*100:.1f}%)")
        print(f"  Improvement: {summary.improvement['success_rate']}")

        print(f"\nProcessing Time:")
        print(f"  Old Processor: {summary.old_avg_time:.2f}s avg")
        print(f"  New Processor: {summary.new_avg_time:.2f}s avg")
        print(f"  Improvement: {summary.improvement['processing_time']}")

        print(f"\nData Completeness:")
        print(f"  Old Processor: {summary.old_data_complete}/{summary.total_urls} ({summary.old_data_complete/summary.total_urls*100:.1f}%)")
        print(f"  New Processor: {summary.new_data_complete}/{summary.total_urls} ({summary.new_data_complete/summary.total_urls*100:.1f}%)")
        print(f"  Improvement: {summary.improvement['data_completeness']}")

        print("="*70)

        # Save summary
        with open(project_root / "grey_test_summary.json", "w") as f:
            json.dump(asdict(summary), f, indent=2)

    def _save_results(self, old_results: List[TestResult], new_results: List[TestResult]):
        """Save detailed results"""
        with open(project_root / "grey_test_results.json", "w") as f:
            json.dump({
                "old_results": [asdict(r) for r in old_results],
                "new_results": [asdict(r) for r in new_results]
            }, f, indent=2)


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Grey testing for enhanced processors")
    parser.add_argument("--urls", nargs="+", help="Specific URLs to test")
    parser.add_argument("--count", type=int, default=10, help="Number of URLs to test")
    parser.add_argument("--old-only", action="store_true", help="Only test old processors")
    parser.add_argument("--new-only", action="store_true", help="Only test enhanced processors")

    args = parser.parse_args()

    tester = GreyTester()

    # Get URLs
    if args.urls:
        urls = args.urls
    else:
        urls = tester.load_sample_urls()[:args.count]

    print(f"Testing {len(urls)} URLs...")

    # Run tests
    if args.old_only:
        # Only test old processors
        old_results = []
        for url in urls:
            result = tester.test_old_processor(url)
            old_results.append(result)
            time.sleep(2)
    elif args.new_only:
        # Only test enhanced processors
        new_results = []
        for url in urls:
            result = tester.test_new_processor(url)
            new_results.append(result)
            time.sleep(2)
    else:
        # Run full grey test
        tester.run_grey_test(urls)


if __name__ == "__main__":
    main()
