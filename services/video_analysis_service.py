"""
Video Analysis Service

Provides comprehensive video analysis including:
- Video downloading
- Audio extraction and speech-to-text transcription
- LLM-powered transcript analysis
- Key frame extraction
"""
import os
import re
import json
import time
import tempfile
import subprocess
import requests
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class VideoAnalysisResult:
    """Result of video analysis"""
    success: bool
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    transcript: Optional[str] = None
    transcript_segments: Optional[List[Dict]] = None
    summary: Optional[str] = None
    key_points: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    key_frames: Optional[List[Dict]] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    processing_time: float = 0


class VideoDownloader:
    """Download videos from various sources"""

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()

    def _get_douyin_video_url(self, url: str) -> Optional[str]:
        """
        尝试使用 douyin_downloader 获取抖音视频 URL

        Returns:
            视频 URL 或 None
        """
        try:
            # 检查是否是抖音链接
            if 'douyin.com' not in url.lower():
                return None

            # 尝试使用 douyin_downloader 获取视频 URL
            from services.douyin_downloader import get_douyin_info
            from services.douyin_remote_client import get_remote_cookie_client

            # 优先从远程服务获取 cookies
            cookies = None
            try:
                remote_client = get_remote_cookie_client()
                logger.info("尝试从远程服务获取 cookies...")
                cookies = remote_client.get_cookies(url)
            except Exception as e:
                logger.warning(f"远程服务获取失败: {e}")

            # 如果远程服务失败，尝试本地保存的 cookies
            if not cookies:
                from services.settings_service import get_settings_service
                settings = get_settings_service()
                cookies = settings.get_douyin_cookies_string()

            result = get_douyin_info(url, cookies)
            if result.get('success') and result.get('video_url'):
                logger.info(f"通过 douyin_downloader 获取到视频URL")
                return result['video_url']

            # 如果没有 cookies，尝试不使用 cookies
            if not cookies:
                result = get_douyin_info(url, None)
                if result.get('success') and result.get('video_url'):
                    logger.info(f"通过 douyin_downloader(无cookie) 获取到视频URL")
                    return result['video_url']

        except Exception as e:
            logger.warning(f"douyin_downloader 获取视频URL失败: {e}")

        return None

    def _get_douyin_video_url_v2(self, url: str) -> Optional[str]:
        """
        使用新架构（远程API）获取抖音视频URL

        Returns:
            视频 URL 或 None
        """
        try:
            # 检查是否是抖音链接
            if 'douyin.com' not in url.lower():
                return None

            # 使用新的远程客户端获取下载链接
            from services.douyin_remote_client import get_douyin_remote_client

            client = get_douyin_remote_client()
            logger.info("使用新架构从远程API获取视频下载链接...")

            # 获取无水印下载链接
            result = client.get_download_url(url, with_watermark=False)

            if result and result.get("success"):
                video_url = result.get("video_url")
                if video_url:
                    logger.info("通过远程API获取到视频URL")
                    return video_url
            else:
                logger.warning(f"获取下载链接失败: {result}")

        except Exception as e:
            logger.warning(f"远程API获取视频URL失败: {e}")

        return None

    def download(self, url: str, progress_callback: Optional[Callable] = None) -> Optional[str]:
        """
        Download video from URL

        Args:
            url: Video URL
            progress_callback: Optional progress callback

        Returns:
            Path to downloaded video or None
        """
        # 优先使用新架构（远程API）
        video_url = self._get_douyin_video_url_v2(url)
        if video_url:
            try:
                output_path = os.path.join(self.temp_dir, f"video_{int(time.time())}.mp4")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Referer': 'https://www.douyin.com/'
                }
                response = requests.get(video_url, headers=headers, stream=True, timeout=60)

                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                        logger.info(f"视频下载成功(新架构): {output_path}")
                        return output_path
            except Exception as e:
                logger.warning(f"使用远程API URL 下载失败: {e}")

        # 备选：使用旧版 douyin_downloader
        video_url = self._get_douyin_video_url(url)
        if video_url:
            try:
                output_path = os.path.join(self.temp_dir, f"video_{int(time.time())}.mp4")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Referer': 'https://www.douyin.com/'
                }
                response = requests.get(video_url, headers=headers, stream=True, timeout=60)

                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                        logger.info(f"视频下载成功: {output_path}")
                        return output_path
            except Exception as e:
                logger.warning(f"使用 douyin_downloader URL 下载失败: {e}")

        # 如果上面的方法失败，尝试 yt_dlp
        try:
            import yt_dlp

            # Generate output path
            output_path = os.path.join(self.temp_dir, f"video_{int(time.time())}.mp4")

            # 检查是否是抖音链接，如果是则尝试添加 cookies
            ydl_opts = {
                'format': 'best[height<=1080][ext=mp4]',
                'outtmpl': output_path,
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 30,
                # Douyin-specific options
                'extractor_retries': 3,
                'fragment_retries': 3,
                'skip_unavailable_fragments': False,
                'geo_bypass': True,
            }

            # 如果是抖音链接，尝试添加 cookies
            if 'douyin.com' in url.lower():
                cookies = None
                cookies_dict = {}

                # 优先从远程服务获取 cookies
                try:
                    from services.douyin_remote_client import get_remote_cookie_client
                    remote_client = get_remote_cookie_client()
                    logger.info("尝试从远程服务获取 cookies...")
                    cookies = remote_client.get_cookies(url)
                except Exception as e:
                    logger.warning(f"远程服务获取失败: {e}")

                # 如果远程服务失败，尝试本地保存的 cookies
                if not cookies:
                    from services.settings_service import get_settings_service
                    settings = get_settings_service()
                    cookies = settings.get_douyin_cookies_string()

                if cookies:
                    # 将 cookies 转换为 dict 格式（支持 Netscape 格式）
                    # 检查是否是 Netscape 格式
                    if cookies.strip().startswith('# Netscape'):
                        for line in cookies.strip().split('\n'):
                            line = line.strip()
                            if not line or line.startswith('#'):
                                continue
                            parts = line.split('\t')
                            if len(parts) >= 7:
                                name = parts[5]
                                value = parts[6]
                                cookies_dict[name] = value
                    else:
                        # 简单格式
                        for item in cookies.split(';'):
                            item = item.strip()
                            if '=' in item:
                                key, value = item.split('=', 1)
                                cookies_dict[key.strip()] = value.strip()

                    if cookies_dict:
                        ydl_opts['cookies'] = cookies_dict
                        logger.info(f"已加载 {len(cookies_dict)} 个 cookies")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path

            # Check for other video files in temp dir
            for f in os.listdir(self.temp_dir):
                if f.endswith(('.mp4', '.mkv', '.webm')):
                    full_path = os.path.join(self.temp_dir, f)
                    if os.path.getsize(full_path) > 1000:  # At least 1KB
                        return full_path

            return None

        except Exception as e:
            logger.error(f"Video download error: {e}")
            # Try direct ffmpeg download as fallback
            return self._download_ffmpeg(url, output_path if 'output_path' in dir() else None)

    def _download_ffmpeg(self, url: str, output_path: str) -> Optional[str]:
        """Fallback download using ffmpeg"""
        try:
            # First get direct URL via yt-dlp (without downloading)
            cmd = ['yt-dlp', '-g', '--no-playlist', url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                video_url = result.stdout.strip().split('\n')[0]

                # Download with ffmpeg
                cmd = [
                    'ffmpeg', '-y',
                    '-i', video_url,
                    '-c', 'copy',
                    '-bsf:a', 'aac_adtstoasc',
                    output_path
                ]
                subprocess.run(cmd, capture_output=True, timeout=300)

                if os.path.exists(output_path):
                    return output_path

        except Exception as e:
            logger.error(f"FFmpeg download error: {e}")

        return None

    def cleanup(self):
        """Clean up temp files"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass


class AudioTranscriber:
    """Transcribe audio to text using Whisper"""

    def __init__(self, model: str = "base"):
        """
        Initialize transcriber

        Args:
            model: Whisper model size (tiny, base, small, medium, large)
        """
        self.model_name = model
        self.model = None

    def _load_model(self):
        """Load Whisper model on demand"""
        if self.model is None:
            try:
                import whisper
                self.model = whisper.load_model(self.model_name)
            except ImportError:
                logger.warning("OpenAI Whisper not installed. Install with: pip install openai-whisper")
                return None
        return self.model

    def transcribe(self, audio_path: str) -> Optional[Dict[str, Any]]:
        """
        Transcribe audio file to text

        Args:
            audio_path: Path to audio file

        Returns:
            Dict with 'text' and 'segments'
        """
        model = self._load_model()
        if model is None:
            return None

        try:
            result = model.transcribe(
                audio_path,
                language='zh',  # Prioritize Chinese
                task='transcribe',
                verbose=False
            )

            return {
                'text': result.get('text', '').strip(),
                'segments': result.get('segments', []),
                'language': result.get('language', 'zh')
            }

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None

    def transcribe_video(self, video_path: str, progress_callback: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
        """
        Extract audio from video and transcribe

        Args:
            video_path: Path to video file
            progress_callback: Optional progress callback

        Returns:
            Dict with 'text' and 'segments'
        """
        # Extract audio
        audio_path = self.extract_audio(video_path)
        if not audio_path:
            return None

        # Transcribe
        result = self.transcribe(audio_path)

        # Cleanup audio file
        try:
            os.remove(audio_path)
        except:
            pass

        return result

    def extract_audio(self, video_path: str) -> Optional[str]:
        """
        Extract audio from video file

        Args:
            video_path: Path to video file

        Returns:
            Path to audio file or None
        """
        audio_path = video_path.replace('.mp4', '.m4a')

        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'aac',
                '-b:a', '128k',
                '-ar', '16000',  # 16kHz for better recognition
                audio_path
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=120)

            if result.returncode == 0 and os.path.exists(audio_path):
                return audio_path

        except Exception as e:
            logger.error(f"Audio extraction error: {e}")

        return None


class TranscriptAnalyzer:
    """Analyze transcript using LLM"""

    def __init__(self):
        self.analyzer = None
        try:
            from ai_analyzer import AIAnalyzer
            self.analyzer = AIAnalyzer()
        except ImportError:
            logger.warning("AI Analyzer not available")

    def analyze(self, transcript: str, video_metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Analyze transcript and extract key information

        Args:
            transcript: Full transcript text
            video_metadata: Optional video metadata (title, author, etc.)

        Returns:
            Dict with summary, key_points, topics, etc.
        """
        if not self.analyzer:
            return {
                'summary': transcript[:500] if transcript else '',
                'key_points': [],
                'topics': [],
                'action_items': []
            }

        try:
            # 直接调用 DeepSeek API
            from openai import OpenAI
            import os
            from dotenv import load_dotenv

            load_dotenv()
            api_key = os.environ.get('DEEPSEEK_API_KEY')

            if not api_key:
                logger.warning("DEEPSEEK_API_KEY not found")
                return {
                    'summary': transcript[:500] if transcript else '',
                    'key_points': [],
                    'topics': [],
                    'action_items': []
                }

            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

            # 构建提示词
            prompt = self._create_analysis_prompt(transcript, video_metadata)

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一位专业的内容分析师，擅长从视频字幕中提取关键信息。请用中文分析并返回JSON格式结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            result_text = response.choices[0].message.content

            # 尝试解析JSON
            import json
            import re

            # 提取JSON部分
            json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return {
                        'summary': result.get('summary', ''),
                        'key_points': result.get('key_points', []),
                        'topics': result.get('topics', []),
                        'action_items': result.get('action_items', []),
                        'full_transcript': transcript
                    }
                except:
                    pass

            # 如果无法解析JSON，返回原始文本作为摘要
            return {
                'summary': result_text[:500] if result_text else transcript[:500],
                'key_points': [],
                'topics': [],
                'action_items': [],
                'full_transcript': transcript
            }

        except Exception as e:
            logger.error(f"Transcript analysis error: {e}")
            return {
                'summary': transcript[:500] if transcript else '',
                'key_points': [],
                'topics': [],
                'action_items': []
            }

    def _create_analysis_prompt(self, transcript: str, metadata: Optional[Dict] = None) -> str:
        """Create analysis prompt"""
        context = ""
        if metadata:
            if metadata.get('title'):
                context += f"视频标题: {metadata['title']}\n"
            if metadata.get('author'):
                context += f"作者: {metadata['author']}\n"

        prompt = f"""{context}
以下是这个视频的完整字幕内容，请进行分析并返回JSON格式的结果：

{transcript[:15000]}  # Limit to 15k chars

请返回JSON格式：
{{
    "summary": "视频内容摘要（200字以内）",
    "key_points": ["核心观点1", "核心观点2", "核心观点3"],
    "topics": ["话题1", "话题2", "话题3"],
    "action_items": ["可执行建议1", "可执行建议2"],
    "sentiment": "正面/中性/负面",
    "quality_score": 8.5
}}
"""
        return prompt


class KeyFrameExtractor:
    """Extract key frames from video"""

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()

    def extract(self, video_path: str, num_frames: int = 5, progress_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """
        Extract key frames from video

        Args:
            video_path: Path to video file
            num_frames: Number of key frames to extract
            progress_callback: Optional progress callback

        Returns:
            List of dicts with 'timestamp', 'image_path', 'description'
        """
        keyframes = []

        try:
            # Get video duration
            duration = self._get_duration(video_path)
            if not duration:
                return keyframes

            # Calculate frame intervals
            interval = duration / (num_frames + 1)

            for i in range(1, num_frames + 1):
                timestamp = interval * i
                output_path = os.path.join(
                    self.temp_dir,
                    f"frame_{int(timestamp)}_{int(time.time())}.jpg"
                )

                # Extract frame
                cmd = [
                    'ffmpeg', '-y',
                    '-ss', str(timestamp),
                    '-i', video_path,
                    '-vframes', '1',
                    '-q:v', '2',  # High quality
                    '-vf', 'scale=640:-1',  # Scale to width 640
                    output_path
                ]

                subprocess.run(cmd, capture_output=True, timeout=30)

                if os.path.exists(output_path):
                    keyframes.append({
                        'timestamp': timestamp,
                        'timestamp_formatted': self._format_time(timestamp),
                        'image_path': output_path,
                        'description': f"Frame at {self._format_time(timestamp)}"
                    })

                if progress_callback:
                    progress_callback(i / num_frames)

        except Exception as e:
            logger.error(f"Key frame extraction error: {e}")

        return keyframes

    def extract_scenes(self, video_path: str, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Extract scenes based on content change detection

        Args:
            video_path: Path to video file
            threshold: Scene change threshold (0-1)

        Returns:
            List of scene info dicts
        """
        scenes = []

        try:
            # Get video info
            duration = self._get_duration(video_path)
            if not duration:
                return scenes

            # Sample frames at regular intervals
            sample_interval = 2  # Sample every 2 seconds
            samples = []

            for t in range(0, int(duration), sample_interval):
                frame_path = os.path.join(self.temp_dir, f"sample_{t}.jpg")

                cmd = [
                    'ffmpeg', '-y',
                    '-ss', str(t),
                    '-i', video_path,
                    '-vframes', '1',
                    '-q:v', '3',
                    '-vf', 'scale=160:-1',  # Small thumbnail for comparison
                    frame_path
                ]

                subprocess.run(cmd, capture_output=True, timeout=30)

                if os.path.exists(frame_path):
                    samples.append({
                        'timestamp': t,
                        'path': frame_path
                    })

            # Compare adjacent frames to find scene changes
            if len(samples) > 1:
                from PIL import Image
                import math

                prev_hash = None
                for sample in samples:
                    if os.path.exists(sample['path']):
                        try:
                            img = Image.open(sample['path'])
                            # Simple perceptual hash
                            img = img.resize((16, 16)).convert('L')
                            pixels = list(img.getdata())
                            avg = sum(pixels) / len(pixels)
                            hash_val = ''.join('1' if p > avg else '0' for p in pixels)

                            # Check for scene change
                            if prev_hash is not None:
                                diff = sum(c1 != c2 for c1, c2 in zip(prev_hash, hash_val))
                                similarity = 1 - (diff / len(prev_hash))

                                if similarity < (1 - threshold):
                                    scenes.append({
                                        'timestamp': sample['timestamp'],
                                        'timestamp_formatted': self._format_time(sample['timestamp']),
                                        'change_detected': True
                                    })

                            prev_hash = hash_val

                        except Exception:
                            pass

        except Exception as e:
            logger.error(f"Scene extraction error: {e}")

        # Cleanup
        for sample in samples:
            try:
                if os.path.exists(sample['path']):
                    os.remove(sample['path'])
            except:
                pass

        return scenes

    def _get_duration(self, video_path: str) -> Optional[float]:
        """Get video duration in seconds"""
        try:
            cmd = [
                'ffmpeg', '-i', video_path,
                '-f', 'null',
                '-'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            # Parse duration from output
            match = re.search(r'Duration: (\d+):(\d+):(\d+\.?\d*)', result.stderr)
            if match:
                hours, mins, secs = match.groups()
                return float(hours) * 3600 + float(mins) * 60 + float(secs)

        except Exception:
            pass

        return None

    def _format_time(self, seconds: float) -> str:
        """Format seconds to MM:SS or HH:MM:SS"""
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    def cleanup(self):
        """Clean up temp files"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass


class VideoAnalysisService:
    """Complete video analysis service"""

    def __init__(self):
        self.downloader = VideoDownloader()
        self.transcriber = AudioTranscriber(model="base")
        self.analyzer = TranscriptAnalyzer()
        self.frame_extractor = KeyFrameExtractor()

    def analyze(self, url: str, enable_transcription: bool = True,
                enable_keyframes: bool = True, num_keyframes: int = 5,
                video_metadata: Optional[Dict] = None) -> VideoAnalysisResult:
        """
        Complete video analysis pipeline

        Args:
            url: Video URL
            enable_transcription: Whether to transcribe audio
            enable_keyframes: Whether to extract key frames
            num_keyframes: Number of key frames to extract
            video_metadata: Optional video metadata

        Returns:
            VideoAnalysisResult with all analysis data
        """
        start_time = time.time()
        result = VideoAnalysisResult(success=False)

        try:
            # Step 1: Download video
            logger.info("Downloading video...")
            video_path = self.downloader.download(url)

            if not video_path:
                # Fallback: Generate analysis from basic metadata if download fails
                logger.warning("Video download failed, using basic metadata analysis")
                result.success = True
                result.processing_time = time.time() - start_time

                # Create a basic result from metadata
                if video_metadata:
                    result.transcript = video_metadata.get('description', '')
                    result.summary = f"Video by {video_metadata.get('author', 'Unknown')}"
                    result.key_points = [video_metadata.get('description', '')[:200]] if video_metadata.get('description') else []

                return result

            result.video_path = video_path

            # Get video duration
            result.duration = self.frame_extractor._get_duration(video_path)

            # Step 2: Transcribe audio (if enabled)
            if enable_transcription:
                logger.info("Transcribing audio...")
                transcript_result = self.transcriber.transcribe_video(
                    video_path,
                    progress_callback=lambda p: logger.info(f"Transcription progress: {p:.0%}")
                )

                if transcript_result:
                    result.transcript = transcript_result.get('text', '')
                    result.transcript_segments = transcript_result.get('segments', [])

                    # Step 3: Analyze transcript
                    logger.info("Analyzing transcript...")
                    analysis = self.analyzer.analyze(
                        result.transcript,
                        video_metadata
                    )

                    result.summary = analysis.get('summary', '')
                    result.key_points = analysis.get('key_points', [])
                    result.topics = analysis.get('topics', [])

            # Step 4: Extract key frames (if enabled)
            if enable_keyframes:
                logger.info("Extracting key frames...")
                result.key_frames = self.frame_extractor.extract(
                    video_path,
                    num_frames=num_keyframes
                )

            result.success = True

        except Exception as e:
            logger.error(f"Video analysis error: {e}")
            result.error = str(e)

        finally:
            result.processing_time = time.time() - start_time
            # Cleanup
            try:
                if result.video_path and os.path.exists(result.video_path):
                    os.remove(result.video_path)
            except:
                pass

        return result

    def cleanup(self):
        """Cleanup all temp resources"""
        self.downloader.cleanup()
        self.frame_extractor.cleanup()


# Convenience function
def analyze_video(url: str, **kwargs) -> VideoAnalysisResult:
    """
    Analyze a video URL

    Args:
        url: Video URL
        **kwargs: Additional arguments for VideoAnalysisService.analyze()

    Returns:
        VideoAnalysisResult
    """
    service = VideoAnalysisService()
    try:
        return service.analyze(url, **kwargs)
    finally:
        service.cleanup()


if __name__ == "__main__":
    # Test
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        url = sys.argv[1]
        result = analyze_video(url)

        print("\n" + "="*60)
        print("VIDEO ANALYSIS RESULT")
        print("="*60)
        print(f"Success: {result.success}")
        print(f"Duration: {result.duration}")
        print(f"Processing time: {result.processing_time:.1f}s")

        if result.transcript:
            print(f"\nTranscript length: {len(result.transcript)} chars")
            print(f"Transcript preview: {result.transcript[:200]}...")

        if result.summary:
            print(f"\nSummary: {result.summary}")

        if result.key_points:
            print(f"\nKey Points ({len(result.key_points)}):")
            for i, point in enumerate(result.key_points, 1):
                print(f"  {i}. {point}")

        if result.topics:
            print(f"\nTopics: {', '.join(result.topics)}")

        if result.key_frames:
            print(f"\nKey Frames ({len(result.key_frames)}):")
            for frame in result.key_frames:
                print(f"  - {frame['timestamp_formatted']}: {frame['image_path']}")

        if result.error:
            print(f"\nError: {result.error}")

        print("="*60)
