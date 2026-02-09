"""
SQLite to PostgreSQL Data Migration Script

This script migrates all data from SQLite to PostgreSQL database,
handling type conversions and data transformations.
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from database.connection import get_db
from database.pg_connection import PostgreSQLConnection, PostgreSQLConfig, get_pg_connection

logger = logging.getLogger(__name__)


class SQLiteToPostgreSQLMigrator:
    """
    Migrates data from SQLite to PostgreSQL
    """

    def __init__(self, sqlite_db_path: str = "linker_mind.db", pg_config: PostgreSQLConfig = None):
        """
        Initialize migrator

        Args:
            sqlite_db_path: Path to SQLite database
            pg_config: PostgreSQL configuration
        """
        self.sqlite_db = get_db(sqlite_db_path)
        self.pg_config = pg_config

    def migrate_all(
        self,
        skip_existing: bool = False,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Migrate all data from SQLite to PostgreSQL

        Args:
            skip_existing: Skip records that already exist in target
            batch_size: Number of records to insert per batch

        Returns:
            Migration results dictionary
        """
        results = {
            'contents_migrated': 0,
            'projects_migrated': 0,
            'notes_migrated': 0,
            'citations_migrated': 0,
            'progress_migrated': 0,
            'skills_migrated': 0,
            'inbox_migrated': 0,
            'links_migrated': 0,
            'sessions_migrated': 0,
            'reviews_migrated': 0,
            'tags_migrated': 0,
            'errors': []
        }

        try:
            pg = get_pg_connection(self.pg_config)

            # Migrate in dependency order
            results['contents_migrated'] = self._migrate_contents(pg, skip_existing, batch_size)
            results['inbox_migrated'] = self._migrate_inbox(pg, skip_existing, batch_size)
            results['notes_migrated'] = self._migrate_notes(pg, skip_existing, batch_size)
            results['tags_migrated'] = self._migrate_tags(pg, skip_existing, batch_size)

            # Migrate nodes (projects → nodes)
            results['projects_migrated'] = self._migrate_nodes(pg, skip_existing, batch_size)

            # Migrate relationships
            results['links_migrated'] = self._migrate_links(pg, skip_existing, batch_size)

            # Migrate creation projects
            results['citations_migrated'] = self._migrate_creation_projects(pg, skip_existing, batch_size)

            # Migrate learning data
            results['sessions_migrated'] = self._migrate_learning_sessions(pg, skip_existing, batch_size)
            results['reviews_migrated'] = self._migrate_review_schedules(pg, skip_existing, batch_size)

            # Migrate skills
            results['skills_migrated'] = self._migrate_skills(pg, skip_existing, batch_size)

            # Migrate progress
            results['progress_migrated'] = self._migrate_progress(pg, skip_existing, batch_size)

            # Post-migration: update sequences and statistics
            self._update_sequences(pg)
            self._update_tag_counts(pg)

            logger.info("Migration completed successfully")
            return results

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            results['errors'].append(str(e))
            raise

    def _migrate_contents(
        self,
        pg: PostgreSQLConnection,
        skip_existing: bool,
        batch_size: int
    ) -> int:
        """Migrate contents table"""
        logger.info("Migrating contents...")

        # Get all SQLite contents
        sqlite_contents = self.sqlite_db.fetchall("SELECT * FROM contents")

        if skip_existing:
            # Filter out already migrated
            existing_ids = pg.fetchval("SELECT ARRAY_AGG(id) FROM contents")
            if existing_ids:
                existing_set = set(existing_ids)
                sqlite_contents = [c for c in sqlite_contents if c['id'] not in existing_set]

        migrated = 0
        batches = [sqlite_contents[i:i + batch_size] for i in range(0, len(sqlite_contents), batch_size)]

        for batch in batches:
            pg_data = []
            for row in batch:
                # Convert JSON fields to JSONB
                ai_analysis = json.loads(row['ai_analysis']) if row['ai_analysis'] else None
                metadata = json.loads(row['metadata']) if row['metadata'] else None

                pg_data.append((
                    row['id'],
                    row['source_type'],
                    row['content_type'],
                    row['title'],
                    row['url'],
                    row['raw_content'],
                    row['summary'],
                    row['main_content'],
                    ai_analysis,
                    metadata,
                    row['favorited'] if row['favorored'] else False,
                    row['archived'] if row['archived'] else False,
                    row['reading_progress'],
                    row['created_at'],
                    row['updated_at'],
                    row.get('processed_at')
                ))

            # Batch insert
            pg.execute_many("""
                INSERT INTO contents (
                    id, source_type, content_type, title, url, raw_content, summary,
                    main_content, ai_analysis, metadata, favorited, archived,
                    reading_progress, created_at, updated_at, processed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, pg_data)

            migrated += len(batch)

        logger.info(f"Migrated {migrated} contents")
        return migrated

    def _migrate_inbox(
        self,
        pg: PostgreSQLConnection,
        skip_existing: bool,
        batch_size: int
    ) -> int:
        """Migrate inbox table"""
        logger.info("Migrating inbox...")

        sqlite_inbox = self.sqlite_db.fetchall("SELECT * FROM inbox")

        if skip_existing:
            existing_ids = pg.fetchval("SELECT ARRAY_AGG(id) FROM inbox")
            if existing_ids:
                existing_set = set(existing_ids)
                sqlite_inbox = [i for i in sqlite_inbox if i['id'] not in existing_set]

        migrated = 0
        for row in sqlite_inbox:
            try:
                # Parse JSON fields
                quick_tags = json.loads(row['quick_tags']) if row['quick_tags'] else []

                pg.insert('inbox', {
                    'id': row['id'],
                    'content_id': row['content_id'],
                    'raw_input': row['raw_input'],
                    'title': row['title'],
                    'url': row['url'],
                    'source_type': row['source_type'],
                    'status': row['status'],
                    'priority': row['priority'] if row['priority'] else 0,
                    'quick_tags': quick_tags,
                    'due_date': row['due_date'],
                    'added_at': row['added_at'],
                    'processed_at': row['processed_at']
                })
                migrated += 1
            except Exception as e:
                logger.warning(f"Failed to migrate inbox item {row.get('id')}: {e}")

        logger.info(f"Migrated {migrated} inbox items")
        return migrated

    def _migrate_notes(
        self,
        pg: PostgreSQLConnection,
        skip_existing: bool,
        batch_size: int
    ) -> int:
        """Migrate notes table"""
        logger.info("Migrating notes...")

        sqlite_notes = self.sqlite_db.fetchall("SELECT * FROM notes")

        if skip_existing:
            existing_ids = pg.fetchval("SELECT ARRAY_AGG(id) FROM notes")
            if existing_ids:
                existing_set = set(existing_ids)
                sqlite_notes = [n for n in sqlite_notes if n['id'] not in existing_set]

        migrated = 0
        for row in sqlite_notes:
            try:
                # Parse JSON fields
                highlights = json.loads(row['highlights']) if row['highlights'] else []
                summary_layers = json.loads(row['summary_layers']) if row['summary_layers'] else {}
                project_tags = json.loads(row['project_tags']) if row['project_tags'] else []

                pg.insert('notes', {
                    'id': row['id'],
                    'content_id': row['content_id'],
                    'note_type': row['note_type'],
                    'content': row['content'],
                    'highlights': highlights,
                    'summary_layers': summary_layers,
                    'project_tags': project_tags,
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                })
                migrated += 1
            except Exception as e:
                logger.warning(f"Failed to migrate note {row.get('id')}: {e}")

        logger.info(f"Migrated {migrated} notes")
        return migrated

    def _migrate_tags(
        self,
        pg: PostgreSQLConnection,
        skip_existing: bool,
        batch_size: int
    ) -> int:
        """Migrate tags and content_tags"""
        logger.info("Migrating tags...")

        migrated = 0

        # First, migrate tags table
        sqlite_tags = self.sqlite_db.fetchall("SELECT * FROM tags")
        existing_tags = pg.fetchall("SELECT name FROM tags")

        existing_tag_names = set(t['name'] for t in existing_tags)

        for row in sqlite_tags:
            if row['name'] not in existing_tag_names:
                try:
                    pg.insert('tags', {
                        'name': row['name'],
                        'color': row['color'] or '#666666',
                        'use_count': row['use_count'] or 0,
                        'created_at': row.get('created_at', datetime.now().isoformat())
                    })
                    migrated += 1
                except Exception as e:
                    logger.warning(f"Failed to migrate tag {row.get('name')}: {e}")

        # Then migrate content_tags
        sqlite_content_tags = self.sqlite_db.fetchall("""
            SELECT ct.content_id, ct.tag_id, ct.tagged_at
            FROM content_tags ct
            JOIN tags t ON ct.tag_id = t.id
        """)

        # Create tag name to ID mapping
        tag_rows = pg.fetchall("SELECT id, name FROM tags")
        tag_id_map = {row['name']: row['id'] for row in tag_rows}

        for row in sqlite_content_tags:
            tag_name = row['tag_name']  # Assuming content_tags has tag_name
            new_tag_id = tag_id_map.get(tag_name)

            if new_tag_name:
                try:
                    pg.insert('content_tags', {
                        'content_id': row['content_id'],
                        'tag_id': new_tag_name,
                        'tagged_at': row['tagged_at']
                    })
                    migrated += 1
                except Exception as e:
                    logger.warning(f"Failed to migrate content_tag: {e}")

        logger.info(f"Migrated {migrated} tag relationships")
        return migrated

    def _migrate_nodes(
        self,
        pg: PostgreSQLConnection,
        skip_existing: bool,
        batch_size: int
    ) -> int:
        """Migrate legacy projects to nodes (PARA system)"""
        logger.info("Migrating projects to nodes...")

        # Read legacy projects
        try:
            with open('projects.json', 'r', encoding='utf-8') as f:
                legacy_projects = json.load(f)
        except:
            legacy_projects = {}

        if not legacy_projects:
            logger.info("No legacy projects to migrate")
            return 0

        migrated = 0

        for project_id, project_data in legacy_projects.items():
            # Check if node already exists
            existing = pg.fetchone("SELECT id FROM nodes WHERE id = %s", (project_id,))
            if existing and skip_existing:
                continue

            try:
                # Map project type to node type
                type_map = {
                    'learning': 'project',
                    'collection': 'area',
                    'resource': 'resource'
                }

                node_type = type_map.get(project_data.get('type', 'learning'), 'project')

                # Get content IDs
                content_ids = project_data.get('content', [])

                # Get tags
                tags = project_data.get('tags', [])
                if isinstance(tags, list):
                    # Convert Tag objects to tag names
                    tags = [tag.get('name', tag) if isinstance(tag, dict) else tag for tag in tags]

                pg.insert('nodes', {
                    'id': project_id,
                    'node_type': node_type,
                    'name': project_data.get('name', 'Untitled Project'),
                    'description': project_data.get('description', ''),
                    'parent_id': None,
                    'tags': tags,
                    'properties': {
                        'url': project_data.get('url', ''),
                        'icon': project_data.get('icon', '📁')
                    },
                    'target_date': project_data.get('target_date'),
                    'status': 'active' if project_data.get('active', True) else 'inactive'
                })

                # Migrate node_contents relationship
                for content_id in content_ids:
                    try:
                        pg.insert('node_contents', {
                            'node_id': project_id,
                            'content_id': content_id
                        })
                    except:
                        pass  # Content may not exist

                migrated += 1

            except Exception as e:
                logger.warning(f"Failed to migrate project {project_id}: {e}")

        logger.info(f"Migrated {migrated} nodes")
        return migrated

    def _migrate_links(
        self,
        pg: PostgreSQLConnection,
        skip_existing: bool,
        batch_size: int
    ) -> int:
        """Migrate links table"""
        logger.info("Migrating links...")

        try:
            with open('citations.json', 'r', encoding='utf-8') as f:
                citations_data = json.load(f)
        except:
            citations_data = {'citations': []}

        migrated = 0

        # In citations, find links between content items
        citation_links = []

        for citation in citations_data.get('citations', []):
            source_id = citation.get('content_id')
            target_id = citation.get('source_content_id')

            if source_id and target_id:
                citation_links.append({
                    'id': f"link_{source_id}_{target_id}_{migrated}",
                    'source_id': source_id,
                    'target_id': target_id,
                    'link_type': 'reference',
                    'context': citation.get('context', ''),
                    'strength': 1.0
                })

        for row in citation_links:
            existing = pg.fetchone("SELECT id FROM links WHERE source_id = %s AND target_id = %s",
                                       (row['source_id'], row['target_id']))

            if existing and skip_existing:
                continue

            try:
                pg.insert('links', row)
                migrated += 1
            except Exception as e:
                logger.warning(f"Failed to migrate link: {e}")

        logger.info(f"Migrated {migrated} links")
        return migrated

    def _migrate_creation_projects(
        self,
        pg: PostgreSQLConnection,
        skip_existing: bool,
        batch_size: int
    ) -> int:
        """Migrate creation projects"""
        logger.info("Migrating creation projects...")

        try:
            with open('projects.json', 'r', encoding='utf-8') as f:
                legacy_projects = json.load(f)
        except:
            logger.info("No creation projects to migrate")
            return 0

        migrated = 0

        for project_id, project_data in legacy_projects.items():
            if project_data.get('type') == 'learning':
                continue  # Skip learning projects

            existing = pg.fetchone("SELECT id FROM creation_projects WHERE id = %s", (project_id,))
            if existing and skip_existing:
                continue

            try:
                pg.insert('creation_projects', {
                    'id': project_id,
                    'project_type': project_data.get('type', 'article'),
                    'title': project_data.get('name', 'Untitled'),
                    'brief': project_data.get('description', ''),
                    'source_materials': project_data.get('content', []),
                    'quotes': project_data.get('quotes', []),
                    'inspirations': project_data.get('inspirations', []),
                    'outline': project_data.get('outline', []),
                    'sections': project_data.get('sections', []),
                    'draft_content': None,
                    'status': 'drafting',
                    'progress': 0.0,
                    'target_date': project_data.get('target_date'),
                    'word_count_goal': project_data.get('word_count_goal'),
                    'word_count_actual': 0,
                    'created_at': project_data.get('created_at'),
                    'updated_at': project_data.get('updated_at')
                })
                migrated += 1
            except Exception as e:
                logger.warning(f"Failed to migrate creation project {project_id}: {e}")

        logger.info(f"Migrated {migrated} creation projects")
        return migrated

    def _migrate_learning_sessions(
        self,
        pg: PostgreSQLConnection,
        skip_existing: bool,
        batch_size: int
    ) -> int:
        """Migrate learning sessions"""
        logger.info("Migrating learning sessions...")

        try:
            with open('learning_progress.json', 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
        except:
            return 0

        migrated = 0

        for content_id, sessions in progress_data.get('sessions', {}).items():
            if sessions:
                # Get the first session
                session_data = sessions[0]

                try:
                    pg.insert('learning_sessions', {
                        'id': session_data.get('id', f"session_{content_id}"),
                        'content_id': content_id,
                        'started_at': session_data.get('first_studied'),
                        'duration': session_data.get('total_time', 0),
                        'comprehension': session_data.get('avg_comprehension', 3),
                        'confidence': session_data.get('avg_confidence', 3),
                        'mood': 'calm'
                    })
                    migrated += 1
                except Exception as e:
                    logger.warning(f"Failed to migrate session for {content_id}: {e}")

        logger.info(f"Migrated {migrated} learning sessions")
        return migrated

    def _migrate_review_schedules(
        self,
        pg: PostgreSQLConnection,
        skip_existing: bool,
        batch_size: int
    ) -> int:
        """Migrate review schedules"""
        logger.info("Migrating review schedules...")

        try:
            with open('learning_progress.json', 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
        except:
            return 0

        migrated = 0

        for content_id, data in progress_data.items():
            next_review = data.get('next_review')
            interval_days = data.get('interval_days', 1)

            if next_review:
                try:
                    pg.insert('review_schedules', {
                        'content_id': content_id,
                        'next_review': next_review,
                        'interval_days': interval_days,
                        'review_count': 1,
                        'ease_factor': 2.5
                    })
                    migrated += 1
                except Exception as e:
                    logger.warning(f"Failed to migrate review schedule for {content_id}: {e}")

        logger.info(f"Migrated {migrated} review schedules")
        return migrated

    def _migrate_skills(
        self,
        pg: PostgreSQLConnection,
        skip_existing: bool,
        batch_size: int
    ) -> int:
        """Migrate skills"""
        logger.info("Migrating skills...")

        try:
            with open('skill_trees.json', 'r', encoding='utf-8') as f:
                skills_data = json.load(f)
        except:
            return 0

        migrated = 0

        for skill_id, skill_data in skills_data.items():
            try:
                pg.insert('skills', {
                    'id': skill_id,
                    'skill_name': skill_data.get('name', skill_id),
                    'category': skill_data.get('category', ''),
                    'level': skill_data.get('level', 'beginner'),
                    'parent_ids': skill_data.get('parent_skills', []),
                    'description': skill_data.get('description', '')
                })
                migrated += 1

                # Migrate skill_contents
                for content_id in skill_data.get('content_items', []):
                    try:
                        pg.insert('skill_contents', {
                            'skill_id': skill_id,
                            'content_id': content_id,
                            'order_index': 0,
                            'completed': skill_data.get('status') == 'completed'
                        })
                    except Exception as e:
                        logger.warning(f"Failed to migrate skill_content: {e}")

            except Exception as e:
                logger.warning(f"Failed to migrate skill {skill_id}: {e}")

        logger.info(f"Migrated {migrated} skills")
        return migrated

    def _migrate_progress(
        self,
        pg: PostgreSQLConnection,
        skip_existing: bool,
        batch_size: int
    ) -> int:
        """Migrate learning progress"""
        logger.info("Migrating learning progress...")
        # This is handled by _migrate_learning_sessions
        return 0

    def _update_sequences(self, pg: PostgreSQLConnection):
        """Update auto-increment sequences if needed"""
        # PostgreSQL uses SERIAL for auto-increment
        # Update tag ID sequence
        max_tag_id = pg.fetchval("SELECT COALESCE(MAX(id), 0) FROM tags")
        if max_tag_id:
            pg.execute("SELECT setval('tags_id_seq', %s, true)", (max_tag_id + 1,))

    def _update_tag_counts(self, pg: PostgreSQLConnection):
        """Update tag use counts"""
        pg.execute("""
            UPDATE tags t
            SET use_count = (
                SELECT COUNT(*)
                FROM content_tags ct
                WHERE ct.tag_id = t.id
            )
        """)


if __name__ == "__main__":
    print("SQLite to PostgreSQL Migration")
    print("=" * 50)

    # Configure PostgreSQL connection
    pg_config = PostgreSQLConfig(
        host="117.72.207.52",
        port=5432,
        database="linker-mind",
        user="postgres",
        password="LinkerAI@2026",
        min_connections=2,
        max_connections=10
    )

    print(f"Connecting to: {pg_config.host}:{pg_config.port}/{pg_config.database}")

    # Create migrator
    migrator = SQLiteToPostgreSQLMigrator(
        sqlite_db_path="linker_mind.db",
        pg_config=pg_config
    )

    # Run migration
    try:
        # First, initialize PostgreSQL schema
        from database.pg_connection import init_postgresql
        print("\n📋 Initializing PostgreSQL schema...")
        init_postgresql(pg_config, "database/schema_pg.sql")

        print("🚀 Starting data migration...")
        results = migrator.migrate_all(skip_existing=True)

        print(f"\n✅ Migration completed:")
        print(f"   Contents: {results['contents_migrated']}")
        print(f"   Projects (Nodes): {results['projects_migrated']}")
        print(f"   Notes: {results['notes_migrated']}")
        print(f"   Tags: {results['tags_migrated']}")
        print(f"   Links: {results['links_migrated']}")
        print(f"   Creation Projects: {results['citations_migrated']}")
        print(f"   Learning Sessions: {results['sessions_migrated']}")
        print(f"   Review Schedules: {results['reviews_migrated']}")
        print(f"   Skills: {results['skills_migrated']}")

        if results['errors']:
            print(f"\n⚠️  Errors: {len(results['errors'])}")
            for error in results['errors'][:5]:
                print(f"   - {error}")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise

    print("\n✓ Migration completed successfully!")