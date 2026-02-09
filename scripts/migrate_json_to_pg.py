#!/usr/bin/env python3
"""
Direct JSON to PostgreSQL Migration

This script migrates data directly from JSON files to PostgreSQL,
bypassing the intermediate SQLite step.

Usage:
    python scripts/migrate_json_to_pg.py
"""
import sys
import os
import json
import argparse
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_env_vars():
    """Load environment variables from .env file"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.info("python-dotenv not found, using environment variables as-is")
        return

    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded environment variables from {env_path}")
    else:
        logger.warning(f".env file not found at {env_path}")


def migrate_contents(pg_conn, json_dir):
    """Migrate contents from linker_data.json"""
    logger.info("Migrating contents...")

    data_file = json_dir / "linker_data.json"
    if not data_file.exists():
        logger.warning(f"Contents file not found: {data_file}")
        return 0

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        logger.error(f"Expected list in {data_file}, got {type(data)}")
        return 0

    migrated = 0
    for item in data:
        try:
            if isinstance(item, str):
                logger.debug(f"Skipping string item: {item[:50]}...")
                continue

            if not isinstance(item, dict):
                logger.debug(f"Skipping non-dict item: {type(item)}")
                continue

            content_id = item.get('id')

            # Check if already exists
            existing = pg_conn.fetchone(
                "SELECT id FROM contents WHERE id = %s",
                (content_id,)
            )
            if existing:
                logger.debug(f"Content {content_id} already exists, skipping")
                continue

            # Convert JSON fields to strings
            ai_analysis = item.get('ai_analysis')
            if isinstance(ai_analysis, (dict, list)):
                ai_analysis = json.dumps(ai_analysis, ensure_ascii=False)

            metadata = item.get('metadata')
            if isinstance(metadata, (dict, list)):
                metadata = json.dumps(metadata, ensure_ascii=False)

            # Insert into PostgreSQL
            pg_conn.insert('contents', {
                'id': content_id,
                'source_type': item.get('source_type', 'unknown'),
                'content_type': item.get('content_type', 'article'),
                'title': item.get('title') or item.get('url', 'Untitled'),
                'url': item.get('url'),
                'raw_content': item.get('raw_content'),
                'summary': item.get('summary'),
                'main_content': item.get('main_content'),
                'ai_analysis': ai_analysis,
                'metadata': metadata,
                'archived': item.get('archived', False),
                'favorited': item.get('favorited', False),
                'reading_progress': item.get('reading_progress', 0.0) or 0.0,
                'created_at': item.get('created_at'),
                'updated_at': item.get('updated_at')
            })
            migrated += 1
            logger.debug(f"Migrated content: {content_id}")

        except Exception as e:
            logger.error(f"Error migrating content {item.get('id')}: {e}")

    logger.info(f"Migrated {migrated} contents")
    return migrated


def migrate_projects_to_nodes(pg_conn, json_dir):
    """Migrate projects from projects.json to nodes table"""
    logger.info("Migrating projects to nodes...")

    data_file = json_dir / "projects.json"
    if not data_file.exists():
        logger.warning(f"Projects file not found: {data_file}")
        return 0

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle both list and dict formats
    if isinstance(data, dict):
        projects = data.get('projects', [])
    elif isinstance(data, list):
        projects = data
    else:
        logger.error(f"Unexpected format in {data_file}: {type(data)}")
        return 0

    migrated = 0

    for project in projects:
        try:
            # Handle both 'id' and 'project_id' field names
            project_id = project.get('id') or project.get('project_id')
            if not project_id:
                logger.debug(f"Skipping project with no ID")
                continue

            # Check if already exists
            existing = pg_conn.fetchone(
                "SELECT id FROM nodes WHERE id = %s",
                (project_id,)
            )
            if existing:
                logger.debug(f"Node {project_id} already exists, skipping")
                continue

            # Handle both 'name' and 'project_name' field names
            name = project.get('name') or project.get('project_name', 'Untitled')

            pg_conn.insert('nodes', {
                'id': project_id,
                'node_type': 'project',
                'name': name,
                'description': project.get('description'),
                'parent_id': project.get('parent_id'),
                'status': project.get('status', 'ACTIVE'),
                'icon': project.get('icon', '📁'),
                'tags': json.dumps(project.get('tags', []), ensure_ascii=False),
                'properties': json.dumps(project.get('properties', {}), ensure_ascii=False),
                'target_date': project.get('target_date'),
                'completed_at': project.get('completed_at')
            })
            migrated += 1
            logger.debug(f"Migrated project: {project_id}")

        except Exception as e:
            logger.error(f"Error migrating project {project.get('id') or project.get('project_id')}: {e}")

    logger.info(f"Migrated {migrated} projects")
    return migrated


def migrate_notes(pg_conn, json_dir):
    """Migrate notes from notes.json"""
    logger.info("Migrating notes...")

    data_file = json_dir / "notes.json"
    if not data_file.exists():
        logger.warning(f"Notes file not found: {data_file}")
        return 0

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle both list and dict formats
    if isinstance(data, dict):
        notes = data.get('notes', [])
    elif isinstance(data, list):
        notes = data
    else:
        logger.error(f"Unexpected format in {data_file}: {type(data)}")
        return 0

    migrated = 0

    for note in notes:
        try:
            # Handle both 'id' and 'note_id' field names
            note_id = note.get('id') or note.get('note_id')
            if not note_id:
                logger.debug(f"Skipping note with no ID")
                continue

            # Check if already exists
            existing = pg_conn.fetchone(
                "SELECT id FROM notes WHERE id = %s",
                (note_id,)
            )
            if existing:
                logger.debug(f"Note {note_id} already exists, skipping")
                continue

            pg_conn.insert('notes', {
                'id': note_id,
                'content_id': note.get('content_id'),
                'note_type': note.get('note_type', 'note'),
                'content': note.get('content', ''),
                'highlights': json.dumps(note.get('highlights', []), ensure_ascii=False),
                'summary_layers': json.dumps(note.get('summary_layers', {}), ensure_ascii=False),
                'project_tags': json.dumps(note.get('project_tags', []), ensure_ascii=False)
            })
            migrated += 1
            logger.debug(f"Migrated note: {note_id}")

        except Exception as e:
            logger.error(f"Error migrating note {note.get('id') or note.get('note_id')}: {e}")

    logger.info(f"Migrated {migrated} notes")
    return migrated


def migrate_skills(pg_conn, json_dir):
    """Migrate skills from skill_trees.json"""
    logger.info("Migrating skills...")

    data_file = json_dir / "skill_trees.json"
    if not data_file.exists():
        logger.warning(f"Skills file not found: {data_file}")
        return 0

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle both list and dict formats
    if isinstance(data, dict):
        skills = data.get('skills', [])
    elif isinstance(data, list):
        skills = data
    else:
        logger.error(f"Unexpected format in {data_file}: {type(data)}")
        return 0

    migrated = 0

    for skill in skills:
        try:
            skill_id = skill.get('id') or skill.get('skill_id')
            if not skill_id:
                logger.debug(f"Skipping skill with no ID")
                continue

            # Check if already exists
            existing = pg_conn.fetchone(
                "SELECT id FROM skills WHERE id = %s",
                (skill_id,)
            )
            if existing:
                logger.debug(f"Skill {skill_id} already exists, skipping")
                continue

            pg_conn.insert('skills', {
                'id': skill_id,
                'skill_name': skill.get('name') or skill.get('skill_name', 'Untitled'),
                'category': skill.get('category'),
                'level': skill.get('level', 'beginner'),
                'parent_ids': json.dumps(skill.get('parent_ids', []), ensure_ascii=False),
                'description': skill.get('description')
            })
            migrated += 1
            logger.debug(f"Migrated skill: {skill_id}")

        except Exception as e:
            logger.error(f"Error migrating skill {skill.get('id')}: {e}")

    logger.info(f"Migrated {migrated} skills")
    return migrated


def migrate_citations(pg_conn, json_dir):
    """Migrate citations from citations.json"""
    logger.info("Migrating citations...")

    data_file = json_dir / "citations.json"
    if not data_file.exists():
        logger.warning(f"Citations file not found: {data_file}")
        return 0

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle both list and dict formats
    if isinstance(data, dict):
        citations = data.get('citations', [])
    elif isinstance(data, list):
        citations = data
    else:
        logger.error(f"Unexpected format in {data_file}: {type(data)}")
        return 0

    migrated = 0

    for citation in citations:
        try:
            citation_id = citation.get('id') or citation.get('citation_id')
            if not citation_id:
                logger.debug(f"Skipping citation with no ID")
                continue

            # Check if already exists
            existing = pg_conn.fetchone(
                "SELECT id FROM citations WHERE id = %s",
                (citation_id,)
            )
            if existing:
                logger.debug(f"Citation {citation_id} already exists, skipping")
                continue

            pg_conn.insert('citations', {
                'id': citation_id,
                'project_id': citation.get('project_id'),
                'source_content_id': citation.get('source_content_id'),
                'quote_text': citation.get('quote_text', ''),
                'context': citation.get('context'),
                'position': citation.get('position')
            })
            migrated += 1
            logger.debug(f"Migrated citation: {citation_id}")

        except Exception as e:
            logger.error(f"Error migrating citation {citation.get('id')}: {e}")

    logger.info(f"Migrated {migrated} citations")
    return migrated


def migrate_learning_progress(pg_conn, json_dir):
    """Migrate learning progress from learning_progress.json"""
    logger.info("Migrating learning progress...")

    data_file = json_dir / "learning_progress.json"
    if not data_file.exists():
        logger.warning(f"Learning progress file not found: {data_file}")
        return 0

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, dict):
        logger.error(f"Expected dict in {data_file}, got {type(data)}")
        return 0

    # Migrate to review_schedules table
    progress_data = data.get('progress', {})
    migrated = 0

    for content_id, progress in progress_data.items():
        try:
            # Check if already exists
            existing = pg_conn.fetchone(
                "SELECT content_id FROM review_schedules WHERE content_id = %s",
                (content_id,)
            )
            if existing:
                logger.debug(f"Review schedule for {content_id} already exists, skipping")
                continue

            pg_conn.insert('review_schedules', {
                'content_id': content_id,
                'last_reviewed': progress.get('last_reviewed'),
                'next_review': progress.get('next_review') or '2026-12-31',
                'review_count': progress.get('review_count', 0),
                'interval_days': progress.get('interval_days', 1),
                'ease_factor': progress.get('ease_factor', 2.5)
            })
            migrated += 1
            logger.debug(f"Migrated review schedule: {content_id}")

        except Exception as e:
            logger.error(f"Error migrating review schedule for {content_id}: {e}")

    logger.info(f"Migrated {migrated} review schedules")
    return migrated


def main():
    parser = argparse.ArgumentParser(
        description='Migrate Linker Mind data from JSON to PostgreSQL'
    )
    parser.add_argument(
        '--json-dir',
        help='Directory containing JSON files (default: current directory)',
        default='.'
    )
    parser.add_argument(
        '--init-only',
        action='store_true',
        help='Only initialize PostgreSQL schema, skip migration'
    )

    args = parser.parse_args()

    # Load environment variables
    load_env_vars()

    logger.info("=" * 60)
    logger.info("Linker Mind - JSON to PostgreSQL Migration")
    logger.info("=" * 60)

    # Import PostgreSQL modules
    try:
        from database.pg_connection import PostgreSQLConfig, get_pg_connection, init_postgresql
    except ImportError as e:
        logger.error(f"Failed to import PostgreSQL modules: {e}")
        logger.error("Install with: pip install psycopg2-binary")
        return 1

    # Build PostgreSQL config
    config = PostgreSQLConfig(
        host=os.getenv('PGHOST', 'localhost'),
        port=int(os.getenv('PGPORT', 5432)),
        database=os.getenv('PGDATABASE', 'linker_mind'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', ''),
        min_connections=2,
        max_connections=10
    )

    json_dir = Path(args.json_dir)

    try:
        # Test PostgreSQL connection
        logger.info("Testing PostgreSQL connection...")
        pg_conn = get_pg_connection(config)

        if args.init_only:
            logger.info("Initializing PostgreSQL schema...")
            schema_file = project_root / "database" / "schema_pg.sql"
            if init_postgresql(config, str(schema_file)):
                logger.info("✓ PostgreSQL schema initialized successfully")
                return 0
            else:
                logger.error("✗ Failed to initialize PostgreSQL schema")
                return 1

        # Check if schema exists
        tables = pg_conn.get_tables()
        if not tables or 'contents' not in tables:
            logger.info("Initializing PostgreSQL schema...")
            schema_file = project_root / "database" / "schema_pg.sql"
            init_postgresql(config, str(schema_file))

        # Run migration
        logger.info("\nStarting migration...")
        logger.info("-" * 60)

        results = {}
        results['contents'] = migrate_contents(pg_conn, json_dir)
        results['projects'] = migrate_projects_to_nodes(pg_conn, json_dir)
        results['notes'] = migrate_notes(pg_conn, json_dir)
        results['skills'] = migrate_skills(pg_conn, json_dir)
        results['citations'] = migrate_citations(pg_conn, json_dir)
        results['learning_progress'] = migrate_learning_progress(pg_conn, json_dir)

        # Print results
        logger.info("-" * 60)
        logger.info("Migration Results:")
        logger.info("-" * 60)

        total_migrated = 0
        for table, count in results.items():
            status = "✓" if count > 0 else "○"
            logger.info(f"{status} {table}: {count} records")
            total_migrated += count

        logger.info("-" * 60)
        logger.info(f"Total records migrated: {total_migrated}")
        logger.info("=" * 60)

        # Post-migration verification
        logger.info("\nPost-migration verification...")
        tables = pg_conn.get_tables()
        logger.info(f"PostgreSQL tables: {tables}")

        logger.info("\nRecord counts in PostgreSQL:")
        for table in ['contents', 'nodes', 'notes', 'skills', 'citations', 'review_schedules']:
            if table in tables:
                count = pg_conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                logger.info(f"  {table}: {count} records")

        logger.info("\n" + "=" * 60)
        logger.info("Migration complete!")
        logger.info("=" * 60)
        logger.info("\nYour data is now in PostgreSQL!")
        logger.info("You can start using the application.")

        return 0

    except Exception as e:
        logger.error(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
