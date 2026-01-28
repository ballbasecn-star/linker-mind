#!/usr/bin/env python3
"""
Test script for Linker Mind
Tests each URL type from url-test.json and displays extracted content details
"""
import json
import sys
import traceback
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from main import LinkerMind
from url_detector import URLDetector, URLType


def load_test_urls():
    """Load test URLs from url-test.json"""
    with open("url-test.json", "r") as f:
        return json.load(f)


def test_url_detection():
    """Test URL detection for all URLs"""
    print("\n" + "="*60)
    print("TEST 1: URL Detection")
    print("="*60)

    detector = URLDetector()
    test_urls = load_test_urls()
    results = {}

    for name, url in test_urls.items():
        try:
            url_info = detector.detect(url)
            results[name] = {
                "url": url,
                "url_type": url_info.url_type.value,
                "platform": url_info.platform,
                "id": url_info.extracted_id,
                "status": "success"
            }
            print(f"✅ {name}: {url_info.url_type.value} | {url_info.platform}")
        except Exception as e:
            results[name] = {
                "url": url,
                "status": "error",
                "error": str(e)
            }
            print(f"❌ {name}: {e}")

    return results


def print_content_details(content):
    """Print detailed content information"""
    print(f"\n📋 Content Details:")
    print(f"   Title: {content.content.get('title', 'N/A')[:80]}")

    # Print metadata
    metadata = content.content.get('metadata', {})
    if metadata:
        print(f"\n📊 Metadata:")
        if metadata.get('author'):
            print(f"   Author: {metadata['author']}")
        if metadata.get('duration'):
            print(f"   Duration: {metadata['duration']}")
        if metadata.get('view_count'):
            print(f"   Views: {metadata['view_count']:,}")
        if metadata.get('publish_date'):
            print(f"   Published: {metadata['publish_date']}")
        if metadata.get('video_id'):
            print(f"   Video ID: {metadata['video_id']}")

    # Print subtitle info for videos
    if metadata.get('has_subtitles'):
        sub_len = metadata.get('subtitle_length', 0)
        print(f"   📝 Subtitles: {sub_len:,} characters")

    # Print content preview
    main_content = content.content.get('main_content', '')
    summary = content.content.get('summary', '')

    if summary:
        print(f"\n📝 Summary:")
        print(f"   {summary[:200]}{'...' if len(summary) > 200 else ''}")

    # Print media info
    if content.media.get('images'):
        img_count = len(content.media['images'])
        print(f"\n🖼️  Media: {img_count} image(s)")

    if content.media.get('screenshots'):
        screen_count = len(content.media['screenshots'])
        print(f"   📸 {screen_count} screenshot(s)")

    # Print AI analysis if available
    if content.ai_analysis:
        ai = content.ai_analysis
        if ai.get('key_points'):
            print(f"\n💡 Key Points:")
            for point in ai['key_points'][:3]:
                print(f"   • {point}")

        if ai.get('sentiment') and ai.get('sentiment') != 'unknown':
            print(f"\n😊 Sentiment: {ai['sentiment']}")

        if ai.get('topics'):
            topics = ', '.join(ai['topics'][:5])
            print(f"🏷️  Topics: {topics}")


def test_processing(enable_ai=False):
    """Test content processing for all URLs"""
    print("\n" + "="*60)
    print(f"TEST 2: Content Processing (AI={'enabled' if enable_ai else 'disabled'})")
    print("="*60)

    test_urls = load_test_urls()
    results = {}

    # Initialize app
    app = LinkerMind(enable_ai=enable_ai)

    for name, url in test_urls.items():
        print(f"\n{'─'*60}")
        print(f"Testing: {name}")
        print(f"URL: {url}")
        print(f"{'─'*60}")

        try:
            # Process URL
            content = app.process(url)

            if content:
                results[name] = {
                    "url": url,
                    "id": content.id,
                    "source_type": content.source_type,
                    "platform": content.platform,
                    "title": content.content.get("title", ""),
                    "has_content": bool(content.content.get("summary") or content.content.get("text")),
                    "has_media": bool(content.media),
                    "has_ai_analysis": bool(content.ai_analysis),
                    "processing_time": content.processing_info.get("processing_time", 0),
                    "status": "success",
                    "content_details": {
                        "title": content.content.get("title", ""),
                        "summary": content.content.get("summary", "")[:500],
                        "metadata": content.content.get("metadata", {}),
                        "subtitle_text": content.content.get("subtitle_text", "")[:500],
                        "ai_analysis": content.ai_analysis
                    }
                }

                print_content_details(content)
                print(f"\n✅ SUCCESS - {content.source_type} | {content.platform}")
            else:
                results[name] = {
                    "url": url,
                    "status": "failed",
                    "error": "Processing returned None"
                }
                print(f"❌ FAILED - Processing returned None")

        except Exception as e:
            results[name] = {
                "url": url,
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            print(f"❌ ERROR - {e}")

    return results


def print_summary(detection_results, processing_results):
    """Print test summary"""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    print("\n📊 URL Detection Results:")
    for name, result in detection_results.items():
        status = result["status"]
        if status == "success":
            print(f"  ✅ {name}: {result['url_type']} | {result['platform']}")
        else:
            print(f"  ❌ {name}: {result.get('error', 'Unknown error')}")

    print("\n📊 Content Processing Results:")
    success_count = 0
    error_count = 0

    for name, result in processing_results.items():
        status = result["status"]
        if status == "success":
            success_count += 1
            has_ai = "🤖" if result.get("has_ai_analysis") else ""
            time = result.get("processing_time", 0)
            print(f"  ✅ {name}: {result['source_type']} | {result['platform']} | {time:.2f}s {has_ai}")
        else:
            error_count += 1
            error = result.get("error", "Unknown error")
            print(f"  ❌ {name}: {error}")

    print(f"\n📈 Statistics:")
    print(f"  Total: {len(processing_results)}")
    print(f"  ✅ Success: {success_count}")
    print(f"  ❌ Errors: {error_count}")

    # Identify issues
    if error_count > 0:
        print(f"\n🔍 Issues Found:")
        for name, result in processing_results.items():
            if result["status"] != "success":
                error = result.get("error", "Unknown error")
                print(f"  • {name}: {error}")

    return success_count, error_count


if __name__ == "__main__":
    print("\n🧪 Linker Mind Test Suite")
    print("="*60)

    # Test 1: URL Detection
    detection_results = test_url_detection()

    # Test 2: Content Processing (without AI)
    processing_results = test_processing(enable_ai=False)

    # Print summary
    success, errors = print_summary(detection_results, processing_results)

    # Save results
    with open("test_results.json", "w") as f:
        json.dump({
            "detection": detection_results,
            "processing": processing_results
        }, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved to: test_results.json")
    print("="*60)

    sys.exit(0 if errors == 0 else 1)
