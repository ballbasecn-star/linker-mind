"""
Content Processor Module - Base classes and implementations for content extraction
"""
import os
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List, TYPE_CHECKING
from datetime import datetime
from dotenv import load_dotenv

from firecrawl import Firecrawl
from url_detector import URLInfo, URLType

# Use TYPE_CHECKING to avoid circular import
if TYPE_CHECKING:
    from video_processor import VideoInfoProcessor
    from twitter_processor import TwitterProcessor

load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


@dataclass
class ProcessedContent:
    """Structured output from content processors"""
    id: str
    timestamp: str
    raw_input: str
    source_type: str
    platform: str

    # Content fields
    raw_content: str = ""  # Complete original extracted text
    content: Dict[str, Any] = field(default_factory=dict)
    media: Dict[str, Any] = field(default_factory=dict)
    ai_analysis: Dict[str, Any] = field(default_factory=dict)
    processing_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "raw_input": self.raw_input,
            "source_type": self.source_type,
            "platform": self.platform,
            "raw_content": self.raw_content,
            "content": self.content,
            "media": self.media,
            "ai_analysis": self.ai_analysis,
            "processing_info": self.processing_info
        }


class ContentProcessor(ABC):
    """
    Abstract base class for all content processors
    """

    def __init__(self):
        self._start_time = None

    @abstractmethod
    def can_process(self, url_info: URLInfo) -> bool:
        """Check if this processor can handle the given URL"""
        pass

    @abstractmethod
    def extract(self, url_info: URLInfo) -> ProcessedContent:
        """Extract content from the URL"""
        pass

    def _create_base_content(self, url_info: URLInfo) -> ProcessedContent:
        """Create base ProcessedContent object"""
        return ProcessedContent(
            id=datetime.now().strftime("%Y%m%d%H%M%S"),
            timestamp=datetime.now().isoformat(),
            raw_input=url_info.url,
            source_type=url_info.url_type.value,
            platform=url_info.platform,
            processing_info={
                "method": self.__class__.__name__,
                "processing_time": 0,
                "success": False,
                "errors": []
            }
        )

    def _start_timer(self):
        """Start processing timer"""
        self._start_time = time.time()

    def _end_timer(self) -> float:
        """End processing timer and return elapsed time"""
        if self._start_time is not None:
            return time.time() - self._start_time
        return 0


class WebPageProcessor(ContentProcessor):
    """
    Processor for general web pages using Firecrawl
    """

    def __init__(self):
        super().__init__()
        self.enabled = bool(FIRECRAWL_API_KEY)
        if self.enabled:
            self.firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)
        else:
            self.firecrawl = None

    def can_process(self, url_info: URLInfo) -> bool:
        """Can process any webpage URL"""
        return url_info.url_type == URLType.WEBPAGE

    def extract(self, url_info: URLInfo) -> ProcessedContent:
        """Extract webpage content using Firecrawl"""
        self._start_timer()
        result = self._create_base_content(url_info)

        # Check if Firecrawl is enabled
        if not self.enabled:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": ["FIRECRAWL_API_KEY not configured"]
            })
            raise ValueError("FIRECRAWL_API_KEY not configured. Please set it in .env file or use --no-ai mode.")

        try:
            # Perform scrape with Firecrawl API
            scrape_result = self.firecrawl.scrape(
                url_info.url,
                formats={'markdown': True, 'html': True, 'screenshot': True},
                only_main_content=True,
                wait_for=2000,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
            )

            # Extract content from Firecrawl result
            # The result is a Document object, not a dict
            result.content = {
                "title": getattr(scrape_result, 'title', ''),
                "url": getattr(scrape_result, 'url', url_info.url),
                "main_content": getattr(scrape_result, 'markdown', ''),
                "html": getattr(scrape_result, 'html', ''),
                "metadata": {
                    "description": getattr(scrape_result, 'description', ''),
                    "keywords": getattr(scrape_result, 'keywords', ''),
                    "author": getattr(scrape_result, 'author', ''),
                    "publish_date": getattr(scrape_result, 'publishedDate', ''),
                    "tags": []
                },
                "extracted_data": {}
            }

            # Store the raw result for reference
            result._raw_result = scrape_result

            # Analyze media
            result.media = self._extract_media_info(scrape_result)

            # Update processing info
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": True,
                "errors": []
            })

        except Exception as e:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [str(e)]
            })
            raise

        return result

    def _extract_media_info(self, scrape_result) -> Dict[str, Any]:
        """Extract media information from scrape result"""
        media = {
            "type": "text",
            "images": [],
            "videos": [],
            "screenshots": []
        }

        # Get markdown content
        markdown = getattr(scrape_result, 'markdown', '')
        if markdown:
            import re
            img_pattern = r'!\[.*?\]\((.*?)\)'
            images = re.findall(img_pattern, markdown)
            media["images"] = images[:20]  # Limit to 20 images

        # Check for screenshots from Firecrawl
        screenshot = getattr(scrape_result, 'screenshot', '')
        if screenshot:
            media["screenshots"].append(screenshot)

        # Check for images attribute
        images = getattr(scrape_result, 'images', [])
        if images:
            media["images"].extend(images[:20])

        # Check for videos attribute
        videos = getattr(scrape_result, 'videos', [])
        if videos:
            media["videos"] = videos[:10]

        # Determine media type
        if media["images"]:
            media["type"] = "mixed"
        if media["videos"]:
            media["type"] = "mixed"

        return media


class SocialMediaProcessor(ContentProcessor):
    """
    Processor for social media content (Twitter/X, WeChat, Douyin)
    Uses MCP WebReader tool for content extraction
    """

    def __init__(self):
        super().__init__()
        # MCP tool will be called dynamically via the main context

    def can_process(self, url_info: URLInfo) -> bool:
        """Can process social media URLs"""
        return url_info.url_type in [URLType.TWITTER, URLType.WECHAT, URLType.DOUYIN]

    def extract(self, url_info: URLInfo, web_reader_func=None) -> ProcessedContent:
        """
        Extract social media content using MCP WebReader

        Args:
            url_info: URL information from URLDetector
            web_reader_func: Optional MCP webReader function (injected from main context)

        Returns:
            ProcessedContent with extracted social media data
        """
        self._start_timer()
        result = self._create_base_content(url_info)

        try:
            # Use MCP WebReader if available
            if web_reader_func:
                content = web_reader_func(url_info.url)
                result.content = self._parse_social_media_content(content, url_info)
            else:
                # Fallback: basic extraction without MCP
                result.content = self._extract_basic_social_media(url_info)

            result.media = {
                "type": "mixed",
                "images": result.content.get("media", {}).get("images", []),
                "videos": result.content.get("media", {}).get("videos", []),
                "screenshots": []
            }

            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": True,
                "errors": []
            })

        except Exception as e:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [str(e)]
            })
            raise

        return result

    def _parse_social_media_content(self, content: str, url_info: URLInfo) -> Dict[str, Any]:
        """Parse social media content from WebReader output"""
        return {
            "title": f"{url_info.platform.capitalize()} Content",
            "summary": content[:500] + "..." if len(content) > 500 else content,
            "main_content": content,
            "metadata": {
                "platform": url_info.platform,
                "author": "",
                "publish_date": "",
                "post_id": url_info.extracted_id,
                "url": url_info.url,
                "tags": []
            },
            "extracted_data": {}
        }

    def _extract_basic_social_media(self, url_info: URLInfo) -> Dict[str, Any]:
        """Basic extraction without MCP tool"""
        return {
            "title": f"{url_info.platform.capitalize()} Post",
            "summary": f"Content from {url_info.url}",
            "main_content": f"Social media content from {url_info.platform}",
            "metadata": {
                "platform": url_info.platform,
                "author": "",
                "publish_date": "",
                "post_id": url_info.extracted_id,
                "url": url_info.url,
                "tags": []
            },
            "extracted_data": {}
        }


class VideoProcessor(ContentProcessor):
    """
    Processor for video content using MCP Video Analyzer
    """

    def __init__(self):
        super().__init__()

    def can_process(self, url_info: URLInfo) -> bool:
        """Can process video URLs"""
        return url_info.url_type == URLType.VIDEO

    def extract(self, url_info: URLInfo, video_analyzer_func=None) -> ProcessedContent:
        """
        Extract and analyze video content using MCP Video Analyzer

        Args:
            url_info: URL information from URLDetector
            video_analyzer_func: Optional MCP analyze_video function (injected)

        Returns:
            ProcessedContent with video analysis
        """
        self._start_timer()
        result = self._create_base_content(url_info)

        try:
            # Use MCP Video Analyzer if available
            if video_analyzer_func:
                analysis = video_analyzer_func(url_info.url)
                result.content = self._parse_video_analysis(analysis, url_info)
            else:
                # Fallback: basic video info
                result.content = self._extract_basic_video_info(url_info)

            result.media = {
                "type": "video",
                "images": [],
                "videos": [{"url": url_info.url, "platform": url_info.platform}],
                "screenshots": []
            }

            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": True,
                "errors": []
            })

        except Exception as e:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [str(e)]
            })
            raise

        return result

    def _parse_video_analysis(self, analysis: str, url_info: URLInfo) -> Dict[str, Any]:
        """Parse video analysis output"""
        return {
            "title": f"Video from {url_info.platform}",
            "summary": analysis[:500] + "..." if len(analysis) > 500 else analysis,
            "main_content": analysis,
            "metadata": {
                "platform": url_info.platform,
                "author": "",
                "publish_date": "",
                "duration": "",
                "url": url_info.url,
                "tags": []
            },
            "extracted_data": {"analysis": analysis}
        }

    def _extract_basic_video_info(self, url_info: URLInfo) -> Dict[str, Any]:
        """Basic video info extraction without MCP"""
        return {
            "title": f"Video from {url_info.platform}",
            "summary": f"Video content at {url_info.url}",
            "main_content": f"Video URL: {url_info.url}",
            "metadata": {
                "platform": url_info.platform,
                "author": "",
                "publish_date": "",
                "duration": "",
                "url": url_info.url,
                "tags": []
            },
            "extracted_data": {}
        }


class TextMemoProcessor(ContentProcessor):
    """
    Processor for plain text notes (non-URL input)
    """

    def can_process(self, url_info: URLInfo) -> bool:
        """Can process any input (fallback)"""
        return url_info.url_type == URLType.UNKNOWN

    def extract(self, text: str) -> ProcessedContent:
        """Process plain text input"""
        self._start_timer()
        result = ProcessedContent(
            id=datetime.now().strftime("%Y%m%d%H%M%S"),
            timestamp=datetime.now().isoformat(),
            raw_input=text,
            source_type="memo",
            platform="text",
            content={
                "title": "Text Note",
                "summary": text[:200] + "..." if len(text) > 200 else text,
                "main_content": text,
                "metadata": {
                    "author": "",
                    "publish_date": "",
                    "tags": []
                }
            },
            media={"type": "text", "images": [], "videos": [], "screenshots": []},
            processing_info={
                "method": self.__class__.__name__,
                "processing_time": 0,
                "success": True,
                "errors": []
            }
        )

        result.processing_info["processing_time"] = self._end_timer()
        return result


class ProcessorFactory:
    """
    Factory class to create appropriate processors for different URL types
    """

    def __init__(self):
        self._processors: List[ContentProcessor] = []

    def register_processor(self, processor: ContentProcessor):
        """Register a new processor"""
        self._processors.append(processor)

    def get_processor(self, url_info: URLInfo) -> Optional[ContentProcessor]:
        """Get appropriate processor for the given URL"""
        for processor in self._processors:
            if processor.can_process(url_info):
                return processor

        # Return TextMemoProcessor as fallback
        return TextMemoProcessor()

    @classmethod
    def create_default(cls) -> 'ProcessorFactory':
        """Create factory with default processors"""
        factory = cls()

        try:
            factory.register_processor(WebPageProcessor())
        except ValueError:
            print("Warning: Firecrawl not configured, web page processing disabled")

        # Twitter/X URLs are handled by TwitterProcessor with MCP WebReader
        try:
            from twitter_processor import TwitterProcessor
            factory.register_processor(TwitterProcessor())
            print("✅ TwitterProcessor enabled (MCP WebReader)")
        except ImportError as e:
            print(f"⚠️  TwitterProcessor unavailable: {e}")
            factory.register_processor(SocialMediaProcessor())

        # Try to use VideoInfoProcessor if yt-dlp is available
        try:
            # Lazy import to avoid circular dependency
            from video_processor import VideoInfoProcessor, YTDLP_AVAILABLE
            if YTDLP_AVAILABLE:
                factory.register_processor(VideoInfoProcessor())
                print("✅ VideoInfoProcessor enabled (yt-dlp)")
            else:
                factory.register_processor(VideoProcessor())
                print("⚠️  yt-dlp not installed, using placeholder VideoProcessor")
        except ImportError as e:
            factory.register_processor(VideoProcessor())
            print(f"⚠️  VideoInfoProcessor unavailable: {e}")

        # Try to use DouyinProcessor for Douyin URLs
        try:
            from douyin_processor import DouyinProcessor
            factory.register_processor(DouyinProcessor())
            print("✅ DouyinProcessor enabled")
        except ImportError as e:
            print(f"⚠️  DouyinProcessor unavailable: {e}")

        # Try to use WeixinProcessor for WeChat URLs
        try:
            from weixin_processor import WeixinProcessor
            factory.register_processor(WeixinProcessor())
            print("✅ WeixinProcessor enabled")
        except ImportError as e:
            print(f"⚠️  WeixinProcessor unavailable: {e}")

        # Try to use BookProcessor for EPUB/PDF files
        try:
            from book_processor import BookProcessor
            factory.register_processor(BookProcessor())
            print("✅ BookProcessor enabled (EPUB/PDF)")
        except ImportError as e:
            print(f"⚠️  BookProcessor unavailable: {e}")

        # Try to use AudioProcessor for audio files
        try:
            from audio_processor import AudioProcessor
            factory.register_processor(AudioProcessor())
            print("✅ AudioProcessor enabled (MP3/M4A/etc)")
        except ImportError as e:
            print(f"⚠️  AudioProcessor unavailable: {e}")

        # Try to use OCRProcessor for images
        try:
            from ocr_processor import OCRProcessor
            factory.register_processor(OCRProcessor())
            print("✅ OCRProcessor enabled (Image text extraction)")
        except ImportError as e:
            print(f"⚠️  OCRProcessor unavailable: {e}")

        return factory
