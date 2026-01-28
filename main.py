"""
Linker Mind - Main Entry Point

A multi-modal content extraction and storage system that processes various link types
(webpages, social media, videos) and provides AI-powered analysis.

Usage:
    python main.py
    python main.py --url <URL>
    python main.py --search <query>
    python main.py --stats
"""
import os
import sys
import argparse
from typing import Optional

from url_detector import URLDetector, URLInfo, URLType
from content_processor import ProcessorFactory, ProcessedContent, WebPageProcessor, SocialMediaProcessor, VideoProcessor, TextMemoProcessor
from ai_analyzer import AIAnalyzer, StorageManager

STORAGE_FILE = "linker_data.json"


class LinkerMind:
    """
    Main application class that orchestrates content processing
    """

    def __init__(self, storage_file: str = STORAGE_FILE, enable_ai: bool = True):
        """
        Initialize Linker Mind

        Args:
            storage_file: Path to JSON storage file
            enable_ai: Whether to enable AI analysis
        """
        self.storage_file = storage_file
        self.enable_ai = enable_ai

        # Initialize components
        self.detector = URLDetector()
        self.processor_factory = ProcessorFactory.create_default()
        self.analyzer = AIAnalyzer() if enable_ai else None
        self.storage = StorageManager(storage_file)

        # MCP tool references (injected if available)
        self._web_reader_func = None
        self._video_analyzer_func = None

    def set_mcp_tools(self, web_reader_func=None, video_analyzer_func=None):
        """
        Set MCP tool functions for enhanced processing

        Args:
            web_reader_func: MCP webReader function
            video_analyzer_func: MCP analyze_video function
        """
        self._web_reader_func = web_reader_func
        self._video_analyzer_func = video_analyzer_func

    def process(self, user_input: str) -> Optional[ProcessedContent]:
        """
        Process user input (URL or text)

        Args:
            user_input: URL or text content to process

        Returns:
            ProcessedContent if successful, None otherwise
        """
        print(f"\n{'='*60}")
        print(f"🔍 Processing: {user_input[:80]}...")
        print(f"{'='*60}\n")

        try:
            # Detect input type
            if user_input.startswith(("http://", "https://")):
                url_info = self.detector.detect(user_input)
                print(f"📌 Detected Type: {url_info.url_type.value.upper()}")
                print(f"📌 Platform: {url_info.platform}")

                content = self._process_url(url_info)
            else:
                print(f"📝 Processing as text note...")
                content = self._process_text(user_input)

            if not content:
                print("❌ Processing failed")
                return None

            # Run AI analysis if enabled
            if self.analyzer:
                print(f"\n🤖 Running AI analysis...")
                content = self.analyzer.analyze(content)

            # Save to storage
            self.storage.save(content)

            # Print summary
            self._print_summary(content)

            return content

        except Exception as e:
            print(f"❌ Error during processing: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _process_url(self, url_info: URLInfo) -> Optional[ProcessedContent]:
        """
        Process a URL with the appropriate processor

        Args:
            url_info: URL information from detector

        Returns:
            ProcessedContent if successful
        """
        processor = self.processor_factory.get_processor(url_info)

        print(f"⚙️  Using processor: {processor.__class__.__name__}")

        # Inject MCP tools for specialized processors
        if isinstance(processor, SocialMediaProcessor) and self._web_reader_func:
            return processor.extract(url_info, web_reader_func=self._web_reader_func)
        elif isinstance(processor, VideoProcessor) and self._video_analyzer_func:
            return processor.extract(url_info, video_analyzer_func=self._video_analyzer_func)
        else:
            return processor.extract(url_info)

    def _process_text(self, text: str) -> Optional[ProcessedContent]:
        """
        Process plain text input

        Args:
            text: Text content to process

        Returns:
            ProcessedContent if successful
        """
        processor = TextMemoProcessor()
        return processor.extract(text)

    def _print_summary(self, content: ProcessedContent):
        """Print processing summary"""
        print(f"\n{'='*60}")
        print(f"✅ Processing Complete!")
        print(f"{'='*60}")
        print(f"🆔 ID: {content.id}")
        print(f"📅 Time: {content.timestamp}")
        print(f"📌 Type: {content.source_type} ({content.platform})")

        if content.content.get("title"):
            print(f"📌 Title: {content.content['title']}")

        if content.content.get("summary"):
            summary = content.content["summary"]
            if len(summary) > 200:
                summary = summary[:200] + "..."
            print(f"📝 Summary: {summary}")

        if content.ai_analysis.get("key_points"):
            print(f"\n💡 Key Points:")
            for i, point in enumerate(content.ai_analysis["key_points"][:3], 1):
                print(f"   {i}. {point}")

        if content.ai_analysis.get("topics"):
            topics_str = ", ".join(content.ai_analysis["topics"][:5])
            print(f"\n🏷️  Topics: {topics_str}")

        if content.ai_analysis.get("sentiment"):
            sentiment = content.ai_analysis["sentiment"]
            emoji = {"positive": "😊", "neutral": "😐", "negative": "😟", "unknown": "❓"}
            print(f"😊 Sentiment: {sentiment} {emoji.get(sentiment, '')}")

        proc_time = content.processing_info.get("processing_time", 0)
        if proc_time > 0:
            print(f"\n⏱️  Processing time: {proc_time:.2f}s")

        print(f"{'='*60}\n")

    def search(self, query: str) -> list[dict]:
        """
        Search stored content

        Args:
            query: Search query

        Returns:
            List of matching items
        """
        print(f"\n🔍 Searching for: {query}")
        results = self.storage.search(query)

        print(f"📊 Found {len(results)} result(s)\n")

        for i, item in enumerate(results, 1):
            # Extract title (handle both old and new formats)
            title = item.get("title", "")
            if not title:
                content_val = item.get('content', {})
                if isinstance(content_val, dict):
                    title = content_val.get('title', 'No title')
                else:
                    title = 'No title'

            # Extract summary (handle both old and new formats)
            summary = ""
            content_val = item.get('content', {})
            if isinstance(content_val, dict):
                summary = content_val.get('summary', '')[:100]
            else:
                summary = str(content_val)[:100]

            print(f"{i}. [{item.get('id')}] {title}")
            print(f"   Type: {item.get('source_type')} | Platform: {item.get('platform', 'unknown')}")
            if summary:
                print(f"   {summary}...")
            print()

        return results

    def show_stats(self):
        """Display storage statistics"""
        stats = self.storage.get_stats()

        print(f"\n{'='*60}")
        print(f"📊 Linker Mind Statistics")
        print(f"{'='*60}")
        print(f"📁 Total Items: {stats['total_items']}")
        print(f"\n📊 By Type:")
        for type_name, count in stats['by_type'].items():
            print(f"   {type_name}: {count}")

        print(f"\n🌐 By Platform:")
        for platform, count in stats['by_platform'].items():
            print(f"   {platform}: {count}")

        print(f"\n🖼️  With Media: {stats['with_media']}")
        print(f"⏱️  Avg Processing Time: {stats['avg_processing_time']}s")
        print(f"{'='*60}\n")

    def interactive_mode(self):
        """Run in interactive CLI mode"""
        print(f"\n{'='*60}")
        print(f"🧠 Linker Mind - Interactive Mode")
        print(f"{'='*60}")
        print(f"Commands:")
        print(f"  <URL or text>  - Process content")
        print(f"  /search <query> - Search stored content")
        print(f"  /stats          - Show statistics")
        print(f"  /help           - Show help")
        print(f"  /quit or /exit  - Exit")
        print(f"{'='*60}\n")

        while True:
            try:
                user_input = input("linker> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["/quit", "/exit", "quit", "exit"]:
                    print("👋 Goodbye!")
                    break

                if user_input.lower() == "/help":
                    self._show_help()
                    continue

                if user_input.lower() == "/stats":
                    self.show_stats()
                    continue

                if user_input.lower().startswith("/search "):
                    query = user_input[8:].strip()
                    if query:
                        self.search(query)
                    continue

                # Process as URL or text
                self.process(user_input)

            except KeyboardInterrupt:
                print(f"\n\n👋 Interrupted. Use /quit to exit.")
            except EOFError:
                print(f"\n👋 Goodbye!")
                break

    @staticmethod
    def _show_help():
        """Display help information"""
        print(f"\n{'='*60}")
        print(f"📖 Linker Mind Help")
        print(f"{'='*60}")
        print(f"\n🌐 Supported URL Types:")
        print(f"   • Web pages        - https://example.com")
        print(f"   • Twitter/X        - https://twitter.com/user/status/123")
        print(f"   • WeChat Articles  - https://mp.weixin.qq.com/s/...")
        print(f"   • Douyin           - https://www.douyin.com/video/...")
        print(f"   • YouTube          - https://youtube.com/watch?v=...")
        print(f"   • Bilibili         - https://bilibili.com/video/...")
        print(f"   • Direct Videos    - https://example.com/video.mp4")
        print(f"\n📝 Text Notes:")
        print(f"   Simply type any text to save as a note")
        print(f"\n💾 Data Storage:")
        print(f"   All content is saved to: {STORAGE_FILE}")
        print(f"{'='*60}\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Linker Mind - Multi-modal content extraction and storage system"
    )
    parser.add_argument(
        "--url", "-u",
        help="URL to process"
    )
    parser.add_argument(
        "--text", "-t",
        help="Text content to process"
    )
    parser.add_argument(
        "--search", "-s",
        help="Search stored content"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show storage statistics"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Disable AI analysis"
    )

    args = parser.parse_args()

    # Initialize application
    app = LinkerMind(enable_ai=not args.no_ai)

    # Route to appropriate command
    if args.interactive:
        app.interactive_mode()

    elif args.stats:
        app.show_stats()

    elif args.search:
        app.search(args.search)

    elif args.url:
        app.process(args.url)

    elif args.text:
        app.process(args.text)

    else:
        # Default: interactive mode
        app.interactive_mode()


if __name__ == "__main__":
    main()
