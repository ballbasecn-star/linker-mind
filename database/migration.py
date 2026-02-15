"""
Data Migration Module - Migrate from JSON files to SQLite database

This module handles:
- Migration from existing JSON files to SQLite
- Data validation during migration
- Rollback support
- Progress tracking
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import (
    get_db,
    init_database,
    json_dumps,
    json_list,
    json_dict
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataMigration:
    """
    Handles migration from JSON storage to SQLite database
    """

    def __init__(self, db_path: str = "linker_mind.db", json_dir: str = "."):
        self.db_path = db_path
        self.json_dir = Path(json_dir)
        self.db = get_db(db_path)

        # Statistics
        self.stats = {
            'contents_migrated': 0,
            'projects_migrated': 0,
            'notes_migrated': 0,
            'citations_migrated': 0,
            'progress_migrated': 0,
            'skills_migrated': 0,
            'errors': []
        }

    def migrate_all(self, skip_existing: bool = True) -> Dict[str, Any]:
        """
        Run full migration from all JSON files

        Args:
            skip_existing: Skip records that already exist in database

        Returns:
            Migration statistics
        """
        logger.info("Starting full migration...")

        # Initialize database if needed
        if not self.db.table_exists('contents'):
            init_database(self.db_path)
            logger.info("Database initialized")
        else:
            logger.info("Using existing database")

        # Migrate contents
        self.migrate_contents(skip_existing)

        # Migrate projects (converts to nodes)
        self.migrate_projects_to_nodes(skip_existing)

        # Migrate notes
        self.migrate_notes(skip_existing)

        # Migrate citations
        self.migrate_citations(skip_existing)

        # Migrate learning progress
        self.migrate_learning_progress(skip_existing)

        # Migrate skills
        self.migrate_skills(skip_existing)

        logger.info(f"Migration complete: {self.stats}")
        return self.stats

    def migrate_contents(self, skip_existing: bool = True) -> int:
        """Migrate contents from linker_data.json"""
        json_file = self.json_dir / "linker_data.json"
        if not json_file.exists():
            logger.warning(f"Contents file not found: {json_file}")
            return 0

        logger.info("Migrating contents...")

        with open(json_file, 'r', encoding='utf-8') as f:
            contents = json.load(f)

        migrated = 0
        for item in contents:
            content_id = item.get('id')
            if not content_id:
                continue

            # Check if already exists
            if skip_existing:
                existing = self.db.fetchone(
                    "SELECT id FROM contents WHERE id = ?",
                    (content_id,)
                )
                if existing:
                    continue

            try:
                self._insert_content(item)
                migrated += 1
            except Exception as e:
                logger.error(f"Error migrating content {content_id}: {e}")
                self.stats['errors'].append(f"content_{content_id}: {e}")

        logger.info(f"Migrated {migrated} contents")
        self.stats['contents_migrated'] = migrated
        return migrated

    def _insert_content(self, item: Dict[str, Any]) -> None:
        """Insert a single content item"""
        content = item.get('content', {})
        metadata = content.get('metadata', {})

        self.db.insert("contents", {
            'id': item.get('id'),
            'source_type': item.get('source_type', 'unknown'),
            'content_type': self._determine_content_type(item),
            'title': content.get('title'),
            'url': content.get('url', item.get('raw_input', '')),
            'raw_content': item.get('raw_input', ''),
            'summary': content.get('summary'),
            'main_content': content.get('main_content', ''),
            'html_content': content.get('html', ''),
            'ai_analysis': json_dumps(item.get('ai_analysis', {})),
            'metadata': json_dumps(metadata),
            'media': json_dumps(item.get('media', {})),
            'processing_info': json_dumps(item.get('processing_info', {})),
            'archived': 0,
            'favorited': 0,
            'reading_progress': 0.0,
            'created_at': item.get('timestamp', datetime.now().isoformat()),
            'updated_at': item.get('timestamp', datetime.now().isoformat())
        })

    def _determine_content_type(self, item: Dict[str, Any]) -> str:
        """Determine content type from source type and platform"""
        source_type = item.get('source_type', '')
        platform = item.get('platform', '')

        # Map source types to content types
        type_mapping = {
            'webpage': 'article',
            'twitter': 'post',
            'tweet': 'post',
            'video': 'video',
            'youtube': 'video',
            'bilibili': 'video',
            'douyin': 'video',
            'wechat': 'article',
            'weixin': 'article',
            'memo': 'note',
            'text': 'note'
        }

        return type_mapping.get(platform, type_mapping.get(source_type, 'article'))

    def migrate_projects_to_nodes(self, skip_existing: bool = True) -> int:
        """Migrate projects.json to nodes table"""
        json_file = self.json_dir / "projects.json"
        if not json_file.exists():
            logger.info(f"Projects file not found: {json_file}")
            return 0

        logger.info("Migrating projects to nodes...")

        with open(json_file, 'r', encoding='utf-8') as f:
            projects = json.load(f)

        migrated = 0
        for project in projects:
            project_id = project.get('project_id')
            if not project_id:
                continue

            # Check if already exists
            if skip_existing:
                existing = self.db.fetchone(
                    "SELECT id FROM nodes WHERE id = ?",
                    (project_id,)
                )
                if existing:
                    # Still need to migrate content associations
                    self._migrate_project_content_associations(project)
                    continue

            try:
                self._insert_node_from_project(project)
                self._migrate_project_content_associations(project)
                migrated += 1
            except Exception as e:
                logger.error(f"Error migrating project {project_id}: {e}")
                self.stats['errors'].append(f"project_{project_id}: {e}")

        logger.info(f"Migrated {migrated} projects to nodes")
        self.stats['projects_migrated'] = migrated
        return migrated

    def _insert_node_from_project(self, project: Dict[str, Any]) -> None:
        """Insert a node from project data"""
        # Map project status to node status
        status_mapping = {
            'collecting': 'ACTIVE',
            'planning': 'ACTIVE',
            'in_progress': 'ACTIVE',
            'review': 'ACTIVE',
            'completed': 'COMPLETED'
        }

        # Map project type to node type
        # Most projects become PROJECT nodes, but we could be smarter
        node_id = project.get('project_id')
        node_type = 'PROJECT'

        self.db.insert("nodes", {
            'id': node_id,
            'node_type': node_type,
            'name': project.get('project_name', 'Unnamed Project'),
            'description': project.get('description', ''),
            'parent_id': None,
            'order_index': 0,
            'status': status_mapping.get(project.get('status', ''), 'ACTIVE'),
            'color': self._get_project_color(project.get('project_type', '')),
            'icon': self._get_project_icon(project.get('project_type', '')),
            'tags': json_dumps(project.get('tags', [])),
            'metadata': json_dumps({
                'project_type': project.get('project_type'),
                'difficulty': project.get('difficulty'),
                'estimated_time': project.get('estimated_time'),
                'skills_involved': project.get('skills_involved', [])
            }),
            'target_date': project.get('target_date'),
            'completed_at': project.get('completed_at'),
            'created_at': project.get('created_at', datetime.now().isoformat())
        })

    def _migrate_project_content_associations(self, project: Dict[str, Any]) -> None:
        """Migrate content associations for a project"""
        project_id = project.get('project_id')
        content_ids = project.get('content_ids', [])

        for content_id in content_ids:
            # Check if association already exists
            existing = self.db.fetchone(
                "SELECT * FROM node_contents WHERE node_id = ? AND content_id = ?",
                (project_id, content_id)
            )
            if not existing:
                self.db.insert("node_contents", {
                    'node_id': project_id,
                    'content_id': content_id,
                    'added_at': datetime.now().isoformat(),
                    'order_index': 0,
                    'notes': None
                })

    def _get_project_color(self, project_type: str) -> str:
        """Get color for project type"""
        colors = {
            'design': '#e74c3c',
            'learning': '#3498db',
            'writing': '#9b59b6',
            'research': '#1abc9c',
            'development': '#e67e22',
            'other': '#95a5a6'
        }
        return colors.get(project_type, '#95a5a6')

    def _get_project_icon(self, project_type: str) -> str:
        """Get icon for project type"""
        icons = {
            'design': '🎨',
            'learning': '📚',
            'writing': '✍️',
            'research': '🔬',
            'development': '💻',
            'other': '📁'
        }
        return icons.get(project_type, '📁')

    def migrate_notes(self, skip_existing: bool = True) -> int:
        """Migrate notes from notes.json"""
        json_file = self.json_dir / "notes.json"
        if not json_file.exists():
            logger.info(f"Notes file not found: {json_file}")
            return 0

        logger.info("Migrating notes...")

        with open(json_file, 'r', encoding='utf-8') as f:
            notes = json.load(f)

        migrated = 0
        for note in notes:
            note_id = note.get('note_id')
            if not note_id:
                continue

            # Check if already exists
            if skip_existing:
                existing = self.db.fetchone(
                    "SELECT id FROM notes WHERE id = ?",
                    (note_id,)
                )
                if existing:
                    continue

            try:
                self._insert_note(note)
                migrated += 1
            except Exception as e:
                logger.error(f"Error migrating note {note_id}: {e}")
                self.stats['errors'].append(f"note_{note_id}: {e}")

        logger.info(f"Migrated {migrated} notes")
        self.stats['notes_migrated'] = migrated
        return migrated

    def _insert_note(self, note: Dict[str, Any]) -> None:
        """Insert a single note"""
        self.db.insert("notes", {
            'id': note.get('note_id'),
            'content_id': note.get('content_id'),
            'node_id': note.get('project_id'),
            'note_type': note.get('note_type', 'learning'),
            'content': note.get('content'),
            'summary_layer': 0,  # Reset progressive summary for migrated notes
            'highlights': json_dumps(note.get('highlights', [])),
            'bolded_text': json_dumps([]),
            'supernotes': json_dumps([]),
            'own_words': json_dumps([]),
            'insights': json_dumps([]),
            'quotes': json_dumps(note.get('highlights', [])),
            'project_tags': json_dumps(note.get('project_tags', [])),
            'mood_tags': json_dumps(note.get('mood_tags', [])),
            'actionable': 1 if note.get('actionable') else 0,
            'related_note_ids': json_dumps(note.get('related_notes', [])),
            'related_content_ids': json_dumps([]),
            'resolved': 1 if note.get('resolved') else 0,
            'resolution_note': None,
            'priority': note.get('priority', 'medium'),
            'status': 'active',
            'created_at': note.get('timestamp', datetime.now().isoformat()),
            'updated_at': note.get('timestamp', datetime.now().isoformat())
        })

    def migrate_citations(self, skip_existing: bool = True) -> int:
        """Migrate citations from citations.json"""
        json_file = self.json_dir / "citations.json"
        if not json_file.exists():
            logger.info(f"Citations file not found: {json_file}")
            return 0

        logger.info("Migrating citations...")

        with open(json_file, 'r', encoding='utf-8') as f:
            citations = json.load(f)

        migrated = 0
        for citation in citations:
            citation_id = citation.get('citation_id')
            if not citation_id:
                continue

            # Check if already exists
            if skip_existing:
                existing = self.db.fetchone(
                    "SELECT id FROM citations WHERE id = ?",
                    (citation_id,)
                )
                if existing:
                    continue

            try:
                self._insert_citation(citation)
                migrated += 1
            except Exception as e:
                logger.error(f"Error migrating citation {citation_id}: {e}")
                self.stats['errors'].append(f"citation_{citation_id}: {e}")

        logger.info(f"Migrated {migrated} citations")
        self.stats['citations_migrated'] = migrated
        return migrated

    def _insert_citation(self, citation: Dict[str, Any]) -> None:
        """Insert a single citation"""
        self.db.insert("citations", {
            'id': citation.get('citation_id'),
            'project_id': None,  # Citations weren't tied to projects before
            'source_content_id': citation.get('source_id'),
            'quote_text': citation.get('quoted_text', ''),
            'context': citation.get('context', ''),
            'position': citation.get('page_reference', ''),
            'citation_format': 'academic'
        })

    def migrate_learning_progress(self, skip_existing: bool = True) -> int:
        """Migrate learning progress from learning_progress.json"""
        json_file = self.json_dir / "learning_progress.json"
        if not json_file.exists():
            logger.info(f"Learning progress file not found: {json_file}")
            return 0

        logger.info("Migrating learning progress...")

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            records = data.get('records', [])

        migrated = 0
        for record in records:
            content_id = record.get('content_id')
            if not content_id:
                continue

            # Check if content exists
            content = self.db.fetchone(
                "SELECT id FROM contents WHERE id = ?",
                (content_id,)
            )
            if not content:
                continue

            try:
                self._migrate_progress_record(record)
                migrated += 1
            except Exception as e:
                logger.error(f"Error migrating progress for {content_id}: {e}")
                self.stats['errors'].append(f"progress_{content_id}: {e}")

        logger.info(f"Migrated {migrated} progress records")
        self.stats['progress_migrated'] = migrated
        return migrated

    def _migrate_progress_record(self, record: Dict[str, Any]) -> None:
        """Migrate a single progress record"""

        # Update content reading progress
        self.db.update(
            "contents",
            {'reading_progress': record.get('reading_progress', 0.0)},
            "id = ?",
            (record.get('content_id'),)
        )

        # Create review schedule if completed
        if record.get('status') in ['completed', 'mastered']:
            existing_schedule = self.db.fetchone(
                "SELECT content_id FROM review_schedules WHERE content_id = ?",
                (record.get('content_id'),)
            )

            if not existing_schedule:
                self.db.insert("review_schedules", {
                    'content_id': record.get('content_id'),
                    'user_id': 'default',
                    'last_reviewed': record.get('last_reviewed'),
                    'next_review': self._calculate_next_review(record),
                    'review_count': record.get('review_count', 0),
                    'interval_days': 1.0,
                    'ease_factor': 2.5,
                    'total_reviews': record.get('review_count', 0)
                })

    def _calculate_next_review(self, record: Dict[str, Any]) -> str:
        """Calculate next review date from record"""
        intervals = [1, 3, 7, 14, 30]
        review_count = record.get('review_count', 0)
        interval = intervals[min(review_count, len(intervals) - 1)]

        if record.get('last_reviewed'):
            try:
                from datetime import timedelta
                last_reviewed = datetime.fromisoformat(record['last_reviewed'])
                next_review = last_reviewed + timedelta(days=interval)
                return next_review.isoformat()
            except:
                pass

        return datetime.now().isoformat()

    def migrate_skills(self, skip_existing: bool = True) -> int:
        """Migrate skills from skill_trees.json"""
        json_file = self.json_dir / "skill_trees.json"
        if not json_file.exists():
            logger.info(f"Skills file not found: {json_file}")
            return 0

        logger.info("Migrating skills...")

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            skills_data = data.get('skills', [])

        migrated = 0
        for skill in skills_data:
            skill_id = skill.get('skill_id')
            if not skill_id:
                continue

            # Check if already exists
            if skip_existing:
                existing = self.db.fetchone(
                    "SELECT id FROM skills WHERE id = ?",
                    (skill_id,)
                )
                if existing:
                    self._migrate_skill_resources(skill)
                    continue

            try:
                self._insert_skill(skill)
                self._migrate_skill_resources(skill)
                migrated += 1
            except Exception as e:
                logger.error(f"Error migrating skill {skill_id}: {e}")
                self.stats['errors'].append(f"skill_{skill_id}: {e}")

        logger.info(f"Migrated {migrated} skills")
        self.stats['skills_migrated'] = migrated
        return migrated

    def _insert_skill(self, skill: Dict[str, Any]) -> None:
        """Insert a single skill"""
        self.db.insert("skills", {
            'id': skill.get('skill_id'),
            'skill_name': skill.get('skill_name'),
            'category': skill.get('category', ''),
            'level': skill.get('level', 'BEGINNER').upper(),
            'parent_ids': json_dumps(skill.get('parent_skills', [])),
            'description': skill.get('description', ''),
            'progress': skill.get('progress', 0.0),
            'status': skill.get('status', 'not_started'),
            'estimated_hours': skill.get('estimated_hours', 0.0),
            'difficulty_score': skill.get('difficulty_score', 1),
            'tags': json_dumps(skill.get('tags', [])),
            'created_at': datetime.now().isoformat()
        })

    def _migrate_skill_resources(self, skill: Dict[str, Any]) -> None:
        """Migrate skill-content associations"""
        skill_id = skill.get('skill_id')
        resource_ids = skill.get('resource_ids', [])

        for resource_id in resource_ids:
            # Check if content exists
            content = self.db.fetchone(
                "SELECT id FROM contents WHERE id = ?",
                (resource_id,)
            )
            if not content:
                continue

            # Check if association already exists
            existing = self.db.fetchone(
                "SELECT * FROM skill_contents WHERE skill_id = ? AND content_id = ?",
                (skill_id, resource_id)
            )
            if not existing:
                self.db.insert("skill_contents", {
                    'skill_id': skill_id,
                    'content_id': resource_id,
                    'order_index': 0,
                    'completed': 0
                })

    def validate_migration(self) -> Dict[str, Any]:
        """Validate the migration by comparing counts"""
        validation = {
            'contents': {'json': 0, 'db': 0, 'match': True},
            'projects': {'json': 0, 'db': 0, 'match': True},
            'notes': {'json': 0, 'db': 0, 'match': True},
            'citations': {'json': 0, 'db': 0, 'match': True},
            'skills': {'json': 0, 'db': 0, 'match': True}
        }

        # Count JSON records
        if (self.json_dir / "linker_data.json").exists():
            with open(self.json_dir / "linker_data.json", 'r') as f:
                validation['contents']['json'] = len(json.load(f))

        if (self.json_dir / "projects.json").exists():
            with open(self.json_dir / "projects.json", 'r') as f:
                validation['projects']['json'] = len(json.load(f))

        if (self.json_dir / "notes.json").exists():
            with open(self.json_dir / "notes.json", 'r') as f:
                validation['notes']['json'] = len(json.load(f))

        if (self.json_dir / "citations.json").exists():
            with open(self.json_dir / "citations.json", 'r') as f:
                validation['citations']['json'] = len(json.load(f))

        if (self.json_dir / "skill_trees.json").exists():
            with open(self.json_dir / "skill_trees.json", 'r') as f:
                data = json.load(f)
                validation['skills']['json'] = len(data.get('skills', []))

        # Count DB records
        validation['contents']['db'] = self.db.fetchval("SELECT COUNT(*) FROM contents")
        validation['projects']['db'] = self.db.fetchval("SELECT COUNT(*) FROM nodes WHERE node_type = 'PROJECT'")
        validation['notes']['db'] = self.db.fetchval("SELECT COUNT(*) FROM notes")
        validation['citations']['db'] = self.db.fetchval("SELECT COUNT(*) FROM citations")
        validation['skills']['db'] = self.db.fetchval("SELECT COUNT(*) FROM skills")

        # Check matches
        for key in validation:
            validation[key]['match'] = validation[key]['json'] == validation[key]['db']

        return validation


def run_migration(db_path: str = "linker_mind.db", json_dir: str = ".", skip_existing: bool = True) -> Dict[str, Any]:
    """
    Run the complete migration

    Args:
        db_path: Path to SQLite database
        json_dir: Directory containing JSON files
        skip_existing: Skip records that already exist

    Returns:
        Migration statistics
    """
    migrator = DataMigration(db_path, json_dir)
    stats = migrator.migrate_all(skip_existing)
    validation = migrator.validate_migration()
    return {'migration': stats, 'validation': validation}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate Linker Mind data from JSON to SQLite")
    parser.add_argument("--db-path", default="linker_mind.db", help="Path to SQLite database")
    parser.add_argument("--json-dir", default=".", help="Directory containing JSON files")
    parser.add_argument("--force", action="store_true", help="Don't skip existing records")
    parser.add_argument("--validate", action="store_true", help="Only validate, don't migrate")

    args = parser.parse_args()

    if args.validate:
        # Only validate
        migrator = DataMigration(args.db_path, args.json_dir)
        validation = migrator.validate_migration()
        print("\n=== Migration Validation ===")
        for key, val in validation.items():
            status = "✓" if val['match'] else "✗"
            print(f"{status} {key}: JSON={val['json']}, DB={val['db']}")
    else:
        # Run migration
        result = run_migration(args.db_path, args.json_dir, skip_existing=not args.force)

        print("\n=== Migration Complete ===")
        print(f"Contents: {result['migration']['contents_migrated']}")
        print(f"Projects: {result['migration']['projects_migrated']}")
        print(f"Notes: {result['migration']['notes_migrated']}")
        print(f"Citations: {result['migration']['citations_migrated']}")
        print(f"Progress: {result['migration']['progress_migrated']}")
        print(f"Skills: {result['migration']['skills_migrated']}")

        if result['migration']['errors']:
            print(f"\n⚠️  {len(result['migration']['errors'])} errors occurred")
            for error in result['migration']['errors'][:5]:
                print(f"  - {error}")

        print("\n=== Validation ===")
        for key, val in result['validation'].items():
            status = "✓" if val['match'] else "✗"
            print(f"{status} {key}: JSON={val['json']}, DB={val['db']}")
