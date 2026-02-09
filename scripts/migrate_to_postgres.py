#!/usr/bin/env python3
"""
PostgreSQL Migration Runner

This script migrates data from SQLite to PostgreSQL.

Usage:
    # Run migration (will use settings from .env)
    python scripts/migrate_to_postgres.py

    # Run with specific settings
    python scripts/migrate_to_postgres.py --host localhost --db linker_mind

    # Skip existing records (idempotent)
    python scripts/migrate_to_postgres.py --skip-existing

    # Dry run (show what would be migrated)
    python scripts/migrate_to_postgres.py --dry-run
"""
import sys
import os
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
        logger.info("Install with: pip install python-dotenv")
        return

    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded environment variables from {env_path}")
    else:
        logger.warning(f".env file not found at {env_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Migrate Linker Mind database from SQLite to PostgreSQL'
    )
    parser.add_argument(
        '--host',
        help='PostgreSQL host (default: from env or localhost)',
        default=None
    )
    parser.add_argument(
        '--port',
        type=int,
        help='PostgreSQL port (default: from env or 5432)',
        default=None
    )
    parser.add_argument(
        '--database', '--db',
        help='PostgreSQL database name (default: from env or linker_mind)',
        default=None
    )
    parser.add_argument(
        '--user',
        help='PostgreSQL user (default: from env or postgres)',
        default=None
    )
    parser.add_argument(
        '--password',
        help='PostgreSQL password (default: from env)',
        default=None
    )
    parser.add_argument(
        '--sqlite-db',
        help='Path to SQLite database (default: linker_mind.db)',
        default='linker_mind.db'
    )
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='Skip records that already exist in PostgreSQL'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of records to process per batch (default: 100)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show migration plan without executing'
    )
    parser.add_argument(
        '--init-only',
        action='store_true',
        help='Only initialize PostgreSQL schema, skip migration'
    )

    args = parser.parse_args()

    # Load environment variables
    load_env_vars()

    # Import migration module
    try:
        from database.migration_pg import SQLiteToPostgreSQLMigrator
        from database.pg_connection import PostgreSQLConfig, get_pg_connection
    except ImportError as e:
        logger.error(f"Failed to import migration modules: {e}")
        logger.error("Make sure psycopg2-binary is installed:")
        logger.error("  pip install psycopg2-binary")
        return 1

    # Build PostgreSQL config
    config = PostgreSQLConfig(
        host=args.host or os.getenv('PGHOST', 'localhost'),
        port=args.port or int(os.getenv('PGPORT', 5432)),
        database=args.database or os.getenv('PGDATABASE', 'linker_mind'),
        user=args.user or os.getenv('PGUSER', 'postgres'),
        password=args.password or os.getenv('PGPASSWORD', ''),
        min_connections=2,
        max_connections=10
    )

    # Check if SQLite database exists
    sqlite_path = Path(args.sqlite_db)
    if not sqlite_path.exists():
        logger.error(f"SQLite database not found: {sqlite_path}")
        logger.error("Please make sure the SQLite database exists before migrating.")
        return 1

    # Initialize migrator
    logger.info("=" * 60)
    logger.info("Linker Mind - PostgreSQL Migration")
    logger.info("=" * 60)
    logger.info(f"SQLite: {sqlite_path}")
    logger.info(f"PostgreSQL: {config.host}:{config.port}/{config.database}")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info("=" * 60)

    try:
        # Test PostgreSQL connection
        logger.info("Testing PostgreSQL connection...")
        pg_conn = get_pg_connection(config)

        # Check tables
        tables = pg_conn.get_tables()
        logger.info(f"PostgreSQL tables found: {len(tables)}")

        if args.init_only:
            logger.info("Initializing PostgreSQL schema...")
            from database.pg_connection import init_postgresql
            schema_file = project_root / "database" / "schema_pg.sql"

            if init_postgresql(config, schema_file):
                logger.info("✓ PostgreSQL schema initialized successfully")
                return 0
            else:
                logger.error("✗ Failed to initialize PostgreSQL schema")
                return 1

        # Create migrator
        migrator = SQLiteToPostgreSQLMigrator(
            sqlite_path=str(sqlite_path),
            pg_config=config
        )

        # Pre-migration check
        logger.info("\nPre-migration check...")
        sqlite_tables = migrator._get_sqlite_tables()
        logger.info(f"SQLite tables: {sqlite_tables}")

        if args.dry_run:
            logger.info("\nMigration plan:")
            for table in sqlite_tables:
                count = migrator._get_sqlite_table_count(table)
                logger.info(f"  - {table}: {count} records")
            logger.info("\nTo run migration, remove --dry-run flag")
            return 0

        # Run migration
        logger.info("\nStarting migration...")
        logger.info("-" * 60)

        results = migrator.migrate_all(
            skip_existing=args.skip_existing,
            batch_size=args.batch_size
        )

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

        # Post-migration check
        logger.info("\nPost-migration verification...")
        pg_tables = pg_conn.get_tables()
        logger.info(f"PostgreSQL tables: {pg_tables}")

        # Compare counts
        logger.info("\nRecord count comparison:")
        all_match = True
        for table in sqlite_tables:
            if table in pg_tables:
                sqlite_count = migrator._get_sqlite_table_count(table)
                pg_count = migrator._get_pg_table_count(table)
                match = "✓" if sqlite_count == pg_count else "✗"
                if sqlite_count != pg_count:
                    all_match = False
                logger.info(f"  {match} {table}: SQLite={sqlite_count}, PG={pg_count}")

        if all_match:
            logger.info("\n✓ All records migrated successfully!")
        else:
            logger.warning("\n⚠ Some record counts don't match. Check the logs above.")

        logger.info("\n" + "=" * 60)
        logger.info("Migration complete!")
        logger.info("=" * 60)
        logger.info("\nNext steps:")
        logger.info("1. Update .env to set DB_TYPE=postgresql")
        logger.info("2. Restart your application")
        logger.info("3. Verify data integrity")
        logger.info("\nTo switch back to SQLite, set DB_TYPE=sqlite")

        return 0

    except Exception as e:
        logger.error(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
