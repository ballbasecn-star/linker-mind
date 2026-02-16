#!/usr/bin/env python3
"""
Linker Mind - Flask Application Entry Point

A Second Brain + Creative Workspace system

Usage:
    python run.py              # Start development server
    python run.py --prod       # Start production server
    python run.py --init       # Initialize database
    python run.py --migrate    # Run database migration
"""
import os
import sys
import argparse
import logging
from pathlib import Path

# Load environment variables from .env file FIRST
from dotenv import load_dotenv

# Explicitly load .env from the project root
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=str(env_path))

# Set PostgreSQL environment variables from .env if not already set
if not os.getenv('PGHOST'):
    os.environ['PGHOST'] = '117.72.207.52'
if not os.getenv('PGPORT'):
    os.environ['PGPORT'] = '5432'
if not os.getenv('PGDATABASE'):
    os.environ['PGDATABASE'] = 'linker-mind'
if not os.getenv('PGUSER'):
    os.environ['PGUSER'] = 'postgres'
if not os.getenv('PGPASSWORD'):
    os.environ['PGPASSWORD'] = 'LinkerAI@2026'
if not os.getenv('DB_TYPE'):
    os.environ['DB_TYPE'] = 'postgresql'

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_database():
    """Initialize the database"""
    from database.db_interface import init_database

    logger.info("Initializing database...")
    success = init_database()

    if success:
        logger.info("✓ Database initialized successfully")
        return True
    else:
        logger.error("✗ Database initialization failed")
        return False


def migrate_data():
    """Migrate data from JSON to database"""
    from database.migration import migrate_json_to_db

    logger.info("Starting data migration from JSON...")

    try:
        stats = migrate_json_to_db()
        logger.info(f"✓ Migration complete:")
        logger.info(f"  - Contents: {stats.get('contents', 0)}")
        logger.info(f"  - Projects: {stats.get('projects', 0)}")
        logger.info(f"  - Notes: {stats.get('notes', 0)}")
        logger.info(f"  - Skills: {stats.get('skills', 0)}")
        return True
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}")
        return False


def validate_config():
    """Validate required configuration before starting app"""
    from config.validator import validate_startup_config
    return validate_startup_config(raise_on_error=True)

def create_app(config=None):
    """Create and configure Flask application"""
    # 首先验证配置
    try:
        validate_config()
    except Exception as e:
        logger.error(f"配置验证失败: {e}")
        raise

    from app import create_app

    app_config = {}

    # Load configuration from environment
    app_config['SECRET_KEY'] = os.environ.get(
        'SECRET_KEY',
        'dev-secret-key-change-in-production'
    )

    # Database configuration (PostgreSQL only)
    db_type = os.environ.get('DB_TYPE', 'postgresql').lower()
    logger.info("Using PostgreSQL database")

    # Debug mode
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app_config['DEBUG'] = debug

    if config:
        app_config.update(config)

    return create_app(app_config)


def run_dev_server(host='127.0.0.1', port=5000):
    """Run development server"""
    app = create_app()

    logger.info(f"Starting development server on http://{host}:{port}")
    logger.info("Press Ctrl+C to stop")

    app.run(
        host=host,
        port=port,
        debug=True,
        use_reloader=True,
        threaded=True
    )


def run_production_server(host='0.0.0.0', port=5000, workers=4):
    """Run production server with gunicorn"""
    try:
        from gunicorn.app.base import BaseApplication

        class LinkerMindApplication(BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    if key in self.cfg.settings and value is not None:
                        self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        app = create_app()

        options = {
            'bind': f'{host}:{port}',
            'workers': workers,
            'worker_class': 'sync',
            'worker_connections': 1000,
            'timeout': 600,  # 10分钟超时，用于视频深度分析
            'keepalive': 2,
            'max_requests': 1000,
            'max_requests_jitter': 50,
            'preload_app': True,
            'accesslog': '-',
            'errorlog': '-',
            'loglevel': 'info',
        }

        LinkerMindApplication(app, options).run()

    except ImportError:
        logger.error("Gunicorn not installed. Install with: pip install gunicorn")
        logger.info("Falling back to development server...")
        run_dev_server(host, port)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Linker Mind - Second Brain + Creative Workspace'
    )

    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Host to bind to (default: 127.0.0.1)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to bind to (default: 5000)'
    )

    parser.add_argument(
        '--prod',
        action='store_true',
        help='Run in production mode with gunicorn'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of worker processes for production (default: 4)'
    )

    parser.add_argument(
        '--init',
        action='store_true',
        help='Initialize the database'
    )

    parser.add_argument(
        '--migrate',
        action='store_true',
        help='Migrate data from JSON to database'
    )

    args = parser.parse_args()

    # Handle special commands
    if args.init:
        success = init_database()
        sys.exit(0 if success else 1)

    if args.migrate:
        success = migrate_data()
        sys.exit(0 if success else 1)

    # Run server
    try:
        if args.prod:
            logger.info("Starting production server...")
            run_production_server(args.host, args.port, args.workers)
        else:
            run_dev_server(args.host, args.port)
    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
