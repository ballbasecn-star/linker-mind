#!/usr/bin/env python3
"""
Interactive Test Script for Linker Mind
Provides a user-friendly interface to test URL processing with enhanced console output
"""
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from main import LinkerMind
from url_detector import URLDetector


def print_header(title: str, width: int = 70):
    """Print a formatted header"""
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def print_section(title: str):
    """Print a section header"""
    print(f"\n┌─ {title}")
    print("│")


def print_field(label: str, value: str, indent: int = 0):
    """Print a key-value field with nice formatting"""
    prefix = "│  " + "  " * indent
    # Handle multi-line values
    lines = value.split('\n')
    for i, line in enumerate(lines):
        if i == 0:
            print(f"{prefix}📌 {label}: {line}")
        else:
            print(f"{prefix}   {line}")


def print_metadata(metadata: dict):
    """Print metadata in a formatted way"""
    if not metadata:
        return

    fields = [
        ("平台", metadata.get("platform")),
        ("作者", metadata.get("author") or metadata.get("uploader")),
        ("发布时间", metadata.get("publish_date")),
        ("时长", metadata.get("duration")),
        ("观看数", f"{metadata.get('view_count', 0):,}" if metadata.get('view_count') else None),
        ("视频ID", metadata.get("video_id")),
    ]

    for label, value in fields:
        if value:
            print_field(label, str(value))


def print_content_preview(content: dict, max_length: int = 500):
    """Print content preview with truncation"""
    title = content.get("title", "No Title")
    summary = content.get("summary", "") or content.get("main_content", "")
    subtitle = content.get("subtitle_text", "")

    print_field("标题", title)

    if summary:
        preview = summary[:max_length] + "..." if len(summary) > max_length else summary
        print_field("摘要", preview)

    if subtitle:
        sub_preview = subtitle[:300] + "..." if len(subtitle) > 300 else subtitle
        print_field("字幕预览", sub_preview, indent=1)


def print_media_info(media: dict):
    """Print media information"""
    if not media:
        return

    images = media.get("images", [])
    screenshots = media.get("screenshots", [])

    if images:
        print(f"│  🖼️  图片: {len(images)} 张")

    if screenshots:
        total_size = sum(len(s) for s in screenshots) / 1024
        print(f"│  📸 截图: {len(screenshots)} 张 ({total_size:.0f} KB)")
        print(f"│  └─ 高质量截图已保存到数据文件")


def print_ai_analysis(ai_analysis: dict):
    """Print AI analysis results"""
    if not ai_analysis:
        return

    if ai_analysis.get("key_points"):
        print("\n│  💡 关键点:")
        for i, point in enumerate(ai_analysis["key_points"][:5], 1):
            print(f"│     {i}. {point}")

    if ai_analysis.get("sentiment") and ai_analysis["sentiment"] != "unknown":
        sentiment_map = {
            "positive": "😊 正面",
            "negative": "😞 负面",
            "neutral": "😐 中性"
        }
        sentiment_label = sentiment_map.get(ai_analysis["sentiment"], ai_analysis["sentiment"])
        print(f"\n│  😊 情感: {sentiment_label}")

    if ai_analysis.get("topics"):
        topics_str = ", ".join(ai_analysis["topics"][:8])
        print(f"│  🏷️  话题: {topics_str}")


def print_processing_info(processing_info: dict):
    """Print processing information"""
    if not processing_info:
        return

    success = processing_info.get("success", False)
    time_taken = processing_info.get("processing_time", 0)

    status = "✅ 成功" if success else "❌ 失败"
    print(f"\n│  ⏱️  处理时间: {time_taken:.2f} 秒")
    print(f"│  📊 状态: {status}")

    if processing_info.get("subtitles_fetched"):
        print(f"│  📝 字幕: 已提取")

    if processing_info.get("screenshots_captured"):
        print(f"│  📸 截图: 已捕获")


def display_extracted_content(url: str, enable_ai: bool = False):
    """
    Display extracted content in a user-friendly format

    Args:
        url: URL to process
        enable_ai: Whether to enable AI analysis
    """
    app = LinkerMind(enable_ai=enable_ai)

    print_header("Linker Mind - 内容提取测试")

    # URL Detection
    print_section("URL 检测")
    detector = URLDetector()
    url_info = detector.detect(url)

    print(f"│  🔗 URL: {url[:70]}")
    print(f"│  📋 类型: {url_info.url_type.value.upper()}")
    print(f"│  🌐 平台: {url_info.platform}")
    if url_info.extracted_id:
        print(f"│  🆔 ID: {url_info.extracted_id}")

    # Content Processing
    print_section("内容提取")

    try:
        content = app.process(url)

        if not content:
            print("│  ❌ 提取失败")
            return

        # Display results
        print_section("提取结果")

        print_content_preview(content.content)
        print()

        if content.content.get("metadata"):
            print_section("元数据")
            print_metadata(content.content["metadata"])

        if content.media:
            print_section("媒体")
            print_media_info(content.media)

        if content.ai_analysis and not content.ai_analysis.get("disabled"):
            print_section("AI 分析")
            print_ai_analysis(content.ai_analysis)

        print_section("处理信息")
        print_processing_info(content.processing_info)

        # Final summary
        print("\n" + "=" * 70)
        print(f"  ✅ 提取完成! ID: {content.id}")
        print(f"  💾 数据已保存到: linker_data.json")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"│  ❌ 错误: {e}")
        print("│")


def interactive_mode():
    """Run interactive test mode"""
    print("\n" + "=" * 70)
    print("  🧠 Linker Mind - 交互式测试模式")
    print("=" * 70)
    print("\n命令:")
    print("  <URL>           - 处理 URL 并显示详细信息")
    print("  --ai            - 启用 AI 分析")
    print("  --no-ai         - 禁用 AI 分析")
    print("  --help          - 显示帮助")
    print("  --quit, --exit   - 退出")
    print("=" * 70 + "\n")

    enable_ai = False

    while True:
        try:
            user_input = input("linker-test> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["--quit", "--exit", "quit", "exit", "q"]:
                print("\n👋 再见！\n")
                break

            if user_input.lower() == "--help":
                print("\n📖 使用说明:")
                print("  直接输入 URL 即可提取内容")
                print("  示例: https://www.bilibili.com/video/BV1xx411c7mD")
                print("  输入 --ai 切换 AI 分析状态")
                print()

            if user_input.lower() == "--ai":
                enable_ai = True
                print("✅ AI 分析已启用\n")
                continue

            if user_input.lower() == "--no-ai":
                enable_ai = False
                print("❌ AI 分析已禁用\n")
                continue

            # Process as URL
            if user_input.startswith(("http://", "https://")):
                display_extracted_content(user_input, enable_ai=enable_ai)
            else:
                print("❌ 请输入有效的 URL\n")

        except KeyboardInterrupt:
            print("\n\n👋 中断。使用 --quit 退出。\n")
        except EOFError:
            print("\n👋 再见！\n")
            break
        except Exception as e:
            print(f"❌ 错误: {e}\n")


if __name__ == "__main__":
    # Check if URL is provided as command line argument
    if len(sys.argv) > 1:
        url = sys.argv[1]
        enable_ai = "--ai" in sys.argv or "-ai" in sys.argv
        display_extracted_content(url, enable_ai=enable_ai)
    else:
        # Run interactive mode
        interactive_mode()
