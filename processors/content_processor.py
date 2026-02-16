"""
Content Processor Module - Base classes and implementations for content extraction

迁移说明：已更新为使用统一API客户端
- 支持 Tavily、Firecrawl、Playwright 等多种API
- 优先级：Tavily > Firecrawl > Playwright
"""
import os
import json
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List, TYPE_CHECKING
from datetime import datetime
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 优先使用统一API客户端
try:
    from services.unified_api_client import (
        UnifiedExtractionClient,
        ExtractionAPI,
        get_unified_client
    )
    EXTRACTION_API_AVAILABLE = True
    EXTRACTION_API_DEFAULT = ExtractionAPI.TAVILY
    logger.info("✅ 统一API客户端已加载，优先使用Tavily")
except ImportError:
    EXTRACTION_API_AVAILABLE = False
    logger.warning("⚠️ 统一API客户端不可用，将尝试使用Firecrawl")

# 保持原有导入作为降级方案
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

load_dotenv()


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
    """Abstract base class for all content processors"""

    def __init__(self):
        self._start_time = None

    @abstractmethod
    def can_process(self, url_info) -> bool:
        """Check if this processor can handle the given URL"""
        pass

    @abstractmethod
    def extract(self, url_info) -> ProcessedContent:
        """Extract content from the URL"""
        pass

    def _create_base_content(self, url_info) -> ProcessedContent:
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
    Processor for general web pages using Unified Extraction API

    支持多种API：
    - Tavily（优先）- 更便宜，功能更强
    - Firecrawl（备用）- 原有方案
    - Playwright（降级）- 自托管选项
    """

    def __init__(self):
        super().__init__()

        # 初始化统一API客户端
        self.api_client = None
        self.extraction_method = "unified"

        if EXTRACTION_API_AVAILABLE:
            try:
                self.api_client = get_unified_client()
                available_apis = self.api_client.get_available_apis()
                logger.info(f"✅ 可用的提取API: {available_apis}")
            except Exception as e:
                logger.warning(f"统一API客户端初始化失败: {e}")

        # 如果统一客户端不可用或未配置，尝试降级到Firecrawl
        if not self.api_client or not self.api_client.get_available_apis():
            try:
                from firecrawl import Firecrawl
                self.firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY) if FIRECRAWL_API_KEY else None
                self.extraction_method = "firecrawl"
                logger.info("降级使用Firecrawl API")
            except ImportError:
                logger.error("Firecrawl SDK未安装")
                self.firecrawl = None
        else:
            self.firecrawl = None

    def can_process(self, url_info) -> bool:
        """Can process any webpage URL"""
        return url_info.url_type.value == "webpage"

    def extract(self, url_info) -> ProcessedContent:
        """Extract webpage content using Unified API"""
        self._start_timer()
        result = self._create_base_content(url_info)

        # 优先使用统一API客户端
        if self.api_client and self.api_client.get_available_apis():
            result = self._extract_with_unified_api(url_info, result)
        # 降级到Firecrawl
        elif self.firecrawl:
            result = self._extract_with_firecrawl(url_info, result)
        else:
            # 没有任何可用的API
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": ["没有可用的内容提取API，请配置TAVILY_API_KEY或FIRECRAWL_API_KEY"]
            })

        result.processing_info['processing_time'] = self._end_timer()
        return result

    def _extract_with_unified_api(self, url_info, result: ProcessedContent) -> ProcessedContent:
        """使用统一API客户端提取内容"""
        try:
            scrape_result = self.api_client.scrape_with_priority(
                url_info.url,
                [ExtractionAPI.TAVILY, ExtractionAPI.FIRECRAWL]
            )

            if scrape_result.success:
                result.content = {
                    "title": scrape_result.title,
                    "main_content": scrape_result.content,
                    "metadata": scrape_result.metadata or {}
                }
                result.processing_info.update({
                    "method": f"unified_{scrape_result.api_used}",
                    "success": True,
                    "extraction_api": scrape_result.api_used,
                    "processing_time": self._end_timer()
                })
            else:
                result.processing_info.update({
                    "method": "unified_api_failed",
                    "success": False,
                    "errors": [scrape_result.error]
                })

        except Exception as e:
            result.processing_info.update({
                "method": "unified_api_error",
                "success": False,
                "errors": [str(e)]
            })

        return result

    def _extract_with_firecrawl(self, url_info, result: ProcessedContent) -> ProcessedContent:
        """使用Firecrawl提取内容（降级方案）"""
        try:
            if not self.firecrawl:
                raise ValueError("Firecrawl未配置")

            scrape_result = self.firecrawl.scrape(
                url_info.url,
                formats={'markdown': True, 'html': True},
                only_main_content=True,
                wait_for=2000,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
            )

            result.content = {
                "title": getattr(scrape_result, 'title', ''),
                "main_content": getattr(scrape_result, 'markdown', ''),
                "metadata": {
                    "html": getattr(scrape_result, 'html', '')
                }
            }
            result.processing_info.update({
                "method": "firecrawl",
                "success": True,
                "processing_time": self._end_timer()
            })

        except Exception as e:
            result.processing_info.update({
                "method": "firecrawl_error",
                "success": False,
                "errors": [str(e)]
            })

        return result


class SocialMediaProcessor(ContentProcessor):
    """Processor for social media content"""

    def can_process(self, url_info) -> bool:
        return url_info.url_type.value in ["twitter", "x", "facebook", "instagram"]

    def extract(self, url_info) -> ProcessedContent:
        self._start_timer()
        result = self._create_base_content(url_info)

        # TODO: 实现社交媒体内容提取
        result.processing_info.update({
            "method": "social_media",
            "success": False,
            "errors": ["Social media extraction not implemented yet"]
        })
        result.processing_info['processing_time'] = self._end_timer()

        return result


class VideoProcessor(ContentProcessor):
    """Processor for video content"""

    def can_process(self, url_info) -> bool:
        return url_info.url_type.value in ["video", "youtube", "bilibili", "douyin"]

    def extract(self, url_info) -> ProcessedContent:
        self._start_timer()
        result = self._create_base_content(url_info)

        # TODO: 实现视频内容提取
        result.processing_info.update({
            "method": "video",
            "success": False,
            "errors": ["Video extraction not implemented yet"]
        })
        result.processing_info['processing_time'] = self._end_timer()

        return result


class TextMemoProcessor(ContentProcessor):
    """Processor for text memos/notes"""

    def can_process(self, url_info) -> bool:
        return url_info.url_type.value == "memo"

    def extract(self, url_info) -> ProcessedContent:
        self._start_timer()
        result = self._create_base_content(url_info)

        result.content = {
            "title": url_info.platform or "Memo",
            "main_content": url_info.url
        }
        result.processing_info.update({
            "method": "memo",
            "success": True,
            "processing_time": self._end_timer()
        })

        return result


class ProcessorFactory:
    """Factory for creating content processors"""

    # 导入专门的处理器
    _additional_processors = []

    @classmethod
    def _load_processors(cls):
        """动态加载专用处理器"""
        if not cls._additional_processors:
            try:
                from processors.platforms.douyin_processor import DouyinProcessorEnhanced
                cls._additional_processors.append(DouyinProcessorEnhanced)
            except ImportError as e:
                logger.warning(f"Failed to load DouyinProcessorEnhanced: {e}")

            try:
                from processors.platforms.weixin_processor import WeixinProcessorEnhanced
                cls._additional_processors.append(WeixinProcessorEnhanced)
            except ImportError as e:
                logger.warning(f"Failed to load WeixinProcessorEnhanced: {e}")

            try:
                from processors.platforms.twitter_processor import TwitterProcessor
                cls._additional_processors.append(TwitterProcessor)
            except (ImportError, ValueError) as e:
                logger.warning(f"TwitterProcessor not available: {e}")

        return cls._additional_processors

    _processors = [
        WebPageProcessor,
        SocialMediaProcessor,
        VideoProcessor,
        TextMemoProcessor,
    ]

    @classmethod
    def create_default(cls) -> 'ProcessorFactory':
        """Create default processor factory"""
        # 预加载专用处理器
        cls._load_processors()
        return cls()

    def get_processor(self, url_info) -> Optional[ContentProcessor]:
        """Get appropriate processor for URL"""
        # 先检查专用处理器（优先级更高）
        for processor_class in self._additional_processors:
            try:
                processor = processor_class()
                if processor.can_process(url_info):
                    return processor
            except (ImportError, ValueError) as e:
                logger.warning(f"Cannot instantiate {processor_class.__name__}: {e}")
                continue

        # 再检查通用处理器
        for processor_class in self._processors:
            try:
                processor = processor_class()
                if processor.can_process(url_info):
                    return processor
            except (ImportError, ValueError) as e:
                logger.warning(f"Cannot instantiate {processor_class.__name__}: {e}")
                continue
        return None

    def get_all_processors(self) -> List[ContentProcessor]:
        """Get all available processors"""
        return [processor_class() for processor_class in self._processors + self._additional_processors]
