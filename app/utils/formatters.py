"""
Template utility functions and formatters
"""

from datetime import datetime, timedelta
from typing import Optional


def format_date(date_str: Optional[str], format_str: str = '%Y-%m-%d %H:%M') -> str:
    """Format date string for display."""
    if not date_str:
        return '-'

    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime(format_str)
    except (ValueError, AttributeError):
        return date_str


def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds to human readable string."""
    if seconds is None:
        return '-'

    if seconds < 60:
        return f'{seconds}s'

    if seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f'{minutes}m {secs}s' if secs else f'{minutes}m'

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f'{hours}h {minutes}m' if minutes else f'{hours}h'


def format_relative_time(date_str: Optional[str]) -> str:
    """Format date as relative time (e.g., '2 hours ago')."""
    if not date_str:
        return '-'

    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        delta = datetime.now() - dt

        if delta.seconds < 60:
            return 'just now'
        if delta.seconds < 3600:
            minutes = delta.seconds // 60
            return f'{minutes} minute{"s" if minutes > 1 else ""} ago'
        if delta.seconds < 86400:
            hours = delta.seconds // 3600
            return f'{hours} hour{"s" if hours > 1 else ""} ago'
        if delta.days < 7:
            return f'{delta.days} day{"s" if delta.days > 1 else ""} ago'
        if delta.days < 30:
            weeks = delta.days // 7
            return f'{weeks} week{"s" if weeks > 1 else ""} ago'
        if delta.days < 365:
            months = delta.days // 30
            return f'{months} month{"s" if months > 1 else ""} ago'

        years = delta.days // 365
        return f'{years} year{"s" if years > 1 else ""} ago'
    except (ValueError, AttributeError):
        return date_str


def format_file_size(size_bytes: int) -> str:
    """Format file size in bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024
    return f'{size_bytes:.1f} TB'


def format_percentage(value: Optional[float], decimals: int = 1) -> str:
    """Format value as percentage."""
    if value is None:
        return '-'

    return f'{value * 100:.{decimals}f}%'


def clean_twitter_content(content: Optional[str]) -> str:
    """
    Clean Twitter/X content by removing leading noise like metrics numbers.

    Removes:
    - Leading metrics numbers (30, 56, 258 patterns separated by blank lines)
    - Analytics links like [37K](https://...)
    - Empty lines at the start
    """
    if not content:
        return ''

    import re

    # Remove leading empty lines
    content = content.lstrip('\n')

    # Strategy: First, remove standalone number lines at the very beginning
    # These are typically metrics like "30", "56", "258"
    lines = content.split('\n')
    cleaned_lines = []

    # Skip leading empty lines and number-only lines
    skip_mode = True
    for line in lines:
        if skip_mode:
            # Skip empty lines
            if not line.strip():
                continue
            # Skip lines that are just numbers (metrics)
            if line.strip().isdigit():
                continue
            # Found real content, stop skipping
            skip_mode = False

        cleaned_lines.append(line)

    content = '\n'.join(cleaned_lines)

    # Remove analytics links like [37K](https://x.com/.../status/.../analytics)
    analytics_pattern = r'\[\d+[KM]?\]\(https://x\.com/[^)]+/status/[^)]+/analytics\)'
    content = re.sub(analytics_pattern, '', content)

    # Remove standalone engagement count links like [30](https://x.com/...)
    engagement_link_pattern = r'\n\[(\d+[KM]?)\]\(https://x\.com/[^\)]+\)'
    content = re.sub(engagement_link_pattern, '', content)

    # Clean up multiple consecutive newlines
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content.strip()
