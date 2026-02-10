"""
Douyin Processor Module - Extract content from Douyin (TikTok China) videos

Features:
- Basic extraction: title, description, stats, cover image
- Deep video analysis: transcript, LLM analysis, key frames
"""
import re
import json
import time
import os
from typing import Optional, Dict, Any, List

from content_processor import ContentProcessor, ProcessedContent
from url_detector import URLInfo


class DouyinProcessor(ContentProcessor):
    """
    Processor for Douyin (抖音) video content
    Uses requests + BeautifulSoup as primary extraction method
    Supports deep video analysis with transcription and LLM
    """

    def __init__(self):
        super().__init__()
        # Try to import required dependencies
        try:
            import requests
            from bs4 import BeautifulSoup
            self.requests = requests
            self.bs4 = BeautifulSoup
            self.requests_available = True
        except ImportError:
            self.requests_available = False

        # Check if MCP WebReader is available
        self.mcp_webreader_available = False
        self.mcp_webreader = None

        # Video analysis service (lazy load)
        self._video_analysis_service = None

    def set_mcp_tools(self, mcp_webreader):
        """Set MCP WebReader tool if available"""
        self.mcp_webreader = mcp_webreader
        self.mcp_webreader_available = mcp_webreader is not None

    def _get_video_analysis_service(self):
        """Get or create video analysis service"""
        if self._video_analysis_service is None:
            try:
                from services.video_analysis_service import VideoAnalysisService
                self._video_analysis_service = VideoAnalysisService()
            except ImportError:
                pass
        return self._video_analysis_service

    def can_process(self, url_info: URLInfo) -> bool:
        """Can process Douyin URLs"""
        return url_info.url_type.value == "douyin"

    def extract(self, url_info: URLInfo, deep_analysis: bool = False) -> ProcessedContent:
        """Extract Douyin video content

        Args:
            url_info: URL info object
            deep_analysis: If True, perform full video analysis with transcription
                          (requires yt-dlp and whisper installed)
        """
        self._start_timer()
        result = self._create_base_content(url_info)

        # Expand short URL first
        expanded_url = self._expand_short_url(url_info.url)
        if expanded_url != url_info.url:
            result.processing_info["url_expanded"] = True
            result.processing_info["original_url"] = url_info.url

        try:
            # Priority: MCP WebReader > requests (primary for Douyin)
            content = None

            # Try MCP WebReader first if available (better for dynamic content)
            if self.mcp_webreader_available:
                try:
                    content = self._extract_with_mcp(expanded_url)
                    result.processing_info["extraction_method"] = "mcp_webreader"
                except Exception as e:
                    result.processing_info["mcp_error"] = str(e)

            # Fall back to requests + BeautifulSoup
            if not content and self.requests_available:
                content = self._extract_with_requests(expanded_url)
                result.processing_info["extraction_method"] = "requests"

            # Final fallback to Firecrawl
            if not content:
                content = self._extract_with_firecrawl(expanded_url)
                result.processing_info["extraction_method"] = "firecrawl"

            # Update result with extracted content
            result.content.update(content)
            result.media = self._build_media_info(content)

            # Deep video analysis (if requested)
            if deep_analysis:
                video_analysis = self._perform_deep_analysis(expanded_url, content)
                if video_analysis:
                    result.content['transcript'] = video_analysis.get('transcript', '')
                    result.content['transcript_summary'] = video_analysis.get('summary', '')
                    result.content['key_points'] = video_analysis.get('key_points', [])
                    result.processing_info['video_analysis'] = video_analysis
                    result.processing_info['deep_analysis'] = True

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

    def _perform_deep_analysis(self, url: str, basic_content: Dict) -> Optional[Dict]:
        """Perform deep video analysis with transcription and LLM

        Args:
            url: Video URL
            basic_content: Basic extracted content

        Returns:
            Dict with transcript, summary, key_points, key_frames, etc.
        """
        video_service = self._get_video_analysis_service()
        if not video_service:
            self.processing_info = getattr(self, 'processing_info', {})
            self.processing_info['deep_analysis_warning'] = 'VideoAnalysisService not available'
            return None

        try:
            # Get video metadata for LLM analysis
            metadata = {
                'title': basic_content.get('title', ''),
                'author': basic_content.get('metadata', {}).get('author', ''),
                'description': basic_content.get('metadata', {}).get('description', '')
            }

            # Perform full analysis
            result = video_service.analyze(
                url=url,
                enable_transcription=True,
                enable_keyframes=True,
                num_keyframes=5,
                video_metadata=metadata
            )

            if not result.success:
                return None

            # Build response
            analysis = {
                'transcript': result.transcript or '',
                'transcript_length': len(result.transcript) if result.transcript else 0,
                'summary': result.summary or '',
                'key_points': result.key_points or [],
                'topics': result.topics or [],
                'duration': result.duration,
                'duration_formatted': self._format_duration(result.duration * 1000) if result.duration else '',
                'key_frames': []
            }

            # Add key frames info (but not actual images to avoid large data)
            if result.key_frames:
                analysis['key_frames'] = [
                    {
                        'timestamp': frame['timestamp'],
                        'timestamp_formatted': frame['timestamp_formatted'],
                        'description': frame['description']
                    }
                    for frame in result.key_frames
                ]

            # Add statistics from basic content
            if basic_content.get('metadata'):
                analysis['stats'] = {
                    'likes': basic_content['metadata'].get('likes', 0),
                    'comments': basic_content['metadata'].get('comments', 0),
                    'shares': basic_content['metadata'].get('shares', 0)
                }

            analysis['processing_time'] = result.processing_time

            return analysis

        except Exception as e:
            logger.error(f"Deep video analysis error: {e}")
            return None

    def _format_duration(self, milliseconds: int) -> str:
        """Format duration from milliseconds to MM:SS"""
        if not milliseconds:
            return "00:00"
        seconds = milliseconds // 1000
        minutes, secs = divmod(seconds, 60)
        return f"{int(minutes):02d}:{int(secs):02d}"

    def _expand_short_url(self, url: str) -> str:
        """Expand short Douyin URL to full URL"""
        if not self.requests_available:
            return url

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }

            # Use allow_redirects=True to follow redirects and get final URL
            response = self.requests.head(url, headers=headers, timeout=5, allow_redirects=True)
            final_url = response.url

            # Validate it's a douyin URL
            if 'douyin.com' in final_url:
                return final_url

            return url
        except Exception:
            return url

    def _extract_with_mcp(self, url: str) -> Dict[str, Any]:
        """Extract using MCP WebReader"""
        if not self.mcp_webreader:
            raise ValueError("MCP WebReader not available")

        result = self.mcp_webreader(
            url=url,
            return_format="markdown",
            timeout=30,
            retain_images=True
        )

        # Parse the markdown content
        markdown = result.markdown if hasattr(result, 'markdown') else str(result)

        return {
            "title": getattr(result, 'title', '') or "抖音视频",
            "url": url,
            "main_content": markdown,
            "html": getattr(result, 'html', '') if hasattr(result, 'html') else '',
            "metadata": {
                "platform": "douyin",
                "author": self._extract_author(markdown, ""),
                "description": self._extract_description(markdown),
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "tags": self._extract_tags(markdown),
                "publish_date": "",
                "video_id": self._extract_video_id(url)
            }
        }

    def _extract_with_firecrawl(self, url: str) -> Dict[str, Any]:
        """Extract using Firecrawl API"""
        # Check if Firecrawl is available
        try:
            from firecrawl import Firecrawl
            import os
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("FIRECRAWL_API_KEY")
            if not api_key:
                raise ValueError("FIRECRAWL_API_KEY not configured")
            firecrawl = Firecrawl(api_key=api_key)
        except Exception as e:
            raise ValueError(f"Firecrawl not available: {e}")

        scrape_result = firecrawl.scrape(
            url,
            formats={'markdown': True, 'html': True},
            only_main_content=True,
            wait_for=3000,  # Douyin may need more time to load
            headers={
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
            }
        )

        # Extract metadata from scraped content
        title = getattr(scrape_result, 'title', '') or "抖音视频"
        markdown = getattr(scrape_result, 'markdown', '')
        html = getattr(scrape_result, 'html', '')

        # Try to extract additional info from HTML/markdown
        author = self._extract_author(markdown, html)
        description = self._extract_description(markdown)
        likes = self._extract_stats(markdown, 'likes')
        comments = self._extract_stats(markdown, 'comments')

        return {
            "title": title,
            "url": url,
            "main_content": markdown,
            "html": html,
            "metadata": {
                "platform": "douyin",
                "author": author,
                "description": description,
                "likes": likes,
                "comments": comments,
                "shares": self._extract_stats(markdown, 'shares'),
                "tags": self._extract_tags(markdown),
                "publish_date": "",
                "video_id": self._extract_video_id(url)
            },
            "extracted_data": {
                "source": "firecrawl"
            }
        }

    def _extract_with_requests(self, url: str) -> Dict[str, Any]:
        """Extract using requests + BeautifulSoup (primary method for Douyin)"""
        if not self.requests_available:
            raise ValueError("requests not available")

        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }

        response = self.requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = self.bs4(response.content, 'html.parser')

        # Try to extract from script tags (Douyin stores data in JSON)
        script_data = self._extract_script_data(soup)

        title = script_data.get('title', '') or soup.find('title')
        title = title.text if hasattr(title, 'text') else str(title)

        # Extract video ID from URL
        video_id = self._extract_video_id(url)

        # Extract complete description/caption
        desc = script_data.get('desc', '') or ""

        # Extract author info
        author_info = script_data.get('author', {}) or {}
        author_name = author_info.get('nickname', '') or author_info.get('unique_id', '') or ""

        # Extract statistics
        stats = script_data.get('statistics', {}) or {}
        digg_count = stats.get('digg_count', 0)  # likes
        comment_count = stats.get('comment_count', 0)
        share_count = stats.get('share_count', 0)

        # Extract video cover image
        video_resource = script_data.get('video', {}) or {}
        cover_url = ""
        if isinstance(video_resource, dict):
            cover_url = video_resource.get('cover', {}).get('url_list', [''])[0] if isinstance(video_resource.get('cover'), dict) else ''
        if not cover_url:
            # Try to find from page
            cover_img = soup.find('img', {'class': 'poster'})
            if cover_img:
                cover_url = cover_img.get('src', '') or cover_img.get('srcset', '').split()[0] if cover_img.get('srcset') else ''

        # Extract video URL (for downloading if needed)
        video_play_url = ""
        if isinstance(video_resource, dict):
            video_play_url = video_resource.get('play_addr', {}).get('url_list', [''])[0] if isinstance(video_resource.get('play_addr'), dict) else ''

        # Extract hashtags
        text_extras = script_data.get('text_extra', []) or []
        hashtags = []
        for extra in text_extras:
            if isinstance(extra, dict) and extra.get('type') == 1:  # hashtag
                hashtag = extra.get('hashtag_name', '')
                if hashtag:
                    hashtags.append(f"#{hashtag}")

        # Build complete caption
        complete_caption = desc
        if hashtags:
            complete_caption += "\n\n" + " ".join(hashtags)

        # Extract duration if available
        duration = 0
        if isinstance(video_resource, dict):
            duration = video_resource.get('duration', 0)  # in milliseconds

        return {
            "title": title or "抖音视频",
            "url": url,
            "main_content": complete_caption,
            "html": str(soup),
            "metadata": {
                "platform": "douyin",
                "author": author_name,
                "author_id": author_info.get('uid', ''),
                "description": desc,
                "likes": digg_count,
                "comments": comment_count,
                "shares": share_count,
                "tags": hashtags,
                "hashtags": hashtags,
                "publish_date": "",
                "video_id": video_id,
                "duration": duration,
                "duration_formatted": self._format_duration(duration) if duration else ""
            },
            "extracted_data": {
                "source": "requests",
                "raw_data": script_data,
                "cover_image": cover_url,
                "video_url": video_play_url,
                "view_count": stats.get('view_count', 0),  # 播放量
                "digg_count": digg_count,  # 点赞
                "collect_count": stats.get('collect_count', 0),  # 收藏
            }
        }

    def _format_duration(self, milliseconds: int) -> str:
        """Format duration from milliseconds to MM:SS"""
        if not milliseconds:
            return "00:00"
        seconds = milliseconds // 1000
        minutes, secs = divmod(seconds, 60)
        return f"{int(minutes):02d}:{int(secs):02d}"

    def _extract_author(self, markdown: str, html: str) -> str:
        """Extract author name from content"""
        # Try various patterns
        patterns = [
            r'@([^\s@]+)',
            r'作者[：:]\s*([^\n@]+)',
            r'Author[：:]\s*([^\n@]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, markdown[:2000])  # Search in first 2000 chars
            if match:
                return match.group(1).strip()
        return ""

    def _extract_description(self, markdown: str) -> str:
        """Extract video description"""
        # Usually the first paragraph or line
        lines = markdown.split('\n')
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('!'):
                return line[:500]
        return ""

    def _extract_stats(self, markdown: str, stat_type: str) -> int:
        """Extract engagement statistics"""
        patterns = {
            'likes': r'(\d+(?:\.\d+)?[kKwW万]?)\s*(?:点赞|likes?|like)',
            'comments': r'(\d+(?:\.\d+)?[kKwW万]?)\s*(?:评论|comments?)',
            'shares': r'(\d+(?:\.\d+)?[kKwW万]?)\s*(?:分享|转发|shares?)',
        }

        pattern = patterns.get(stat_type, '')
        if not pattern:
            return 0

        match = re.search(pattern, markdown, re.IGNORECASE)
        if match:
            num_str = match.group(1)
            return self._parse_number(num_str)
        return 0

    def _parse_number(self, num_str: str) -> int:
        """Parse number with k/w/万 suffix"""
        num_str = num_str.lower().strip()
        multipliers = {
            'k': 1000,
            'w': 10000,
            '万': 10000,
        }

        for suffix, mult in multipliers.items():
            if num_str.endswith(suffix):
                try:
                    return int(float(num_str[:-1]) * mult)
                except ValueError:
                    return 0

        try:
            return int(float(num_str))
        except ValueError:
            return 0

    def _extract_tags(self, markdown: str) -> list:
        """Extract hashtags from content"""
        hashtag_pattern = r'#([^\s#]+)'
        tags = re.findall(hashtag_pattern, markdown)
        return tags[:10]  # Limit to 10 tags

    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from URL"""
        match = re.search(r'/video/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'/note/(\d+)', url)
        if match:
            return match.group(1)
        return ""

    def _extract_script_data(self, soup) -> Dict[str, Any]:
        """Extract JSON data from script tags - Enhanced for Douyin"""
        result = {}

        # Method 1: Look for window._ROUTER_DATA (current Douyin format)
        for script in soup.find_all('script'):
            if script.string and 'window._ROUTER_DATA' in script.string:
                try:
                    # Find the JSON start and end positions
                    start = script.string.find('window._ROUTER_DATA = ') + len('window._ROUTER_DATA = ')
                    json_str = script.string[start:]
                    brace_count = 0
                    for i, c in enumerate(json_str):
                        if c == '{':
                            brace_count += 1
                        elif c == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end = start + i + 1
                                break
                    else:
                        end = start + 10000  # fallback limit

                    json_str = script.string[start:end].strip()
                    if json_str.endswith(';'):
                        json_str = json_str[:-1]

                    # Fix escaped unicode
                    json_str = json_str.replace('\\u002F', '/')

                    data = json.loads(json_str)
                    if data and 'loaderData' in data:
                        ld = data['loaderData']
                        # Navigate to video data
                        for key, value in ld.items():
                            if isinstance(value, dict) and 'videoInfoRes' in value:
                                vi_res = value['videoInfoRes']
                                if isinstance(vi_res, dict) and 'item_list' in vi_res:
                                    item_list = vi_res['item_list']
                                    if isinstance(item_list, list) and len(item_list) > 0:
                                        item = item_list[0]
                                        if isinstance(item, dict):
                                            # Extract video data
                                            video = item.get('video', {})
                                            return {
                                                'desc': item.get('desc', ''),
                                                'aweme_id': item.get('aweme_id', ''),
                                                'create_time': item.get('create_time', 0),
                                                'video': {
                                                    'duration': video.get('duration', 0),
                                                    'cover': video.get('cover', {}),
                                                    'play_addr': video.get('play_addr', {})
                                                },
                                                'author': item.get('author', {}),
                                                'statistics': item.get('statistics', {}),
                                                'text_extra': item.get('text_extra', [])
                                            }
                except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                    pass

        # Method 2: Look for window.__INITIAL_STATE__
        for script in soup.find_all('script'):
            if script.string and 'window.__INITIAL_STATE__' in script.string:
                try:
                    match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', script.string)
                    if match:
                        result = json.loads(match.group(1))
                        if result:
                            return result
                except (json.JSONDecodeError, ValueError):
                    pass

        # Method 3: Look for RENDER_DATA or __NEXT_DATA__ (Next.js)
        for script in soup.find_all('script'):
            if script.string:
                # Look for Next.js data
                if '__NEXT_DATA__' in script.string:
                    try:
                        match = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.+?)</script>', script.string, re.DOTALL)
                        if match:
                            next_data = json.loads(match.group(1))
                            if 'props' in next_data and 'pageProps' in next_data['props']:
                                # Try to find video data in pageProps
                                page_props = next_data['props']['pageProps']
                                if 'video' in page_props:
                                    return {'video': page_props['video']}
                                if 'initialState' in page_props:
                                    return page_props['initialState']
                    except Exception:
                        pass

                # Look for RENDER_DATA (older Douyin format)
                if 'window.__RENDER_DATA__' in script.string:
                    try:
                        match = re.search(r'window\.__RENDER_DATA__\s*=\s*(.+?)(?:;|</script>)', script.string)
                        if match:
                            data = json.loads(match.group(1))
                            if isinstance(data, dict):
                                return data
                    except Exception:
                        pass

        # Method 4: Look for any JSON-LD or structured data
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                ld_data = json.loads(script.string)
                if isinstance(ld_data, dict):
                    # Look for VideoObject
                    if ld_data.get('@type') == 'VideoObject':
                        return {
                            'title': ld_data.get('name'),
                            'desc': ld_data.get('description'),
                            'author': ld_data.get('author', {}).get('name'),
                            'video': {
                                'duration': ld_data.get('duration'),  # ISO 8601 format
                                'thumbnailUrl': ld_data.get('thumbnailUrl')
                            }
                        }
            except Exception:
                pass

        # Method 5: Look for data in any script tag with video-related content
        for script in soup.find_all('script'):
            if script.string:
                # Look for videoId, desc, digg_count patterns
                try:
                    # Try to find JSON object with video data
                    json_matches = re.findall(r'(\{[^{}]*(?:videoId|desc|digg_count|comment_count)[^{}]*\})', script.string)
                    for json_str in json_matches:
                        try:
                            data = json.loads(json_str)
                            if 'desc' in data or 'videoId' in data:
                                return data
                        except json.JSONDecodeError:
                            continue
                except Exception:
                    pass

        # Method 6: Extract from HTML meta tags as fallback
        meta_data = {}

        # Title
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.string or ''
            # Remove common suffixes
            meta_data['title'] = re.sub(r'\s*[-_]\s*抖音\s*$', '', title_text).strip()

        # Description from og:description or twitter:description
        for meta_name in ['og:description', 'twitter:description', 'description']:
            meta_tag = soup.find('meta', attrs={'name': meta_name})
            if meta_tag and meta_tag.get('content'):
                meta_data['desc'] = meta_tag.get('content')
                break

        # Author from og:video:tag or other meta
        author_tag = soup.find('meta', attrs={'name': 'author'})
        if author_tag:
            meta_data['author'] = {'nickname': author_tag.get('content')}

        # Video cover from og:image
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image:
            meta_data['video'] = {'cover': {'url_list': [og_image.get('content', '')]}}

        return meta_data

    def _build_media_info(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Build media information from content"""
        media = {
            "type": "video",
            "cover_image": "",
            "images": [],
            "videos": [],
            "thumbnails": [],
            "video_data": {}
        }

        # Extract from extracted_data first (more reliable for Douyin)
        extracted_data = content.get("extracted_data", {})
        if extracted_data:
            # Cover image from page data
            cover_url = extracted_data.get("cover_image", "")
            if cover_url:
                media["cover_image"] = cover_url
                media["thumbnails"] = [cover_url]

            # Video URL if available
            video_url = extracted_data.get("video_url", "")
            if video_url:
                media["videos"] = [video_url]
                media["video_data"] = {
                    "url": video_url,
                    "view_count": extracted_data.get("view_count", 0),
                    "digg_count": extracted_data.get("digg_count", 0),
                    "collect_count": extracted_data.get("collect_count", 0)
                }

        # Fallback: extract images from markdown
        if not media["thumbnails"]:
            markdown = content.get("main_content", "")
            img_pattern = r'!\[.*?\]\((.*?)\)'
            images = re.findall(img_pattern, markdown)
            media["images"] = images[:10]
            media["thumbnails"] = images[:5]

        return media
