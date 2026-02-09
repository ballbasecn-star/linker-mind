#!/usr/bin/env python3
"""
Initialize PostgreSQL Tables

Creates all required tables for Linker Mind in PostgreSQL.
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / '.env')
except ImportError:
    pass

from database.pg_connection import PostgreSQLConfig, get_pg_connection

# Configuration
config = PostgreSQLConfig(
    host=os.getenv('PGHOST', 'localhost'),
    port=int(os.getenv('PGPORT', 5432)),
    database=os.getenv('PGDATABASE', 'linker_mind'),
    user=os.getenv('PGUSER', 'postgres'),
    password=os.getenv('PGPASSWORD', ''),
    min_connections=2,
    max_connections=10
)

# Table definitions
TABLES = {
    'contents': '''
        CREATE TABLE IF NOT EXISTS contents (
            id VARCHAR(64) PRIMARY KEY,
            source_type VARCHAR(50) NOT NULL,
            content_type VARCHAR(50) NOT NULL,
            title VARCHAR(1000),
            url TEXT,
            raw_content TEXT,
            summary TEXT,
            main_content TEXT,
            ai_analysis JSONB,
            metadata JSONB,
            favorited BOOLEAN DEFAULT FALSE,
            archived BOOLEAN DEFAULT FALSE,
            reading_progress DECIMAL(5,2) DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    ''',

    'nodes': '''
        CREATE TABLE IF NOT EXISTS nodes (
            id VARCHAR(64) PRIMARY KEY,
            node_type VARCHAR(20) NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            parent_id VARCHAR(64),
            status VARCHAR(20) DEFAULT 'ACTIVE',
            icon VARCHAR(10) DEFAULT '📁',
            tags JSONB DEFAULT '[]'::jsonb,
            properties JSONB DEFAULT '{}'::jsonb,
            target_date DATE,
            completed_at DATE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    ''',

    'notes': '''
        CREATE TABLE IF NOT EXISTS notes (
            id VARCHAR(64) PRIMARY KEY,
            content_id VARCHAR(64),
            note_type VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            highlights JSONB DEFAULT '[]'::jsonb,
            summary_layers JSONB DEFAULT '{}'::jsonb,
            project_tags JSONB DEFAULT '[]'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    ''',

    'skills': '''
        CREATE TABLE IF NOT EXISTS skills (
            id VARCHAR(64) PRIMARY KEY,
            skill_name VARCHAR(200) NOT NULL,
            category VARCHAR(100),
            level VARCHAR(20) DEFAULT 'beginner',
            parent_ids JSONB DEFAULT '[]'::jsonb,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    ''',

    'citations': '''
        CREATE TABLE IF NOT EXISTS citations (
            id VARCHAR(64) PRIMARY KEY,
            project_id VARCHAR(64) NOT NULL,
            source_content_id VARCHAR(64) NOT NULL,
            quote_text TEXT NOT NULL,
            context TEXT,
            position VARCHAR(100),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    ''',

    'review_schedules': '''
        CREATE TABLE IF NOT EXISTS review_schedules (
            content_id VARCHAR(64) PRIMARY KEY,
            last_reviewed TIMESTAMP WITH TIME ZONE,
            next_review TIMESTAMP WITH TIME ZONE NOT NULL,
            review_count INTEGER DEFAULT 0,
            interval_days INTEGER DEFAULT 1,
            ease_factor DECIMAL(4,2) DEFAULT 2.5,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    ''',

    'inbox': '''
        CREATE TABLE IF NOT EXISTS inbox (
            id VARCHAR(64) PRIMARY KEY,
            content_id VARCHAR(64),
            raw_input TEXT NOT NULL,
            source_type VARCHAR(50),
            title VARCHAR(500),
            url TEXT,
            status VARCHAR(20) DEFAULT 'PENDING',
            priority INTEGER DEFAULT 0,
            quick_tags JSONB DEFAULT '[]'::jsonb,
            added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP WITH TIME ZONE,
            due_date DATE
        )
    ''',

    'links': '''
        CREATE TABLE IF NOT EXISTS links (
            id VARCHAR(64) PRIMARY KEY,
            source_id VARCHAR(64) NOT NULL,
            source_type VARCHAR(20) DEFAULT 'content',
            target_id VARCHAR(64) NOT NULL,
            target_type VARCHAR(20) DEFAULT 'content',
            link_type VARCHAR(50) NOT NULL,
            context TEXT,
            strength DECIMAL(3,2) DEFAULT 1.0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    ''',

    'tags': '''
        CREATE TABLE IF NOT EXISTS tags (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            color VARCHAR(20) DEFAULT '#666666',
            use_count INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    ''',

    'content_tags': '''
        CREATE TABLE IF NOT EXISTS content_tags (
            content_id VARCHAR(64) NOT NULL,
            tag_id INTEGER NOT NULL,
            tagged_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (content_id, tag_id)
        )
    ''',

    'node_contents': '''
        CREATE TABLE IF NOT EXISTS node_contents (
            node_id VARCHAR(64) NOT NULL,
            content_id VARCHAR(64) NOT NULL,
            added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (node_id, content_id)
        )
    ''',

    'creation_projects': '''
        CREATE TABLE IF NOT EXISTS creation_projects (
            id VARCHAR(64) PRIMARY KEY,
            project_type VARCHAR(50) NOT NULL,
            title VARCHAR(300) NOT NULL,
            brief TEXT,
            source_materials JSONB DEFAULT '[]'::jsonb,
            quotes JSONB DEFAULT '[]'::jsonb,
            inspirations JSONB DEFAULT '[]'::jsonb,
            outline JSONB DEFAULT '[]'::jsonb,
            sections JSONB DEFAULT '[]'::jsonb,
            draft_content TEXT,
            published_url TEXT,
            status VARCHAR(20) DEFAULT 'research',
            progress DECIMAL(3,2) DEFAULT 0.0,
            word_count_goal INTEGER,
            word_count_actual INTEGER DEFAULT 0,
            target_date DATE,
            published_at DATE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    ''',

    'learning_sessions': '''
        CREATE TABLE IF NOT EXISTS learning_sessions (
            id VARCHAR(64) PRIMARY KEY,
            content_id VARCHAR(64) NOT NULL,
            started_at TIMESTAMP WITH TIME ZONE NOT NULL,
            duration INTEGER DEFAULT 0,
            highlights_count INTEGER DEFAULT 0,
            notes_added INTEGER DEFAULT 0,
            links_created INTEGER DEFAULT 0,
            summary_layer INTEGER DEFAULT 0,
            comprehension INTEGER DEFAULT 3,
            confidence INTEGER DEFAULT 3,
            mood VARCHAR(50) DEFAULT 'calm',
            key_takeaways JSONB DEFAULT '[]'::jsonb,
            questions JSONB DEFAULT '[]'::jsonb,
            session_notes TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    '''
}

def main():
    print("Linker Mind - Initialize PostgreSQL Tables")
    print("=" * 60)

    try:
        pg = get_pg_connection(config)
        print(f"Connected to PostgreSQL at {config.host}:{config.port}/{config.database}")
        print()

        # Create tables
        with pg.get_connection() as conn:
            with conn.cursor() as cursor:
                for table_name, sql in TABLES.items():
                    try:
                        cursor.execute(sql)
                        print(f"✓ Created/verified table: {table_name}")
                    except Exception as e:
                        print(f"✗ Error creating {table_name}: {e}")
                        return 1

                conn.commit()

        print()
        print("=" * 60)
        print("All tables initialized successfully!")
        print("=" * 60)

        # Verify
        print()
        print("Tables in database:")
        for t in pg.get_tables():
            print(f"  - {t}")

        return 0

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
