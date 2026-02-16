"""
Audio Processor Module - Handle audio files and podcasts

This module processes audio content to extract:
- Audio metadata
- Transcription (if available)
- Podcast episode info
- Duration and format
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from url_detector import URLInfo, URLType
from processors.content_processor import ContentProcessor, ProcessedContent


@dataclass
class AudioMetadata:
    """Metadata extracted from audio"""
    title: str
    artist: str = ""
    album: str = ""
    duration: float = 0  # seconds
    bitrate: int = 0
    sample_rate: int = 0
    codec: str = ""

    # Podcast-specific
    podcast_name: str = ""
    episode_number: int = 0
    episode_date: str = ""
    show_notes: str = ""
    host: str = ""

    # File info
    file_size: int = 0
    format: str = ""


@dataclass
class TranscriptSegment:
    """A segment of transcribed audio"""
    start_time: float
    end_time: float
    text: str
    confidence: float = 1.0


class AudioProcessor(ContentProcessor):
    """
    Processor for audio files and podcasts

    Supports:
    - Audio files (MP3, M4A, WAV, FLAC, etc.)
    - Podcast URLs (various platforms)
    - Local file paths
    - Optional transcription
    """

    def __init__(self):
        super().__init__()
        self.mutagen_available = self._check_mutagen_support()
        self.transcription_available = self._check_transcription_support()

    def can_process(self, url_info: URLInfo) -> bool:
        """Check if this is an audio file or podcast"""
        # Check file extension
        if url_info.url_type == URLType.FILE:
            path = url_info.url.lower()
            audio_extensions = (
                '.mp3', '.m4a', '.wav', '.flac', '.aac', '.ogg',
                '.wma', '.opus', '.mp4', '.m4b', '.m4p'
            )
            return path.endswith(audio_extensions)

        # Check for audio URLs
        url_lower = url_info.url.lower()

        # Podcast platforms
        podcast_domains = [
            'podcasts.apple.com', 'open.spotify.com/show',
            'podcast.google.com', 'stitcher.com',
            'pca.st', 'podbean.com', 'buzzsprout.com',
            'soundcloud.com', 'mixcloud.com'
        ]

        # Audio file indicators
        audio_indicators = [
            '.mp3', '.m4a', '.wav', '.flac', '.aac',
            'audio', 'podcast', 'episode'
        ]

        return any(domain in url_lower for domain in podcast_domains) or \
               any(indicator in url_lower for indicator in audio_indicators)

    def extract(self, url_info: URLInfo) -> ProcessedContent:
        """Extract content from audio"""
        self._start_timer()
        result = self._create_base_content(url_info)

        # Determine source type
        url = url_info.url

        # Check if it's a local file
        if not url.startswith(('http://', 'https://')):
            return self._extract_local_file(url, url_info)

        # Check for podcast URLs
        if self._is_podcast_url(url):
            return self._extract_podcast(url, url_info)

        # Direct audio URL
        if url.lower().endswith(('.mp3', '.m4a', '.wav', '.flac')):
            return self._extract_from_url(url, url_info)

        # Generic audio URL
        result.content = {
            "title": self._extract_title_from_url(url),
            "url": url,
            "main_content": "",
            "summary": "Audio content - transcription not available",
            "metadata": {"type": "audio", "requires_download": True}
        }

        result.processing_info.update({
            "processing_time": self._end_timer(),
            "success": True,
            "note": "Audio URL detected. Download and process locally for full extraction."
        })

        return result

    def _extract_local_file(self, file_path: str, url_info: URLInfo) -> ProcessedContent:
        """Extract from local audio file"""
        result = self._create_base_content(url_info)

        path = Path(file_path)
        if not path.exists():
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [f"File not found: {file_path}"]
            })
            return result

        try:
            metadata = self._extract_audio_metadata(path)

            result.content = {
                "title": metadata.title,
                "url": str(path),
                "main_content": "",
                "summary": self._generate_audio_summary(metadata),
                "metadata": {
                    "artist": metadata.artist,
                    "album": metadata.album,
                    "duration": metadata.duration,
                    "duration_formatted": self._format_duration(metadata.duration),
                    "format": metadata.format,
                    "bitrate": metadata.bitrate,
                    "podcast_name": metadata.podcast_name,
                    "episode_number": metadata.episode_number
                }
            }

            # Try to extract show notes from filename or metadata
            show_notes = self._extract_show_notes(path, metadata)
            if show_notes:
                result.content["show_notes"] = show_notes

            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": True,
                "duration": metadata.duration,
                "file_size": metadata.file_size
            })

        except Exception as e:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [f"Audio extraction failed: {str(e)}"]
            })

        return result

    def _extract_podcast(self, url: str, url_info: URLInfo) -> ProcessedContent:
        """Extract podcast information from URL"""
        result = self._create_base_content(url_info)

        # Parse podcast URL to extract info
        info = self._parse_podcast_url(url)

        result.content = {
            "title": info.get("title", "Podcast Episode"),
            "url": url,
            "main_content": "",
            "summary": info.get("description", f"Episode from {info.get('podcast_name', 'Unknown Podcast')}"),
            "metadata": {
                "podcast_name": info.get("podcast_name", ""),
                "episode_number": info.get("episode_number", ""),
                "episode_date": info.get("episode_date", ""),
                "host": info.get("host", ""),
                "type": "podcast"
            }
        }

        result.processing_info.update({
            "processing_time": self._end_timer(),
            "success": True,
            "note": "For full audio processing, download the episode and process locally."
        })

        return result

    def _extract_from_url(self, url: str, url_info: URLInfo) -> ProcessedContent:
        """Extract metadata from direct audio URL"""
        result = self._create_base_content(url_info)

        result.content = {
            "title": self._extract_title_from_url(url),
            "url": url,
            "main_content": "",
            "summary": "Audio file - Download and process locally for full metadata",
            "metadata": {"type": "audio", "url": url}
        }

        result.processing_info.update({
            "processing_time": self._end_timer(),
            "success": True,
            "note": "Direct audio URL. Download for full processing."
        })

        return result

    def _extract_audio_metadata(self, path: Path) -> AudioMetadata:
        """Extract metadata from audio file"""
        metadata = AudioMetadata(
            title=path.stem,
            file_size=path.stat().st_size,
            format=path.suffix[1:].upper()
        )

        if not self.mutagen_available:
            return metadata

        try:
            import mutagen

            audio_file = mutagen.File(path)

            if audio_file is None:
                return metadata

            # Extract common metadata
            if hasattr(audio_file, 'info'):
                info = audio_file.info
                metadata.duration = getattr(info, 'length', 0)
                metadata.bitrate = getattr(info, 'bitrate', 0)
                metadata.sample_rate = getattr(info, 'sample_rate', 0)

            # Extract tags
            if hasattr(audio_file, 'tags'):
                tags = audio_file.tags or {}

                # Try common tag names
                tag_map = {
                    'TIT2': 'title', 'TITLE': 'title', 'title': 'title',
                    'TPE1': 'artist', 'ARTIST': 'artist', 'artist': 'artist',
                    'TALB': 'album', 'ALBUM': 'album', 'album': 'album',
                    'TDRC': 'date', 'DATE': 'date', 'date': 'date',
                    'TCON': 'genre', 'GENRE': 'genre', 'genre': 'genre'
                }

                for tag_key, attr_name in tag_map.items():
                    if tag_key in tags:
                        value = tags[tag_key]
                        if isinstance(value, list) and value:
                            value = value[0]
                        if hasattr(value, 'text'):
                            value = value.text[0] if value.text else str(value)

                        setattr(metadata, attr_name, str(value))

                # Podcast-specific tags
                if 'podcast' in str(tags).lower():
                    metadata.podcast_name = tags.get('album', [''])[0] if 'album' in tags else ''
                    metadata.episode_number = self._extract_episode_number(tags)

        except Exception as e:
            print(f"Warning: Could not extract full audio metadata: {e}")

        return metadata

    def _extract_show_notes(self, path: Path, metadata: AudioMetadata) -> Optional[str]:
        """Extract show notes from external file or metadata"""
        # Check for accompanying text file
        notes_path = path.with_suffix('.txt')
        if notes_path.exists():
            try:
                with open(notes_path, 'r', encoding='utf-8') as f:
                    return f.read()[:5000]  # Limit to 5000 chars
            except:
                pass

        # Check for chapters file
        chapters_path = path.with_suffix('.chapters.txt')
        if chapters_path.exists():
            try:
                with open(chapters_path, 'r', encoding='utf-8') as f:
                    return f"Chapters:\n" + f.read()[:3000]
            except:
                pass

        return None

    def _parse_podcast_url(self, url: str) -> Dict[str, Any]:
        """Parse podcast URL for episode information"""
        info = {}

        url_lower = url.lower()

        # Apple Podcasts
        if 'podcasts.apple.com' in url_lower:
            parts = url.split('/')
            for i, part in enumerate(parts):
                if part == 'podcast':
                    info['podcast_name'] = parts[i + 1] if i + 1 < len(parts) else ''
                elif part == 'i':
                    info['episode_number'] = parts[i + 1] if i + 1 < len(parts) else ''

        # Spotify
        elif 'open.spotify.com/show' in url_lower:
            show_match = re.search(r'/show/([^/]+)', url)
            episode_match = re.search(r'/episode/([^/]+)', url)
            if show_match:
                info['podcast_name'] = show_match.group(1)
            if episode_match:
                info['episode_number'] = episode_match.group(1)

        # Google Podcasts
        elif 'podcast.google.com' in url_lower:
            feed_match = re.search(r'feed=([^&]+)', url)
            if feed_match:
                info['podcast_name'] = feed_match.group(1)

        # Extract title from URL if no other info
        if not info.get('title'):
            title_match = re.search(r'/([^/]+)(?:/\d+)?$', url)
            if title_match:
                info['title'] = title_match.group(1).replace('-', ' ').replace('_', ' ').title()
                info['title'] = re.sub(r'\d{8,}', '', info['title'])  # Remove long numbers

        return info

    def _is_podcast_url(self, url: str) -> bool:
        """Check if URL is a podcast"""
        podcast_domains = [
            'podcasts.apple.com', 'open.spotify.com/show',
            'podcast.google.com', 'stitcher.com',
            'pca.st', 'podbean.com', 'buzzsprout.com',
            'soundcloud.com', 'mixcloud.com'
        ]
        return any(domain in url.lower() for domain in podcast_domains)

    def _extract_title_from_url(self, url: str) -> str:
        """Extract title from URL"""
        # Get filename from URL
        parts = url.split('/')
        filename = parts[-1] if parts else ''

        # Remove extension and clean up
        title = filename.rsplit('.', 1)[0] if '.' in filename else filename
        title = title.replace('-', ' ').replace('_', ' ').title()
        title = re.sub(r'\d{8,}', '', title)  # Remove long numbers
        title = re.sub(r'\s+', ' ', title).strip()

        return title or "Audio Content"

    def _extract_episode_number(self, tags: dict) -> int:
        """Try to extract episode number from tags"""
        # Check common episode number tags
        episode_tags = ['trck', 'tracknumber', 'episode', 'tn']

        for tag in episode_tags:
            if tag in tags:
                try:
                    value = tags[tag]
                    if isinstance(value, list):
                        value = value[0]
                    return int(str(value).split('/')[0])
                except:
                    pass

        return 0

    def _generate_audio_summary(self, metadata: AudioMetadata) -> str:
        """Generate a summary from audio metadata"""
        parts = []

        if metadata.podcast_name:
            parts.append(f"Podcast: {metadata.podcast_name}")

        if metadata.artist:
            parts.append(f"Artist: {metadata.artist}")

        if metadata.album:
            parts.append(f"Album: {metadata.album}")

        if metadata.duration > 0:
            parts.append(f"Duration: {self._format_duration(metadata.duration)}")

        return " | ".join(parts) if parts else "Audio file"

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            mins = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}h {mins}m"

    def transcribe(self, audio_path: str, language: str = "en") -> List[TranscriptSegment]:
        """
        Transcribe audio file

        Note: This requires additional dependencies like:
        - OpenAI Whisper (pip install openai-whisper)
        - Or use an API service

        Args:
            audio_path: Path to audio file
            language: Language code (default: en)

        Returns:
            List of transcript segments
        """
        segments = []

        if not self.transcription_available:
            print("Transcription not available. Install whisper: pip install openai-whisper")
            return segments

        try:
            import whisper

            # Load model (base is fastest, use large for better accuracy)
            model = whisper.load_model("base")

            # Transcribe
            result = model.transcribe(audio_path, language=language)

            # Convert to segments
            for seg in result['segments']:
                segments.append(TranscriptSegment(
                    start_time=seg['start'],
                    end_time=seg['end'],
                    text=seg['text'].strip(),
                    confidence=1.0  # Whisper doesn't provide confidence
                ))

        except Exception as e:
            print(f"Transcription failed: {e}")

        return segments

    def _check_mutagen_support(self) -> bool:
        """Check if mutagen is available for audio metadata"""
        try:
            import mutagen
            return True
        except ImportError:
            return False

    def _check_transcription_support(self) -> bool:
        """Check if transcription is available"""
        try:
            import whisper
            return True
        except ImportError:
            return False

    @staticmethod
    def get_installation_instructions() -> str:
        """Return installation instructions for dependencies"""
        return """
To enable audio processing, install the following:

For audio metadata:
    pip install mutagen

For audio transcription (optional):
    pip install openai-whisper

Or install all:
    pip install mutagen openai-whisper
        """


if __name__ == "__main__":
    # Test the audio processor
    print("Audio Processor Module")
    print("=" * 50)

    processor = AudioProcessor()

    print(f"\nMutagen support: {processor.mutagen_available}")
    print(f"Transcription support: {processor.transcription_available}")

    if not processor.mutagen_available:
        print("\n" + processor.get_installation_instructions())

    print("\n✓ Audio processor module loaded!")
