"""
Database Package - Unified PostgreSQL interface for Linker Mind

This package provides a unified interface for PostgreSQL database.
The database type is automatically detected from environment variables.

Environment Variables:
    DATABASE_URL - Full database URL (e.g., postgresql://user:pass@host:port/db)
    DB_TYPE - Explicit database type (always 'postgresql')
    PGHOST - PostgreSQL host (default: localhost)
    PGPORT - PostgreSQL port (default: 5432)
    PGDATABASE - PostgreSQL database name (default: linker_mind)
    PGUSER - PostgreSQL user (default: postgres)
    PGPASSWORD - PostgreSQL password

Usage:
    from database import get_connection, init_database

    # Initialize database
    init_database()

    # Get connection
    db = get_connection()

    # Use connection
    results = db.fetchall("SELECT * FROM contents")
"""

# Version info
__version__ = "2.0.0"

# Import unified interface
from database.db_interface import (
    get_connection,
    init_database,
    get_database_type,
    is_postgresql,
    reset_connection,
    DatabaseConnectionInterface,
    DatabaseType,
    # JSON helper functions for PostgreSQL compatibility
    json_dumps,
    json_loads,
    json_list,
    json_dict
)

# Export main functions
__all__ = [
    'get_connection',
    'init_database',
    'get_database_type',
    'is_postgresql',
    'reset_connection',
    'DatabaseConnectionInterface',
    'DatabaseType',
    'json_dumps',
    'json_loads',
    'json_list',
    'json_dict',
]
