"""
Video Processor Module - Extract video information using yt-dlp

Supports: YouTube, Bilibili, and 1000+ other video platforms
"""
import os
import re
import json
import time
import tempfile
import subprocess
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from url_detector import URLInfo, URLType
from processors.content_processor import ContentProcessor, ProcessedContent


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
    subtitle_text: str  # extracted subtitle content
    extractor: str  # which yt-dlp extractor was used
    formatted_duration: str  # human readable duration
    screenshots: List[str]  # base64 encoded screenshots


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

    # Expanded subtitle language support
    SUBTITLE_LANGUAGES = [
        # Primary languages (most likely to have subtitles)
        'en',           # English
        'zh-Hans',      # Chinese Simplified
        'zh-Hant',      # Chinese Traditional
        'zh',           # Chinese (any)
        'ja',           # Japanese
        'ko',           # Korean
        'es',           # Spanish
        'fr',           # French
        'de',           # German
        'pt',           # Portuguese
        'ru',           # Russian
        'it',           # Italian
        'ar',           # Arabic
        'hi',           # Hindi
        'th',           # Thai
        'vi',           # Vietnamese
        'id',           # Indonesian
        'ms',           # Malay
        'tr',           # Turkish
        'pl',           # Polish
        'nl',           # Dutch
        'sv',           # Swedish
        'no',           # Norwegian
        'da',           # Danish
        'fi',           # Finnish
        'cs',           # Czech
        'el',           # Greek
        'he',           # Hebrew
        'uk',           # Ukrainian
        # B站弹幕
        'danmaku',      # Bilibili danmaku
        # Fallback to auto-generated
        'en-US',        # English US
        'en-GB',        # English UK
        'zh-CN',        # Chinese China
        'zh-TW',        # Chinese Taiwan
        'zh-HK',        # Chinese Hong Kong
    ]

    def __init__(self):
        super().__init__()
        if not YTDLP_AVAILABLE:
            raise ImportError(
                "yt-dlp is not installed. Install it with: pip install yt-dlp"
            )

    def can_process(self, url_info: URLInfo) -> bool:
        """Can process video URLs"""
        return url_info.url_type == URLType.VIDEO

    def extract(self, url_info: URLInfo, fetch_subtitles: bool = True, capture_screenshots: bool = True) -> ProcessedContent:
        """
        Extract video information using yt-dlp

        Args:
            url_info: URL information from URLDetector
            fetch_subtitles: Whether to fetch subtitles/captions if available (default: True)
            capture_screenshots: Whether to capture key frame screenshots (default: True)

        Returns:
            ProcessedContent with video metadata
        """
        self._start_timer()
        result = self._create_base_content(url_info)

        try:
            # Extract video info
            video_info = self._extract_video_info(url_info.url, fetch_subtitles, capture_screenshots)

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
                    "extractor": video_info.extractor,
                    "has_subtitles": bool(video_info.subtitle_text),
                    "subtitle_length": len(video_info.subtitle_text) if video_info.subtitle_text else 0,
                    "screenshot_count": len(video_info.screenshots)
                }
            }

            # Include subtitle text if available
            if video_info.subtitle_text:
                result.content["subtitle_text"] = video_info.subtitle_text
                # Add subtitle summary to main content
                subtitle_summary = video_info.subtitle_text[:500]
                if len(video_info.subtitle_text) > 500:
                    subtitle_summary += "..."
                result.content["main_content"] += f"\n\n## Transcript Preview\n\n{subtitle_summary}"

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
                "screenshots": video_info.screenshots
            }

            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": True,
                "errors": [],
                "extractor_used": video_info.extractor,
                "subtitles_fetched": bool(video_info.subtitle_text),
                "screenshots_captured": len(video_info.screenshots) > 0
            })

        except Exception as e:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [str(e)]
            })
            raise

        return result

    def _extract_video_info(self, url: str, fetch_subtitles: bool = True, capture_screenshots: bool = True) -> VideoInfo:
        """Extract video information using yt-dlp"""
        opts = self.YTDLP_OPTS.copy()

        # Configure subtitle extraction with expanded language support
        if fetch_subtitles:
            opts['writesubtitles'] = True
            opts['writeautomaticsub'] = True
            opts['subtitleslangs'] = self.SUBTITLE_LANGUAGES

        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)

                if not info:
                    raise ValueError(f"Failed to extract info from {url}")

                # Extract subtitle URLs and fetch subtitle text
                subtitles = []
                subtitle_text = ""

                if fetch_subtitles:
                    # Get manual subtitles (prioritized)
                    manual_subs = info.get('subtitles', {})
                    for lang in self.SUBTITLE_LANGUAGES:
                        if lang in manual_subs:
                            sub_list = manual_subs[lang]
                            if isinstance(sub_list, list) and len(sub_list) > 0:
                                sub_url = sub_list[0].get('url', '')
                                if sub_url:
                                    subtitles.append(sub_url)

                    # Get automatic captions (fallback)
                    if not subtitles:
                        auto_caps = info.get('automatic_captions', {})
                        for lang in self.SUBTITLE_LANGUAGES:
                            if lang in auto_caps:
                                sub_list = auto_caps[lang]
                                if isinstance(sub_list, list) and len(sub_list) > 0:
                                    sub_url = sub_list[0].get('url', '')
                                    if sub_url:
                                        subtitles.append(sub_url)

                    # Fetch subtitle text with improved parsing
                    if subtitles:
                        # Try multiple subtitle sources, combine results
                        all_subtitle_texts = []
                        for sub_url in subtitles[:5]:  # Try up to 5 subtitle sources
                            try:
                                text = self._fetch_subtitles([sub_url])
                                if text and len(text) > 50:  # Only use if meaningful
                                    all_subtitle_texts.append(text)
                            except Exception:
                                continue

                        # Combine multiple subtitle sources
                        if all_subtitle_texts:
                            subtitle_text = self._combine_subtitle_texts(all_subtitle_texts)

                # Capture screenshots if requested
                screenshots = []
                if capture_screenshots:
                    screenshots = self._capture_screenshots_from_info(info, num_screenshots=5)

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
                    subtitle_text=subtitle_text,
                    extractor=info.get('extractor', 'generic'),
                    formatted_duration=self._format_duration(info.get('duration', 0)),
                    screenshots=screenshots
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
                headers = {
                    'User-Agent': 'Mozilla/5.0',
                    'Referer': 'https://www.bilibili.com/' if 'bilibili' in url else None
                }
                # Filter out None headers
                headers = {k: v for k, v in headers.items() if v is not None}

                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()

                # Try to detect encoding
                if 'bilibili' in url:
                    response.encoding = 'utf-8'

                # Parse subtitle format (usually VTT, SRT, or TTML/danmaku)
                content = response.text
                return self._parse_subtitle_content(content)
            except Exception as e:
                continue

        return ""

    def _parse_subtitle_content(self, content: str) -> str:
        """
        Parse subtitle content and extract text with improved precision

        Handles:
        - WebVTT format (.vtt)
        - SubRip format (.srt)
        - TTML format (.ttml)
        - Bilibili Danmaku XML format
        - Various JSON subtitle formats
        """
        lines = content.split('\n')
        text_lines = []

        # Detect format
        is_vtt = content.strip().startswith('WEBVTT')
        is_srt = bool(re.search(r'^\d+\s*\n\d{2}:\d{2}:\d{2}', content, re.MULTILINE))
        is_ttml = '<tt' in content.lower()
        is_danmaku = '<d p=' in content or '<chatid>' in content

        if is_ttml:
            # TTML format - XML based
            return self._parse_ttml_content(content)

        if is_danmaku:
            # Bilibili danmaku format
            return self._parse_danmaku_content(content)

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip VTT/SRT metadata and empty lines
            if not line:
                i += 1
                continue

            # Skip VTT header
            if line == 'WEBVTT':
                i += 1
                continue

            # Skip style/meta blocks
            if line.startswith(('STYLE', 'NOTE', 'Kind:')):
                i += 1
                continue

            # Skip line numbers (SRT)
            if re.match(r'^\d+$', line):
                i += 1
                continue

            # Skip timestamp lines
            if self._is_timestamp_line(line):
                i += 1
                continue

            # Skip timestamp tags in VTT
            if line.startswith('<') and line.endswith('>'):
                i += 1
                continue

            # Clean and process text line
            cleaned_line = self._clean_subtitle_line(line)
            if cleaned_line and len(cleaned_line) > 1:
                # Avoid duplicate consecutive lines
                if not text_lines or text_lines[-1] != cleaned_line:
                    text_lines.append(cleaned_line)

            i += 1

        # Join with proper spacing
        result = ' '.join(text_lines)

        # Clean up common issues
        result = self._post_process_subtitle_text(result)

        return result

    def _is_timestamp_line(self, line: str) -> bool:
        """Check if line is a timestamp"""
        # VTT/SRT timestamp patterns
        timestamp_patterns = [
            r'^\d{2}:\d{2}:\d{2}',  # 00:00:00
            r'^\d{2}:\d{2}:\d{2}\.\d{3}',  # 00:00:00.000
            r'^\d{2}:\d{2}:\d{2},\d{3}',  # 00:00:00,000
            r'^\d{2}:\d{2}',  # 00:00
            r'\d{2}:\d{2}:\d{2}.*-->',  # Timestamp with arrow
            r'-->.*\d{2}:\d{2}:\d{2}',  # Arrow with timestamp
        ]
        return any(re.search(pattern, line) for pattern in timestamp_patterns)

    def _clean_subtitle_line(self, line: str) -> str:
        """Clean a subtitle line by removing formatting and tags"""
        # Remove HTML/XML tags
        line = re.sub(r'<[^>]+>', '', line)
        # Remove curly brace tags (common in subtitles)
        line = re.sub(r'\{[^}]+\}', '', line)
        # Remove square bracket tags
        line = re.sub(r'\[[^\]]+\]', '', line)
        # Remove timestamps at start/end
        line = re.sub(r'^\d{2}:\d{2}:\d{2}[.,]\d+\s*', '', line)
        line = re.sub(r'\s*\d{2}:\d{2}:\d{2}[.,]\d+\s*$', '', line)
        # Remove position tags like {\an8}
        line = re.sub(r'\\[aAnN]\d+', '', line)
        # Remove music symbols
        line = line.replace('♫', '').replace('♪', '')
        # Remove duplicate spaces
        line = re.sub(r'\s+', ' ', line)
        return line.strip()

    def _post_process_subtitle_text(self, text: str) -> str:
        """Post-process subtitle text to fix common issues"""
        # Fix common OCR/spacing issues
        text = re.sub(r'\s+([.!?,:;])', r'\1', text)  # Fix "word ." -> "word."
        text = re.sub(r'([.!?])\s+([a-z])', r'\1 \2', text)  # Ensure proper sentence spacing
        # Remove ellipsis overuse
        text = re.sub(r'\.{4,}', '...', text)
        # Fix broken words at line breaks
        text = re.sub(r'([a-z])-\s+([a-z])', r'\1\2', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _parse_ttml_content(self, content: str) -> str:
        """Parse TTML (XML-based) subtitle format"""
        try:
            import xml.etree.ElementTree as ET
            # Remove namespace if present
            content = re.sub(r'<\?xml[^>]+\?>', '', content)
            content = re.sub(r'xmlns[^=]*="[^"]*"', '', content)

            root = ET.fromstring(content)
            text_lines = []

            # Find all text elements
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    text = elem.text.strip()
                    # Remove tags from within TTML
                    text = re.sub(r'<[^>]+>', '', text)
                    if text and len(text) > 1:
                        text_lines.append(text)

            return ' '.join(text_lines)
        except Exception:
            # Fallback to regex extraction
            text_matches = re.findall(r'>([^<]{10,})<', content)
            return ' '.join(text_matches)

    def _parse_danmaku_content(self, content: str) -> str:
        """
        Parse Bilibili danmaku XML format

        Danmaku format: <d p="time,type,size,color,send_time,hash,id,pool">content</d>
        """
        try:
            import xml.etree.ElementTree as ET

            root = ET.fromstring(content)
            danmaku_texts = []

            # Find all <d> tags (danmaku entries)
            for d_tag in root.findall('d'):
                if d_tag.text and d_tag.text.strip():
                    text = d_tag.text.strip()
                    # Filter out very short or spam-like danmaku
                    if len(text) >= 2:
                        # Skip pure punctuation or numbers
                        if not text.replace('，', '').replace('。', '').replace('！', '').replace('？', '').replace('/', '').isdigit():
                            danmaku_texts.append(text)

            # Join danmaku with spacing
            result = ' '.join(danmaku_texts)

            # Post-process to clean up
            result = self._post_process_subtitle_text(result)

            return result
        except Exception as e:
            # Fallback to regex extraction
            # Match content inside <d> tags
            danmaku_matches = re.findall(r'<d[^>]*>([^<]+)</d>', content)
            filtered = [d.strip() for d in danmaku_matches if len(d.strip()) >= 2]
            return ' '.join(filtered)

    def _combine_subtitle_texts(self, texts: list) -> str:
        """
        Combine multiple subtitle texts intelligently

        Removes duplicates while preserving unique content
        """
        if not texts:
            return ""

        # Clean and deduplicate
        seen = set()
        unique_texts = []

        for text in texts:
            # Normalize for comparison
            normalized = ' '.join(text.split()).lower()
            # Create a hash for comparison (use first 100 chars as key)
            text_key = normalized[:100]

            if text_key not in seen:
                seen.add(text_key)
                unique_texts.append(text)

        # Combine all unique texts
        combined = ' '.join(unique_texts)

        # Clean up combined text
        combined = self._post_process_subtitle_text(combined)

        return combined

    def _capture_screenshots_from_info(self, info: Dict, num_screenshots: int = 5) -> List[str]:
        """
        Capture key frame screenshots from video info

        Args:
            info: Video info dict from yt-dlp
            num_screenshots: Number of screenshots to capture (default: 5)

        Returns:
            List of base64 encoded screenshot data URIs
        """
        screenshots = []

        # Try to get thumbnail URLs first (most reliable)
        thumbnail = info.get('thumbnail', '')
        if thumbnail:
            try:
                thumb_data = self._download_and_encode_image(thumbnail, high_quality=True)
                if thumb_data:
                    screenshots.append(thumb_data)
            except Exception:
                pass

        # Try to get additional thumbnails if available
        thumbnails = info.get('thumbnails', [])
        for thumb in thumbnails[:num_screenshots - 1]:
            try:
                thumb_url = thumb.get('url', '')
                if thumb_url and thumb_url != thumbnail:
                    thumb_data = self._download_and_encode_image(thumb_url, high_quality=True)
                    if thumb_data:
                        screenshots.append(thumb_data)
                        if len(screenshots) >= num_screenshots:
                            break
            except Exception:
                continue

        # If we still need more screenshots and ffmpeg is available, capture from video
        if len(screenshots) < num_screenshots and self._check_ffmpeg_available():
            try:
                video_url = info.get('url', '')
                if video_url:
                    additional_count = num_screenshots - len(screenshots)
                    additional_screenshots = self._capture_ffmpeg_screenshots(
                        video_url,
                        additional_count,
                        high_quality=True
                    )
                    screenshots.extend(additional_screenshots)
            except Exception:
                pass

        return screenshots[:num_screenshots]

    def _download_and_encode_image(self, url: str, high_quality: bool = False) -> str:
        """
        Download image and convert to base64 data URI

        Args:
            url: Image URL
            high_quality: Whether to request high quality version

        Returns:
            Base64 encoded data URI
        """
        if not REQUESTS_AVAILABLE:
            return ""

        try:
            headers = {}
            if high_quality:
                # Request high quality images
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }

            response = requests.get(url, headers=headers, timeout=15, stream=True)
            response.raise_for_status()

            import base64

            # Detect image format
            content_type = response.headers.get('Content-Type', 'image/jpeg')

            # Encode to base64
            image_data = response.content
            base64_data = base64.b64encode(image_data).decode('utf-8')

            return f"data:{content_type};base64,{base64_data}"

        except Exception:
            return ""

    def _check_ffmpeg_available(self) -> bool:
        """Check if ffmpeg is available in the system"""
        try:
            result = subprocess.run(['ffmpeg', '-version'],
                                    capture_output=True,
                                    timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _capture_ffmpeg_screenshots(self, video_url: str, num_screenshots: int, high_quality: bool = True) -> List[str]:
        """
        Capture screenshots using ffmpeg at different time points

        Args:
            video_url: URL of the video
            num_screenshots: Number of screenshots to capture
            high_quality: Whether to capture high quality screenshots

        Returns:
            List of base64 encoded screenshots
        """
        screenshots = []

        if not self._check_ffmpeg_available():
            return screenshots

        try:
            import base64

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Get video duration first
                probe_cmd = [
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    video_url
                ]

                result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
                duration = float(result.stdout.strip()) if result.stdout.strip() else 60

                # Calculate screenshot time points (evenly distributed)
                # More time points for better coverage
                time_points = []
                for i in range(1, num_screenshots + 1):
                    pct = i / (num_screenshots + 1)
                    time_points.append(duration * pct)

                for i, time_point in enumerate(time_points):
                    output_file = temp_path / f"screenshot_{i}.jpg"

                    # Quality settings
                    quality = '1' if high_quality else '2'  # Lower = better quality (1-31 scale)
                    vframes = '1'  # Single frame

                    # Capture screenshot with improved quality
                    ffmpeg_cmd = [
                        'ffmpeg', '-ss', str(time_point),
                        '-i', video_url,
                        '-vframes', vframes,
                        '-q:v', quality,
                        '-vf', 'scale=1280:-2',  # Scale to 1280px width, maintain aspect ratio
                        '-y',  # Overwrite output file
                        str(output_file)
                    ]

                    subprocess.run(ffmpeg_cmd, capture_output=True, timeout=30)

                    if output_file.exists():
                        # Read and encode
                        with open(output_file, 'rb') as f:
                            image_data = f.read()
                        base64_data = base64.b64encode(image_data).decode('utf-8')
                        screenshots.append(f"data:image/jpeg;base64,{base64_data}")

        except Exception:
            pass

        return screenshots

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
