#!/usr/bin/env python3
"""Simple test of enhanced processors"""
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print(f"Python {sys.version}")

# Test 1: Import test
print("\n=== Test 1: Import Enhanced Processors ===")
try:
    from processors.platforms.douyin_processor import DouyinProcessorEnhanced
    print("  DouyinProcessorEnhanced: OK")
except Exception as e:
    print(f"  DouyinProcessorEnhanced: FAILED - {e}")

try:
    from processors.platforms.weixin_processor import WeixinProcessorEnhanced
    print("  WeixinProcessorEnhanced: OK")
except Exception as e:
    print(f"  WeixinProcessorEnhanced: FAILED - {e}")

# Test 2: Create instances
print("\n=== Test 2: Create Processor Instances ===")
try:
    from processors.platforms.douyin_processor import DouyinProcessorEnhanced
    processor = DouyinProcessorEnhanced()
    print(f"  Douyin instance: {type(processor).__name__}")
except Exception as e:
    print(f"  Douyin instance creation: FAILED - {e}")

try:
    from processors.platforms.weixin_processor import WeixinProcessorEnhanced
    processor = WeixinProcessorEnhanced()
    print(f"  Weixin instance: {type(processor).__name__}")
except Exception as e:
    print(f"  Weixin instance creation: FAILED - {e}")

# Test 3: Test URL detection
print("\n=== Test 3: URL Detection ===")
try:
    from url_detector import detect_url, URLType
    test_urls = [
        "https://www.douyin.com/video/7123456789",
        "https://mp.weixin.qq.com/s/abc123"
    ]

    for url in test_urls:
        url_info = detect_url(url)
        if url_info:
            print(f"  {url}: {url_info.url_type.value}")
except Exception as e:
    print(f"  URL Detection: FAILED - {e}")

# Test 4: Test ProcessorFactory
print("\n=== Test 4: ProcessorFactory ===")
try:
    from processors.content_processor import ProcessorFactory
    factory = ProcessorFactory.create_default()
    print(f"  Factory created: {type(factory).__name__}")
except Exception as e:
    print(f"  ProcessorFactory: FAILED - {e}")

print("\n=== All Tests Complete ===")
