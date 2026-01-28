"""
Video Processor Module - Extract video information using yt-dlp

Supports: YouTube, Bilibili, and 1000+ other video platforms
"""
import os
import re
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import timedelta

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

from url_detector import URLInfo, URLType
from content_processor import ContentProcessor, ProcessedContent


@dataclass
class VideoInfo:
    """Container for video metadata"""
    id: str
    title: str
    description: str
    uploader: str
    uploader_id: str
    duration: int  # seconds
    view_count: int
    upload_date: str  # YYYYMMDD
    thumbnail: str
    tags: List[str]
    categories: List[str]
    webpage_url: str
    original_url: str
    platform: str
    subtitles: List[str]  # subtitle URLs
    extractor: str  # which yt-dlp extractor was used
    formatted_duration: str  # human readable duration


class VideoInfoProcessor(ContentProcessor):
    """
    Extract video metadata using yt-dlp

    Supports 1000+ websites including:
    - YouTube (youtube.com, youtu.be)
    - Bilibili (bilibili.com)
    - Vimeo
    - Twitter/X videos
    - And many more...
    """

    # yt-dlp configuration
    YTDLP_OPTS = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',  # Get metadata without format checking
        'ignoreerrors': True,
        'nocheckcertificate': True,
        'socket_timeout': 30,
        # Optional: Add cookie support for YouTube
        # 'cookiesfrombrowser': ('chrome',),  # Uncomment to use browser cookies
    }

    def __init__(self):
        super().__init__()
        if not YTDLP_AVAILABLE:
            raise ImportError(
                "yt-dlp is not installed. Install it with: pip install yt-dlp"
            )

    def can_process(self, url_info: URLInfo) -> bool:
        """Can process video URLs"""
        return url_info.url_type == URLType.VIDEO

    def extract(self, url_info: URLInfo, fetch_subtitles: bool = False) -> ProcessedContent:
        """
        Extract video information using yt-dlp

        Args:
            url_info: URL information from URLDetector
            fetch_subtitles: Whether to fetch subtitles/captions if available

        Returns:
            ProcessedContent with video metadata
        """
        self._start_timer()
        result = self._create_base_content(url_info)

        try:
            # Extract video info
            video_info = self._extract_video_info(url_info.url, fetch_subtitles)

            # Build content structure
            result.content = {
                "title": video_info.title,
                "url": video_info.webpage_url,
                "main_content": self._build_main_content(video_info),
                "summary": self._generate_summary(video_info),
                "metadata": {
                    "platform": video_info.platform,
                    "author": video_info.uploader,
                    "uploader_id": video_info.uploader_id,
                    "publish_date": self._format_date(video_info.upload_date),
                    "duration": video_info.formatted_duration,
                    "duration_seconds": video_info.duration,
                    "view_count": video_info.view_count,
                    "tags": video_info.tags,
                    "categories": video_info.categories,
                    "video_id": video_info.id,
                    "thumbnail": video_info.thumbnail,
                    "extractor": video_info.extractor
                }
            }

            # Extract subtitle text if available
            subtitle_text = ""
            if fetch_subtitles and video_info.subtitles:
                subtitle_text = self._fetch_subtitles(video_info.subtitles[:1])  # Only first subtitle
                if subtitle_text:
                    result.content["subtitle_text"] = subtitle_text
                    result.content["main_content"] += f"\n\n## Subtitles/Transcript\n\n{subtitle_text}"

            # Media info
            result.media = {
                "type": "video",
                "images": [video_info.thumbnail] if video_info.thumbnail else [],
                "videos": [{
                    "url": video_info.webpage_url,
                    "platform": video_info.platform,
                    "id": video_info.id,
                    "duration": video_info.formatted_duration
                }],
                "screenshots": []
            }

            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": True,
                "errors": [],
                "extractor_used": video_info.extractor
            })

        except Exception as e:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [str(e)]
            })
            raise

        return result

    def _extract_video_info(self, url: str, fetch_subtitles: bool) -> VideoInfo:
        """Extract video information using yt-dlp"""
        opts = self.YTDLP_OPTS.copy()
        if fetch_subtitles:
            opts['writesubtitles'] = True
            opts['writeautomaticsub'] = True
            opts['subtitleslangs'] = ['en', 'zh-Hans', 'zh-Hant', 'zh']

        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)

                if not info:
                    raise ValueError(f"Failed to extract info from {url}")

                # Extract subtitle URLs
                subtitles = []
                if info.get('subtitles'):
                    for lang, sub_list in info['subtitles'].items():
                        if isinstance(sub_list, list) and len(sub_list) > 0:
                            subtitles.append(sub_list[0].get('url', ''))
                if info.get('automatic_captions'):
                    for lang, sub_list in info['automatic_captions'].items():
                        if isinstance(sub_list, list) and len(sub_list) > 0:
                            subtitles.append(sub_list[0].get('url', ''))

                # Build video info
                return VideoInfo(
                    id=info.get('id', ''),
                    title=info.get('title', 'Unknown Title'),
                    description=info.get('description', ''),
                    uploader=info.get('uploader', 'Unknown'),
                    uploader_id=info.get('uploader_id', ''),
                    duration=info.get('duration', 0),
                    view_count=info.get('view_count', 0),
                    upload_date=info.get('upload_date', ''),
                    thumbnail=info.get('thumbnail', ''),
                    tags=info.get('tags', []),
                    categories=info.get('categories', []),
                    webpage_url=info.get('webpage_url', url),
                    original_url=url,
                    platform=self._detect_platform(info),
                    subtitles=subtitles,
                    extractor=info.get('extractor', 'generic'),
                    formatted_duration=self._format_duration(info.get('duration', 0))
                )

            except Exception as e:
                raise Exception(f"yt-dlp extraction failed: {e}")

    def _detect_platform(self, info: Dict) -> str:
        """Detect platform from extracted info"""
        extractor = info.get('extractor', '')

        extractor_map = {
            'youtube': 'youtube',
            'youtu.be': 'youtube',
            'bilibili': 'bilibili',
            'vimeo': 'vimeo',
            'twitter': 'twitter',
            'x.com': 'twitter',
            'douyin': 'douyin',
            'tiktok': 'tiktok',
        }

        for key, platform in extractor_map.items():
            if key in extractor.lower():
                return platform

        return extractor or 'unknown'

    def _build_main_content(self, video_info: VideoInfo) -> str:
        """Build main content string from video info"""
        parts = []

        if video_info.title:
            parts.append(f"# {video_info.title}\n")

        if video_info.description:
            parts.append(f"## Description\n\n{video_info.description}\n")

        if video_info.tags:
            parts.append(f"## Tags\n\n{', '.join(video_info.tags)}\n")

        if video_info.categories:
            parts.append(f"## Categories\n\n{', '.join(video_info.categories)}\n")

        return "\n".join(parts)

    def _generate_summary(self, video_info: VideoInfo) -> str:
        """Generate a summary from video metadata"""
        parts = []

        if video_info.title:
            parts.append(video_info.title)

        if video_info.description:
            desc = video_info.description[:200]
            if len(video_info.description) > 200:
                desc += "..."
            parts.append(desc)

        return " - ".join(parts)

    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to human readable"""
        if not seconds:
            return "Unknown"

        td = timedelta(seconds=seconds)
        hours = td.seconds // 3600
        minutes = (td.seconds % 3600) // 60
        secs = td.seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"

    def _format_date(self, date_str: str) -> str:
        """Format YYYYMMDD to ISO format"""
        if not date_str or len(date_str) != 8:
            return ""

        try:
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            return f"{year}-{month}-{day}"
        except:
            return date_str

    def _fetch_subtitles(self, subtitle_urls: List[str]) -> str:
        """Fetch subtitle content from URLs"""
        if not subtitle_urls:
            return ""

        import requests

        for url in subtitle_urls:
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                # Parse subtitle format (usually VTT or SRT)
                content = response.text
                return self._parse_subtitle_content(content)
            except Exception as e:
                continue

        return ""

    def _parse_subtitle_content(self, content: str) -> str:
        """Parse subtitle content and extract text"""
        lines = content.split('\n')
        text_lines = []

        for line in lines:
            line = line.strip()
            # Skip VTT/SRT metadata lines
            if (not line or
                line.startswith('WEBVTT') or
                line.startswith('Kind:') or
                re.match(r'\d{2}:', line) or
                re.match(r'\d+ -->', line) or
                re.match(r'^\d+$', line)):
                continue

            # Remove timestamp and formatting
            line = re.sub(r'<[^>]+>', '', line)  # Remove HTML tags
            line = re.sub(r'\{[^}]+\}', '', line)  # Remove {} tags
            line = re.sub(r'\[[^\]]+\]', '', line)  # Remove [] tags

            if line and len(line) > 1:
                text_lines.append(line)

        return ' '.join(text_lines)

    def batch_extract(self, urls: List[str], fetch_subtitles: bool = False) -> List[ProcessedContent]:
        """
        Extract info from multiple URLs

        Args:
            urls: List of video URLs
            fetch_subtitles: Whether to fetch subtitles

        Returns:
            List of ProcessedContent objects
        """
        results = []
        for url in urls:
            try:
                from url_detector import detect_url
                url_info = detect_url(url)
                if self.can_process(url_info):
                    result = self.extract(url_info, fetch_subtitles)
                    results.append(result)
            except Exception as e:
                print(f"Failed to extract {url}: {e}")
                continue

        return results


def extract_video_info(url: str, fetch_subtitles: bool = False) -> Optional[VideoInfo]:
    """
    Convenience function to extract video info

    Args:
        url: Video URL
        fetch_subtitles: Whether to fetch subtitles

    Returns:
        VideoInfo object or None if failed
    """
    if not YTDLP_AVAILABLE:
        raise ImportError("yt-dlp is not installed")

    processor = VideoInfoProcessor()
    from url_detector import detect_url

    url_info = detect_url(url)
    if url_info.url_type == URLType.VIDEO:
        content = processor.extract(url_info, fetch_subtitles)
        # Return raw info instead
        return processor._extract_video_info(url, fetch_subtitles)

    return None


# Test function
def test_video_extraction():
    """Test video info extraction with sample URLs"""
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # YouTube
        "https://www.bilibili.com/video/BV1xx411c7mD",  # Bilibili (example)
    ]

    processor = VideoInfoProcessor()

    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"Testing: {url}")
        print(f"{'='*60}")

        try:
            from url_detector import detect_url
            url_info = detect_url(url)

            if processor.can_process(url_info):
                content = processor.extract(url_info, fetch_subtitles=False)

                print(f"✅ Success!")
                print(f"Title: {content.content.get('title')}")
                print(f"Platform: {content.content.get('metadata', {}).get('platform')}")
                print(f"Duration: {content.content.get('metadata', {}).get('duration')}")
                print(f"Views: {content.content.get('metadata', {}).get('view_count')}")
            else:
                print(f"❌ Cannot process this URL type")

        except Exception as e:
            print(f"❌ Failed: {e}")


if __name__ == "__main__":
    test_video_extraction()
