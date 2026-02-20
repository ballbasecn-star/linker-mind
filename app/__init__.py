"""
Linker Mind - Flask Application Factory
======================

A Second Brain + Creative Workspace system
"""

from flask import Flask
import os
import re


def create_app(config=None):
    """
    Application factory pattern.

    Args:
        config: Optional configuration dictionary

    Returns:
        Flask application instance
    """
    # Get the project root directory
    import os
    # Get the directory containing the app folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_root = os.path.dirname(current_dir)

    app = Flask(__name__,
                template_folder=os.path.join(app_root, 'templates'),
                static_folder=os.path.join(app_root, 'static'),
                static_url_path='/static')

    # Default configuration
    app.config.setdefault('SECRET_KEY', os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production'))
    app.config.setdefault('JSON_AS_ASCII', False)
    app.config.setdefault('JSONIFY_PRETTYPRINT_REGULAR', True)
    app.config.setdefault('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)  # 16MB max upload
    app.config.setdefault('TEMPLATES_auto_reload', True)  # Enable template auto-reload

    # Apply custom configuration
    if config:
        app.config.update(config)

    # Register error handlers
    register_error_handlers(app)

    # Register custom Jinja filters
    register_jinja_filters(app)

    # Register blueprints
    register_blueprints(app)

    # Register context processors
    register_context_processors(app)

    return app


def register_jinja_filters(app):
    """Register custom Jinja filters."""

    @app.template_filter('markdown_images')
    def markdown_images(text):
        """Convert Markdown image syntax to HTML img tags.

        Handles various formats:
        - ![alt](url) - basic markdown image
        - [Image N: Image](url) - Twitter's format
        - [![Image N: Image](pbs.twimg.com)](x.com link) - nested format
        - [Image: source: /path/to/file.jpg] - local file format
        - <img src="..."> - HTML img tags (preserve)
        - 微信图片格式 (mmbiz.qpic.cn, qpic.cn, etc.)
        """
        if not text:
            return text

        # Strategy: Process patterns from most complex to simplest

        # First: Preserve existing HTML img tags to avoid double-processing
        img_tags = []
        def save_img_tags(match):
            img_tags.append(match.group(0))
            return f'___IMG_TAG_{len(img_tags)-1}___'

        text = re.sub(r'<img[^>]+>', save_img_tags, text)

        # Pattern 0: WeChat image format - direct URLs from WeChat CDN
        # Match common WeChat image domains
        def replace_wechat_image(match):
            url = match.group(0)
            # Filter out non-image URLs
            if any(x in url for x in ['wx_fmt=gif', 'wx_fmt=webp']) and 'mmbiz.qpic.cn' not in url:
                # Might be an animation, still show it
                return f'<img src="{url}" alt="Image" loading="lazy" style="max-width: 100%; border-radius: 8px; margin: 8px 0;">'
            return f'<img src="{url}" alt="Image" loading="lazy" style="max-width: 100%; border-radius: 8px; margin: 8px 0;">'

        # Match WeChat CDN URLs directly
        text = re.sub(r'https://mmbiz\.qpic\.cn/[^\s\)\]"\']+', replace_wechat_image, text)
        text = re.sub(r'https://qpic\.cn/[^\s\)\]"\']+', replace_wechat_image, text)
        text = re.sub(r'https://mmbiz\.qlogo\.cn/[^\s\)\]"\']+', replace_wechat_image, text)

        # First: Remove or convert local file paths (not accessible in browser)
        # Pattern: [Image: source: /path/to/file.jpg] or similar
        def replace_local_image(match):
            content = match.group(1)
            # Try to find a URL in the content
            url_match = re.search(r'(https?://[^\s\]]+|/[\w\-./]+)', content)
            if url_match:
                url = url_match.group(1)
                if url.startswith('http'):
                    return f'<img src="{url}" alt="Image" loading="lazy" style="max-width: 100%; border-radius: 8px; margin: 8px 0;">'
                # Local file - hide it or show a placeholder
                return f'<div style="display:none;"></div>'
            return ''

        text = re.sub(r'\[Image:\s*source:\s*([^\]]+)\]', replace_local_image, text)

        # Pattern 1: Nested format - [![Image N: Image](pbs.twimg.com)](x.com/...)
        # This is the main format causing issues
        def replace_nested(match):
            full = match.group(0)
            # Extract the inner pbs.twimg.com URL from inside ![...](...)
            inner_match = re.search(r'!\[[^\]]*\]\(([^)]+)\)', full)
            if inner_match:
                url = inner_match.group(1)
                if 'pbs.twimg.com' in url:
                    return f'<img src="{url}" alt="Image" loading="lazy" style="max-width: 100%; border-radius: 8px; margin: 8px 0;">'
            # If not a pbs.twimg.com URL, try to find any URL in the text
            url_match = re.search(r'https?://[^\s\)\]]+', full)
            if url_match:
                return f'<img src="{url_match.group(0)}" alt="Image" loading="lazy" style="max-width: 100%; border-radius: 8px; margin: 8px 0;">'
            return full

        # Match nested images: [![Image...](pbs...)](x.com...)
        text = re.sub(r'!\[[^\]]+\]\(https?://[^\)]+\)\([^)]+\)', replace_nested, text)

        # Pattern 2: Twitter format [Image N: Image](url) - url contains pbs.twimg.com
        def replace_twitter_image(match):
            text_content = match.group(1)
            url = match.group(2)
            # Check if URL is pbs.twimg.com
            if 'pbs.twimg.com' in url:
                return f'<img src="{url}" alt="Image" loading="lazy" style="max-width: 100%; border-radius: 8px; margin: 8px 0;">'
            # Otherwise make it a link
            return f'<a href="{url}" target="_blank" style="color: #1DA1F2;">{text_content}</a>'

        text = re.sub(r'\[(Image[^\]]*)\]\((https?://[^\)]+)\)', replace_twitter_image, text)

        # Pattern 3: Basic markdown image ![alt](url)
        def replace_basic_image(match):
            alt_text = match.group(1) or 'Image'
            url = match.group(2)
            return f'<img src="{url}" alt="{alt_text}" loading="lazy" style="max-width: 100%; border-radius: 8px; margin: 8px 0;">'

        text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_basic_image, text)

        # Restore saved HTML img tags
        for i, img_tag in enumerate(img_tags):
            text = text.replace(f'___IMG_TAG_{i}___', img_tag)

        return text

    # Also add a filter to convert newlines to <br>
    @app.template_filter('nl2br')
    def nl2br(text):
        """Convert newlines to <br> tags."""
        if not text:
            return text
        return text.replace('\n', '<br>')


def register_blueprints(app):
    """Register all Flask blueprints."""
    from app.blueprints import (
        content_bp,
        node_bp,
        note_bp,
        inbox_bp,
        link_bp,
        creation_bp,
        session_bp,
        skill_bp,
        graph_bp,
        search_bp,
        api_bp,
    )

    app.register_blueprint(content_bp)
    app.register_blueprint(node_bp)
    app.register_blueprint(note_bp)
    app.register_blueprint(inbox_bp)
    app.register_blueprint(link_bp)
    app.register_blueprint(creation_bp)
    app.register_blueprint(session_bp)
    app.register_blueprint(skill_bp)
    app.register_blueprint(graph_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(api_bp)


def register_error_handlers(app):
    """Register global error handlers."""
    from flask import jsonify

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': str(error)
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': 'Not Found',
            'message': str(error)
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': str(error)
        }), 500


def register_context_processors(app):
    """Register template context processors."""
    @app.context_processor
    def utility_processor():
        """Utility functions for templates."""
        from app.utils.formatters import format_date, format_duration, clean_twitter_content

        return {
            'format_date': format_date,
            'format_duration': format_duration,
            'clean_twitter_content': clean_twitter_content,
        }
