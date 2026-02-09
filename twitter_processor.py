"""
Twitter Processor Module - Extract tweet content using Tavily API

This module uses Tavily's extract endpoint to fetch Twitter/X tweet content.
Tavily is a real-time search API optimized for AI/LLM applications.

API Documentation: https://docs.tavily.com/documentation/api-reference/endpoint/extract
"""
import re
import os
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

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
    quotes: int
    views: int
    url: str


class TwitterProcessor(ContentProcessor):
    """
    Extract Twitter/X tweet content using Tavily API

    This processor:
    1. Uses Tavily's extract endpoint to fetch tweet content
    2. Parses the markdown/HTML output to extract tweet data
    3. Works without Twitter accounts or API keys
    4. Requires TAVILY_API_KEY environment variable

    Get your API key at: https://tavily.com/
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize TwitterProcessor

        Args:
            api_key: Optional Tavily API key (default: from TAVILY_API_KEY env var)
        """
        super().__init__()
        if not TAVILY_AVAILABLE:
            raise ImportError(
                "tavily-python is not installed. "
                "Install with: pip install tavily-python"
            )

        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError(
                "TAVILY_API_KEY not found. Please:\n"
                "1. Get an API key at https://tavily.com/\n"
                "2. Set it as environment variable: export TAVILY_API_KEY=your_key\n"
                "3. Or add it to your .env file"
            )

        self.client = TavilyClient(api_key=self.api_key)

    def can_process(self, url_info: URLInfo) -> bool:
        """Can process Twitter/X URLs"""
        return url_info.url_type == URLType.TWITTER

    def extract(self, url_info: URLInfo) -> ProcessedContent:
        """
        Extract tweet content using Tavily API

        Args:
            url_info: URL information from URLDetector

        Returns:
            ProcessedContent with tweet data
        """
        self._start_timer()
        result = self._create_base_content(url_info)

        try:
            # Use Tavily extract endpoint
            response = self.client.extract(
                url_info.url,
                extract_depth="advanced",
                include_images=True,
                include_image_description=True,
            )

            # Parse the response
            tweet_info = self._parse_tavily_response(response, url_info.url)

            # Extract article title from content (for long-form articles)
            article_title = self._extract_article_title(tweet_info.content)

            # Embed images into content at appropriate positions
            content_with_images = self._embed_images_in_content(
                tweet_info.content,
                tweet_info.images
            )

            # Save complete raw content with embedded images (for template display)
            result.raw_content = content_with_images

            # Build processing_info with all the rich data
            # This will be saved as 'metadata' in the database
            result.processing_info = {
                "platform": "twitter",
                "author": f"@{tweet_info.username}",
                "display_name": tweet_info.display_name,
                "publish_date": tweet_info.created_at,
                "tweet_id": tweet_info.id,
                "metrics": {
                    "likes": tweet_info.likes,
                    "retweets": tweet_info.retweets,
                    "replies": tweet_info.replies,
                    "quotes": tweet_info.quotes,
                    "views": tweet_info.views
                },
                "cover_image": tweet_info.images[0] if tweet_info.images else None,
                "subtitle_text": f"By {tweet_info.display_name} (@{tweet_info.username})",
                # Also save images list to metadata for template access
                "images": tweet_info.images,
                "videos": tweet_info.videos
            }

            # Build content structure for display
            # Use full content with embedded images
            result.content = {
                "title": article_title or tweet_info.display_name or f"@{tweet_info.username}",
                "main_content": content_with_images,  # Full content with images embedded
                "summary": tweet_info.content[:200] + "..." if len(tweet_info.content) > 200 else tweet_info.content
            }

            # Media info - keep full image list, template will skip cover
            result.media = {
                "type": "mixed" if (tweet_info.images or tweet_info.videos) else "text",
                "cover": tweet_info.images[0] if tweet_info.images else None,
                "images": tweet_info.images,  # Keep full list, template will handle cover
                "videos": tweet_info.videos,
                "screenshots": []
            }

            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": True,
                "errors": [],
                "method": "tavily_api"
            })

        except Exception as e:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [str(e)]
            })
            raise

        return result

    def _parse_tavily_response(self, response: Dict[str, Any], url: str) -> TweetInfo:
        """Parse Tavily extract response to extract tweet information"""
        # Initialize with defaults
        tweet_info = TweetInfo(
            id="",
            username="",
            display_name="",
            content="",
            created_at="",
            images=[],
            videos=[],
            likes=0,
            retweets=0,
            replies=0,
            quotes=0,
            views=0,
            url=url
        )

        # Tavily returns data in 'results' array
        results = response.get("results", [])
        if results and len(results) > 0:
            first_result = results[0]

            # Extract title - format: "DisplayName on X: \"Tweet Content\" / X"
            title = first_result.get("title", "")
            if title:
                # Parse title to extract display name only
                display_name, _ = self._parse_title(title)
                if display_name:
                    tweet_info.display_name = display_name

            # Always extract from raw_content for full content (handles both short tweets and long-form articles)
            raw_content = first_result.get("raw_content", "")
            if raw_content:
                tweet_info.content = self._extract_tweet_text(raw_content)

            # Extract images - filter out profile pictures
            images = first_result.get("images", [])
            if isinstance(images, list):
                # Filter out profile pictures (they have profile_images in the URL)
                content_images = [img for img in images if 'profile_images' not in img]
                tweet_info.images = content_images

        # Also check for direct content field (some Tavily responses)
        if not tweet_info.content and "content" in response:
            tweet_info.content = response["content"]

        # Parse username from URL
        username_match = re.search(r'(?:twitter\.com|x\.com)/([^/]+)/status', url)
        if username_match:
            tweet_info.username = username_match.group(1)

        # Parse tweet ID from URL
        id_match = re.search(r'/status/(\d+)', url)
        if id_match:
            tweet_info.id = id_match.group(1)

        # Extract stats from raw content if available
        if results and len(results) > 0:
            raw_content = results[0].get("raw_content", "")
            if raw_content:
                # Extract all metrics (replies, retweets, quotes, likes, views)
                # Pattern: "30 56 258 37K" - replies, retweets, quotes, views
                # Or individual patterns
                metrics_patterns = [
                    (r'(\d+)\s+\d+\s+\d+\s+([\d\.]+[KM]?)', ['replies', 'retweets_quotes_views']),  # Combined pattern
                    (r'([\d,]+)\s*Repl(?:ies|y)', 'replies'),
                    (r'([\d,]+)\s*Retweets?', 'retweets'),
                    (r'([\d,]+)\s*Quotes?', 'quotes'),
                    (r'❤️\s*([\d,]+)', 'likes'),
                    (r'🔄\s*([\d,]+)', 'retweets'),
                    (r'([\d,]+)\s*Views?', 'views'),
                ]

                # Try to extract the compact metrics format first (e.g., "30 56 258 37K")
                compact_match = re.search(r'(\d+)\s+(\d+)\s+(\d+)\s+([\d\.]+[KM]?)', raw_content)
                if compact_match:
                    tweet_info.replies = int(compact_match.group(1))
                    tweet_info.retweets = int(compact_match.group(2))
                    tweet_info.quotes = int(compact_match.group(3))
                    tweet_info.views = self._parse_count(compact_match.group(4))

                # Extract individual metrics as fallback
                for pattern_info in metrics_patterns:
                    if isinstance(pattern_info, list):
                        continue  # Skip combined pattern
                    pattern, metric = pattern_info
                    match = re.search(pattern, raw_content, re.IGNORECASE)
                    if match:
                        value = self._parse_count(match.group(1))
                        if metric == 'replies' and tweet_info.replies == 0:
                            tweet_info.replies = value
                        elif metric == 'retweets' and tweet_info.retweets == 0:
                            tweet_info.retweets = value
                        elif metric == 'quotes' and tweet_info.quotes == 0:
                            tweet_info.quotes = value
                        elif metric == 'likes' and tweet_info.likes == 0:
                            tweet_info.likes = value
                        elif metric == 'views' and tweet_info.views == 0:
                            tweet_info.views = value

                # Extract date
                date_match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M\s*·\s*\w+\s+\d+)', raw_content)
                if date_match:
                    tweet_info.created_at = date_match.group(1)

        return tweet_info

    def _parse_title(self, title: str) -> Tuple[str, str]:
        """Parse Tavily title to extract display name and tweet content

        Title format: "DisplayName on X: \"Tweet Content\" / X"

        Returns:
            (display_name, content) tuple
        """
        display_name = ""
        content = ""

        # Remove " / X" suffix
        title = title.replace(" / X", "").strip()

        # Pattern: "DisplayName on X: \"Content\""
        # First, extract the part after " on X:"
        if " on X:" in title:
            parts = title.split(" on X:", 1)
            display_name = parts[0].strip()
            remaining = parts[1].strip()

            # Remove leading/trailing quotes from content
            if remaining.startswith('"') and remaining.endswith('"'):
                content = remaining[1:-1].strip()
            elif remaining.startswith('"'):
                content = remaining[1:].strip()
            else:
                content = remaining
        else:
            # Fallback: just use the title as display name
            display_name = title

        return display_name, content

    def _extract_article_title(self, content: str) -> Optional[str]:
        """Extract article title from tweet content for long-form articles

        For X/Twitter long-form articles, the title is usually:
        - The first line (if it's Chinese and ends with punctuation like 。)
        - Shorter than 100 characters
        - Not a URL or image link

        Returns:
            Article title or None if not found
        """
        if not content:
            return None

        lines = content.strip().split('\n')

        # Look for the first line that could be a title
        for i, line in enumerate(lines[:5]):  # Check first 5 lines only
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Skip image tags
            if stripped.startswith('<img') or 'pbs.twimg.com' in stripped:
                continue

            # Skip markdown headers
            if stripped.startswith('#'):
                # Remove # prefix and get the title
                title = stripped.lstrip('#').strip()
                if len(title) > 5 and len(title) < 200:
                    return title
                continue

            # Check if this looks like a title:
            # - Contains Chinese characters
            # - Ends with proper punctuation
            # - Reasonable length (10-100 chars)
            has_chinese = bool(re.search(r'[\u4e00-\u9fff]', stripped))
            ends_with_punct = bool(re.search(r'[。！？\.!?]$', stripped))
            reasonable_length = 10 < len(stripped) < 100

            if has_chinese and (ends_with_punct or reasonable_length):
                # This is likely the title
                return stripped

            # For non-Chinese content, look for short first line
            if not has_chinese and reasonable_length and i == 0:
                return stripped

        return None

    def _extract_tweet_text(self, raw_content: str) -> str:
        """Extract tweet text from raw HTML/markdown content

        Handles both regular tweets and long-form Articles
        Preserves inline images for proper display
        Skips title and metrics that are displayed separately
        """
        if not raw_content:
            return ""

        lines = raw_content.split('\n')
        content_lines = []

        # Pattern: header noise -> author links -> title -> metrics -> ACTUAL CONTENT -> footer
        content_started = False
        seen_author_links = False
        title_candidates = []

        # Header noise to skip
        header_noise = [
            "Don't miss what's happening",
            'People on X are the first to know',
            '[Log in]',
            '[Sign up]',
            'Create account',
            'Article',
            'See new posts',
            'Conversation',
            '==========',
            '---------------',
        ]

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Always skip header noise
            if any(noise in line for noise in header_noise):
                continue

            # Skip navigation links
            if re.match(r'^\[\]\(https://x\.com/\)', stripped):
                continue
            if '/article/' in stripped and '[](https://' in stripped:
                continue

            # Skip profile images (only at the beginning)
            if not content_started and 'pbs.twimg.com/profile_images' in line:
                continue

            # Check for author links (indicates we're past the header)
            is_author_link = bool(re.search(r'\[.*?\]\(https://x\.com/[^)]+\)', stripped)) and '@' in stripped
            if is_author_link:
                seen_author_links = True
                continue

            # Skip engagement count links (e.g., "[37K](https://...)")
            if re.match(r'^\[[\d\.]+[KM]?\]\(https://', stripped):
                continue

            # Skip separator lines
            if re.match(r'^[-_]{3,}$', stripped):
                continue

            # After author links, identify and skip title/metrics
            if seen_author_links and not content_started:
                # Skip metrics (4 numbers separated by spaces like "30 56 258 37K")
                if re.match(r'^[\d\.]+[KM]?\s+[\d\.]+[KM]?\s+[\d\.]+[KM]?\s+[\d\.]+[KM]?$', stripped):
                    continue

                # Skip standalone numbers (engagement counts)
                if stripped.isdigit() and len(stripped) <= 4:
                    continue

                # Skip lines that are just numbers or metrics
                if re.match(r'^[\d\s,\.KMB]+$', stripped):
                    continue

                # Collect potential title candidates
                if stripped and len(stripped) < 100:
                    title_candidates.append(stripped)
                    continue

                # If we have multiple title candidates, skip the first few lines
                # and start content after that
                if len(title_candidates) >= 1 and len(stripped) >= 20:
                    # Skip the title lines we collected
                    title_candidates = []
                    content_started = True
                elif stripped:
                    # Start content if we have substantial text
                    content_started = True

            if content_started:
                # Stop at footer markers
                footer_markers = [
                    '**Posted:**',
                    'Translate post',
                    'New to X?',
                    'Trending now',
                    '© 202',
                    'Terms of Service',
                    'Privacy Policy',
                    'Cookie Policy',
                    'Want to publish',
                    'Upgrade to Premium',
                    'More · · ·'
                ]
                if any(marker in line for marker in footer_markers):
                    break

                # Preserve image markdown links (don't skip them!)
                # These are like: ![Image](url) or [![Image](url)](link)
                if stripped.startswith('![') or '[![Image' in stripped:
                    content_lines.append(line)
                    continue

                # Skip lines that are just image URLs (not markdown format)
                if re.match(r'^https?://pbs\.twimg\.com/media/', stripped):
                    continue

                # Preserve paragraph breaks
                if not stripped:
                    if content_lines and content_lines[-1] != '\n\n':
                        content_lines.append('\n\n')
                    continue

                content_lines.append(stripped + '\n')

        # Join content
        content = ''.join(content_lines)

        # Clean up extra whitespace but preserve paragraph breaks
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = content.strip()

        return content

    def _embed_images_in_content(self, content: str, images: List[str]) -> str:
        """Supplement missing images into content.

        For long-form Twitter/X articles, the original markdown already contains
        most images. This function only supplements images that are missing
        from the original content.
        """
        if not images or not content:
            return content

        # Filter out non-image URLs
        valid_images = []
        for img in images:
            is_image = any(ext in img.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'])
            has_format = 'format=' in img.lower() and '&name=' in img
            if (is_image or has_format) and 'profile_images' not in img:
                valid_images.append(img)

        if not valid_images:
            return content

        # Find already embedded images in content
        existing_images = set()
        for match in re.finditer(r'!\[.*?\]\((https://pbs\.twimg\.com/media/[^\)]+)\)', content):
            existing_images.add(match.group(1))

        # Only add images that are NOT already in content
        images_to_add = [img for img in valid_images if img not in existing_images]

        if not images_to_add:
            return content

        # Just append the missing images at the end
        # They don't have a natural position, so we add them as a gallery at the end
        content = content.rstrip()

        content += '\n\n---\n\n'
        content += '**附加图片**\n\n'

        for img in images_to_add:
            content += f'![Image]({img})\n'

        return content

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
        """Build main content string from tweet info

        Note: Stats and media are now displayed separately in the UI,
        so this only contains the actual tweet/article content.
        """
        parts = []

        # Add tweet content directly (already formatted from _extract_tweet_text)
        if tweet_info.content:
            parts.append(tweet_info.content)

        # Add a separator for additional context if needed
        if tweet_info.created_at:
            parts.append(f"\n\n---\n\n**Posted:** {tweet_info.created_at}")

        return "\n".join(parts)


# Test function
def test_twitter_extraction():
    """Test Twitter extraction with sample URLs"""
    test_urls = [
        "https://x.com/gengdaJ/status/2018462029867286877",
    ]

    try:
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
                    print(f"Display Name: {content.content.get('metadata', {}).get('display_name')}")
                    print(f"Content: {content.content.get('summary')}")
                    print(f"Likes: {content.content.get('metadata', {}).get('likes')}")
                    print(f"Views: {content.content.get('metadata', {}).get('views')}")
                    print(f"Images: {len(content.media.get('images', []))}")
                else:
                    print(f"❌ Cannot process this URL type")

            except Exception as e:
                print(f"❌ Failed: {e}")

    except ValueError as e:
        print(f"⚠️  {e}")
        print("\nTo get a Tavily API key:")
        print("1. Visit https://tavily.com/")
        print("2. Sign up for an account")
        print("3. Get your API key from the dashboard")
        print("4. Set it as environment variable:")
        print("   export TAVILY_API_KEY=your_key_here")
        print("   Or add to .env file:")
        print("   TAVILY_API_KEY=your_key_here")


def check_api_key():
    """Check if Tavily API key is configured"""
    api_key = os.getenv("TAVILY_API_KEY")
    if api_key:
        print(f"✅ TAVILY_API_KEY is configured (length: {len(api_key)})")
    else:
        print("❌ TAVILY_API_KEY not found")
        print("\nTo configure:")
        print("1. Get an API key at https://tavily.com/")
        print("2. Set environment variable: export TAVILY_API_KEY=your_key")
        print("3. Or add to .env file: TAVILY_API_KEY=your_key")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        check_api_key()
    else:
        test_twitter_extraction()
