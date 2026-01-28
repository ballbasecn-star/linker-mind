"""
URL Detector Module - Identifies and classifies different URL types
"""
import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class URLType(Enum):
    """URL type enumeration"""
    WEBPAGE = "webpage"
    TWITTER = "twitter"
    WECHAT = "wechat"
    DOUYIN = "douyin"
    VIDEO = "video"
    UNKNOWN = "unknown"


@dataclass
class URLInfo:
    """Container for URL analysis results"""
    url: str
    url_type: URLType
    platform: str
    extracted_id: Optional[str] = None
    is_video: bool = False


class URLDetector:
    """
    Detects and classifies URLs by type and platform
    """

    # URL pattern regex definitions
    PATTERNS = {
        URLType.TWITTER: [
            r'https?://(www\.)?twitter\.com/[^/]+/status/\d+',
            r'https?://(www\.)?x\.com/[^/]+/status/\d+',
            r'https?://(www\.)?(twitter|x)\.com/.*'
        ],
        URLType.WECHAT: [
            r'https?://mp\.weixin\.qq\.com/.*'
        ],
        URLType.DOUYIN: [
            r'https?://(www\.)?douyin\.com/.*',
            r'https?://v\.douyin\.com/.*'
        ],
        URLType.VIDEO: [
            r'.*\.(mp4|mov|m4v|avi|mkv|webm)(\?.*)?$',
            r'https?://(www\.)?youtube\.com/.*',
            r'https?://(www\.)?youtu\.be/.*',
            r'https?://(www\.)?bilibili\.com/.*',
        ]
    }

    VIDEO_EXTENSIONS = ['.mp4', '.mov', '.m4v', '.avi', '.mkv', '.webm']
    VIDEO_DOMAINS = ['youtube.com', 'youtu.be', 'bilibili.com']

    def __init__(self):
        """Initialize compiled regex patterns for efficiency"""
        self._compiled_patterns = {}
        for url_type, patterns in self.PATTERNS.items():
            self._compiled_patterns[url_type] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]

    def detect(self, url: str) -> URLInfo:
        """
        Detect the type and platform of a given URL

        Args:
            url: The URL string to analyze

        Returns:
            URLInfo object containing detection results
        """
        url = url.strip()

        # Check for video content first (highest priority)
        if self._is_video_url(url):
            return URLInfo(
                url=url,
                url_type=URLType.VIDEO,
                platform=self._extract_video_platform(url),
                is_video=True
            )

        # Check specific platform patterns
        for url_type in [URLType.TWITTER, URLType.WECHAT, URLType.DOUYIN]:
            if self._matches_patterns(url, url_type):
                return URLInfo(
                    url=url,
                    url_type=url_type,
                    platform=url_type.value,
                    extracted_id=self._extract_id(url, url_type)
                )

        # Default to webpage
        return URLInfo(
            url=url,
            url_type=URLType.WEBPAGE,
            platform="web"
        )

    def _is_video_url(self, url: str) -> bool:
        """Check if URL points to video content"""
        url_lower = url.lower()

        # Check file extensions
        for ext in self.VIDEO_EXTENSIONS:
            if ext in url_lower:
                return True

        # Check video platforms
        for domain in self.VIDEO_DOMAINS:
            if domain in url_lower:
                return True

        return False

    def _matches_patterns(self, url: str, url_type: URLType) -> bool:
        """Check if URL matches patterns for a specific type"""
        patterns = self._compiled_patterns.get(url_type, [])
        return any(pattern.match(url) for pattern in patterns)

    def _extract_id(self, url: str, url_type: URLType) -> Optional[str]:
        """Extract platform-specific ID from URL"""
        try:
            if url_type == URLType.TWITTER:
                # Extract tweet ID
                match = re.search(r'/status/(\d+)', url)
                if match:
                    return match.group(1)
                # Extract username
                match = re.search(r'(?:twitter|x)\.com/([^/]+)', url)
                if match:
                    return match.group(1)

            elif url_type == URLType.WECHAT:
                # Extract WeChat article ID
                match = re.search(r's/([A-Za-z0-9_-]+)', url)
                if match:
                    return match.group(1)

            elif url_type == URLType.DOUYIN:
                # Extract Douyin video ID
                match = re.search(r'/video/(\d+)', url)
                if match:
                    return match.group(1)
                match = re.search(r'/note/(\d+)', url)
                if match:
                    return match.group(1)
        except Exception:
            pass

        return None

    def _extract_video_platform(self, url: str) -> str:
        """Extract video platform name from URL"""
        url_lower = url.lower()

        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'youtube'
        elif 'bilibili.com' in url_lower:
            return 'bilibili'
        elif 'douyin.com' in url_lower:
            return 'douyin'

        # Check file extension
        for ext in self.VIDEO_EXTENSIONS:
            if ext in url_lower:
                return 'direct_video'

        return 'unknown'

    def is_valid_url(self, url: str) -> bool:
        """Basic URL validation"""
        if not url or not isinstance(url, str):
            return False

        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            return False

        # Basic structure check
        import validators
        return validators.url(url)

    def batch_detect(self, urls: list[str]) -> list[URLInfo]:
        """
        Detect multiple URLs in batch

        Args:
            urls: List of URL strings to analyze

        Returns:
            List of URLInfo objects
        """
        return [self.detect(url) for url in urls]


# Singleton instance for convenience
_detector_instance = None


def get_detector() -> URLDetector:
    """Get or create the singleton URLDetector instance"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = URLDetector()
    return _detector_instance


def detect_url(url: str) -> URLInfo:
    """
    Convenience function to detect a single URL

    Args:
        url: The URL string to analyze

    Returns:
        URLInfo object containing detection results
    """
    return get_detector().detect(url)
