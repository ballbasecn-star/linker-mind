"""
Twitter Processor Module - Extract tweet content using nitter instances

Nitter is a free/open-source alternative Twitter front-end that allows
accessing Twitter content without authentication or API keys.
"""
import re
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from url_detector import URLInfo, URLType
from content_processor import ContentProcessor, ProcessedContent


@dataclass
class TweetInfo:
    """Container for tweet information"""
    id: str
    username: str
    display_name: str
    content: str
    created_at: str
    images: List[str]
    videos: List[str]
    likes: int
    retweets: int
    replies: int
    url: str


class NitterInstance:
    """Represents a nitter instance with fallback support"""

    # Public nitter instances (as of 2025)
    INSTANCES = [
        "https://nitter.net",
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
        "https://nitter.1d4.us",
        "https://nitter.kavin.rocks",
    ]

    def __init__(self, instances: Optional[List[str]] = None):
        """Initialize with custom or default instances"""
        self.instances = instances or self.INSTANCES.copy()
        self.working_instances = []

    def get_working_instance(self) -> Optional[str]:
        """Get a working nitter instance"""
        # Try cached working instances first
        for instance in self.working_instances:
            if self._check_instance(instance):
                return instance

        # Try all instances
        for instance in self.instances:
            if self._check_instance(instance):
                self.working_instances.append(instance)
                return instance

        return None

    def _check_instance(self, instance: str) -> bool:
        """Check if instance is accessible"""
        try:
            response = requests.get(
                instance,
                timeout=10,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            return response.status_code == 200
        except:
            return False

    def convert_url(self, twitter_url: str) -> Optional[str]:
        """Convert Twitter/X URL to nitter URL"""
        # Extract tweet ID and username
        tweet_info = self._parse_twitter_url(twitter_url)
        if not tweet_info:
            return None

        instance = self.get_working_instance()
        if not instance:
            return None

        return f"{instance}/{tweet_info['username']}/status/{tweet_info['id']}"

    def _parse_twitter_url(self, url: str) -> Optional[Dict[str, str]]:
        """Parse Twitter URL to extract username and tweet ID"""
        patterns = [
            r'https?://(?:www\.)?twitter\.com/([^/]+)/status/(\d+)',
            r'https?://(?:www\.)?x\.com/([^/]+)/status/(\d+)',
        ]

        for pattern in patterns:
            match = re.match(pattern, url)
            if match:
                return {
                    'username': match.group(1),
                    'id': match.group(2)
                }

        return None


class TwitterProcessor(ContentProcessor):
    """
    Extract Twitter/X tweet content using nitter instances

    This processor:
    1. Converts Twitter/X URLs to nitter URLs
    2. Falls back through multiple nitter instances
    3. Parses tweet content, author, media, and engagement stats
    """

    def __init__(self):
        super().__init__()
        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "requests or beautifulsoup4 is not installed. "
                "Install with: pip install requests beautifulsoup4"
            )

        self.nitter = NitterInstance()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36'
        })

    def can_process(self, url_info: URLInfo) -> bool:
        """Can process Twitter/X URLs"""
        return url_info.url_type == URLType.TWITTER

    def extract(self, url_info: URLInfo) -> ProcessedContent:
        """
        Extract tweet content using nitter

        Args:
            url_info: URL information from URLDetector

        Returns:
            ProcessedContent with tweet data
        """
        self._start_timer()
        result = self._create_base_content(url_info)

        try:
            # Convert to nitter URL
            nitter_url = self.nitter.convert_url(url_info.url)
            if not nitter_url:
                raise Exception("Could not convert to nitter URL")

            # Fetch tweet page
            tweet_info = self._fetch_tweet(nitter_url)

            # Build content structure
            result.content = {
                "title": f"@{tweet_info.username}: {tweet_info.content[:50]}...",
                "url": url_info.url,
                "main_content": self._build_main_content(tweet_info),
                "summary": tweet_info.content[:200] + "..." if len(tweet_info.content) > 200 else tweet_info.content,
                "metadata": {
                    "platform": "twitter",
                    "author": f"@{tweet_info.username}",
                    "display_name": tweet_info.display_name,
                    "publish_date": tweet_info.created_at,
                    "tweet_id": tweet_info.id,
                    "likes": tweet_info.likes,
                    "retweets": tweet_info.retweets,
                    "replies": tweet_info.replies,
                    "url": url_info.url,
                    "nitter_url": nitter_url,
                    "tags": []
                }
            }

            # Media info
            result.media = {
                "type": "mixed" if (tweet_info.images or tweet_info.videos) else "text",
                "images": tweet_info.images,
                "videos": tweet_info.videos,
                "screenshots": []
            }

            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": True,
                "errors": [],
                "nitter_instance": nitter_url.split('/')[2]
            })

        except Exception as e:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [str(e)]
            })
            raise

        return result

    def _fetch_tweet(self, nitter_url: str) -> TweetInfo:
        """Fetch tweet page and extract information"""
        response = self.session.get(nitter_url, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract tweet ID from URL
        tweet_id = nitter_url.split('/')[-1]

        # Extract username and display name
        username = ""
        display_name = ""
        username_elem = soup.select_one('.username a')
        if username_elem:
            username = username_elem.text.strip().lstrip('@')

        name_elem = soup.select_one('.fullname')
        if name_elem:
            display_name = name_elem.text.strip()

        # Extract tweet content
        content = ""
        content_elem = soup.select_one('.tweet-content')
        if content_elem:
            content = content_elem.get_text(strip=True)

        # Extract date
        created_at = ""
        date_elem = soup.select_one('.tweet-date')
        if date_elem:
            created_at = date_elem.get('title', '')

        # Extract images
        images = []
        for img in soup.select('.tweet-media img, .gallery-item img'):
            src = img.get('src', '')
            if src and not src.startswith('data:'):
                # Remove size parameters for full quality
                images.append(src.split(':')[0].replace('/thumb', '/pic'))

        # Extract videos
        videos = []
        for video in soup.select('video source'):
            src = video.get('src', '')
            if src:
                videos.append(src)

        # Extract engagement stats
        likes = 0
        retweets = 0
        replies = 0

        # Try various selectors for stats (nitter UI changes)
        stats_container = soup.select_one('.tweet-stats')
        if stats_container:
            # Likes
            like_elem = stats_container.select_one('.icon-heart + span, .likes-count')
            if like_elem:
                likes = self._parse_count(like_elem.text)

            # Retweets
            retweet_elem = stats_container.select_one('.icon-retweet + span, .retweets-count')
            if retweet_elem:
                retweets = self._parse_count(retweet_elem.text)

            # Replies
            reply_elem = stats_container.select_one('.icon-comment + span, .comments-count')
            if reply_elem:
                replies = self._parse_count(reply_elem.text)

        return TweetInfo(
            id=tweet_id,
            username=username,
            display_name=display_name,
            content=content,
            created_at=created_at,
            images=images,
            videos=videos,
            likes=likes,
            retweets=retweets,
            replies=replies,
            url=nitter_url
        )

    def _parse_count(self, text: str) -> int:
        """Parse count string like '1.2K' to integer"""
        text = text.strip().replace(',', '')
        multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}

        for suffix, mult in multipliers.items():
            if text.upper().endswith(suffix):
                try:
                    return int(float(text[:-1]) * mult)
                except:
                    return 0

        try:
            return int(text)
        except:
            return 0

    def _build_main_content(self, tweet_info: TweetInfo) -> str:
        """Build main content string from tweet info"""
        parts = []

        parts.append(f"# Tweet by @{tweet_info.username}")

        if tweet_info.display_name:
            parts.append(f"**{tweet_info.display_name}** (@{tweet_info.username})")
        else:
            parts.append(f"@{tweet_info.username}")

        parts.append("")  # Empty line

        if tweet_info.content:
            parts.append(f"## Content\n\n{tweet_info.content}\n")

        if tweet_info.created_at:
            parts.append(f"**Posted:** {tweet_info.created_at}\n")

        parts.append("## Stats\n\n")
        parts.append(f"- ❤️ Likes: {tweet_info.likes:,}")
        parts.append(f"- 🔄 Retweets: {tweet_info.retweets:,}")
        parts.append(f"- 💬 Replies: {tweet_info.replies:,}")

        if tweet_info.images:
            parts.append(f"\n## Media\n\n{len(tweet_info.images)} image(s)")

        if tweet_info.videos:
            parts.append(f"\n## Video\n\n{len(tweet_info.videos)} video(s)")

        return "\n".join(parts)


# Test function
def test_twitter_extraction():
    """Test Twitter extraction with sample URLs"""
    test_urls = [
        "https://twitter.com/anthropic/status/1700000000000000000",  # Example
        "https://x.com/elonmusk/status/1700000000000000000",  # Example
    ]

    processor = TwitterProcessor()

    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"Testing: {url}")
        print(f"{'='*60}")

        try:
            from url_detector import detect_url
            url_info = detect_url(url)

            if processor.can_process(url_info):
                content = processor.extract(url_info)

                print(f"✅ Success!")
                print(f"Author: {content.content.get('metadata', {}).get('author')}")
                print(f"Content: {content.content.get('summary')}")
                print(f"Likes: {content.content.get('metadata', {}).get('likes')}")
            else:
                print(f"❌ Cannot process this URL type")

        except Exception as e:
            print(f"❌ Failed: {e}")


if __name__ == "__main__":
    test_twitter_extraction()
