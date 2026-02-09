"""
Linker Mind - Flask Application Factory
======================

A Second Brain + Creative Workspace system
"""

from flask import Flask
import os


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

    # Register blueprints
    register_blueprints(app)

    # Register context processors
    register_context_processors(app)

    return app


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
