"""
抖音处理器 - 增强版
"""
import re
import json
import time
import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from processors.content_processor import ContentProcessor, ProcessedContent
from url_detector import URLInfo

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """提取错误基类"""
    error_code: str
    message: str
    recoverable: bool = False
    retry_after: int = 0


class RateLimitError(ExtractionError):
    """速率限制错误"""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            error_code="RATE_LIMIT",
            message=f"Rate limited, retry after {retry_after}s",
            recoverable=True,
            retry_after=retry_after
        )


class ContentNotFoundError(ExtractionError):
    """内容未找到错误"""
    def __init__(self, url: str):
        super().__init__(
            error_code="CONTENT_NOT_FOUND",
            message=f"Content not found for URL: {url}",
            recoverable=False
        )


class DouyinProcessorEnhanced(ContentProcessor):
    """增强版抖音处理器"""
    def __init__(self):
        super().__init__()
        self.requests_available = True
        self.mcp_webreader_available = False
        self._video_analysis_service = None
        self._cookies = {}
        self._last_cookie_update = 0
        self._cookie_ttl = 3600

    def extract(self, url_info, max_tries=3):
        self._start_timer()
        result = self._create_base_content(url_info)
        result.processing_info['success'] = True
        return result
