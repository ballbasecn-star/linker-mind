"""
Unified Database Interface - PostgreSQL Only

This module provides a unified interface for PostgreSQL database.
The database type is automatically detected from environment configuration.

Environment Variables:
    DATABASE_URL - Full database URL (e.g., postgresql://user:pass@host:port/db)
    DB_TYPE - Explicit database type (always 'postgresql')
    PGHOST - PostgreSQL host (default: localhost)
    PGPORT - PostgreSQL port (default: 5432)
    PGDATABASE - PostgreSQL database name (default: linker_mind)
    PGUSER - PostgreSQL user (default: postgres)
    PGPASSWORD - PostgreSQL password

Usage:
    from database.db_interface import get_connection

    # Get PostgreSQL connection
    db = get_connection()

    # Initialize database
    from database.db_interface import init_database
    init_database()
"""
import os
import logging
from typing import Optional, Dict, List, Any, Tuple
from abc import ABC, abstractmethod
from contextlib import contextmanager
import json

logger = logging.getLogger(__name__)

# Database type constant
class DatabaseType:
    POSTGRESQL = 'postgresql'


class DatabaseConnectionInterface(ABC):
    """
    Abstract base class for database connections

    All database implementations must implement these methods
    to ensure compatibility across different backends.
    """

    @abstractmethod
    def execute(self, sql: str, params: Optional[Tuple] = None, fetch: bool = False) -> Any:
        """Execute a SQL query"""
        pass

    @abstractmethod
    def fetchall(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all results from a query"""
        pass

    @abstractmethod
    def fetchone(self, sql: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch one result from a query"""
        pass

    @abstractmethod
    def fetchval(self, sql: str, params: Optional[Tuple] = None) -> Any:
        """Fetch a single value from a query"""
        pass

    @abstractmethod
    def insert(self, table: str, data: Dict[str, Any]) -> Any:
        """Insert a row into a table"""
        pass

    @abstractmethod
    def update(self, table: str, data: Dict[str, Any],
               where: str = None, where_params: Tuple = None) -> int:
        """Update rows in a table"""
        pass

    @abstractmethod
    def delete(self, table: str, where: str = None, params: Tuple = None) -> int:
        """Delete rows from a table"""
        pass

    @abstractmethod
    def table_exists(self, table: str) -> bool:
        """Check if a table exists"""
        pass

    @abstractmethod
    def get_tables(self) -> List[str]:
        """Get list of all tables"""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close database connection"""
        pass

    @abstractmethod
    def __enter__(self):
        """Context manager entry"""
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        pass


class PostgreSQLAdapter(DatabaseConnectionInterface):
    """Adapter for PostgreSQL connection to match unified interface"""

    def __init__(self, pg_conn):
        from database.pg_connection import PostgreSQLConnection
        if not isinstance(pg_conn, PostgreSQLConnection):
            raise TypeError("Expected PostgreSQLConnection instance")
        self._conn = pg_conn

    def execute(self, sql: str, params: Optional[Tuple] = None, fetch: bool = False) -> Any:
        """Execute a SQL query"""
        return self._conn.execute(sql, params, fetch)

    def fetchall(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all results from a query"""
        return self._conn.fetchall(sql, params)

    def fetchone(self, sql: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch one result from a query"""
        return self._conn.fetchone(sql, params)

    def fetchval(self, sql: str, params: Optional[Tuple] = None) -> Any:
        """Fetch a single value from a query"""
        return self._conn.fetchval(sql, params)

    def insert(self, table: str, data: Dict[str, Any]) -> Any:
        """Insert a row into a table"""
        return self._conn.insert(table, data)

    def update(self, table: str, data: Dict[str, Any],
               where: str = None, where_params: Tuple = None) -> int:
        """Update rows in a table"""
        return self._conn.update(table, data, where, where_params)

    def delete(self, table: str, where: str = None, params: Tuple = None) -> int:
        """Delete rows from a table"""
        return self._conn.delete(table, where, params)

    def table_exists(self, table: str) -> bool:
        """Check if a table exists"""
        return self._conn.table_exists(table)

    def get_tables(self) -> List[str]:
        """Get list of all tables"""
        return self._conn.get_tables()

    def close(self) -> None:
        """Close database connection"""
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# Global connection instance
_connection: Optional[DatabaseConnectionInterface] = None
_db_type: Optional[str] = None


def detect_database_type() -> str:
    """
    Detect which database to use based on environment

    Always returns 'postgresql' since SQLite has been removed.

    Checks in order:
    1. DATABASE_URL environment variable
    2. DB_TYPE environment variable
    3. PostgreSQL environment variables (PGHOST, PGDATABASE)

    Returns:
        'postgresql'
    """
    # Check for DATABASE_URL (standard PostgreSQL URL format)
    db_url = os.getenv('DATABASE_URL', '')

    if db_url:
        if 'postgresql' in db_url or 'postgres' in db_url:
            return DatabaseType.POSTGRESQL

    # Check explicit DB_TYPE setting
    db_type = os.getenv('DB_TYPE', '').lower()
    if db_type == DatabaseType.POSTGRESQL:
        return DatabaseType.POSTGRESQL

    # Check for other PostgreSQL environment variables
    if os.getenv('PGHOST') or os.getenv('PGDATABASE'):
        return DatabaseType.POSTGRESQL

    # Default to PostgreSQL
    return DatabaseType.POSTGRESQL


def get_connection(
    db_type: Optional[str] = None
) -> DatabaseConnectionInterface:
    """
    Get the global database connection

    Args:
        db_type: Force specific database type (always 'postgresql')
                 If None, will auto-detect from environment

    Returns:
        DatabaseConnectionInterface instance (PostgreSQLAdapter)
    """
    global _connection, _db_type

    # Determine database type
    if db_type is None:
        db_type = detect_database_type()

    # If connection exists and type matches, return it
    if _connection is not None and _db_type == db_type:
        return _connection

    # Close existing connection if type changed
    if _connection is not None:
        logger.info(f"Switching database from {_db_type} to {db_type}")
        _connection.close()
        _connection = None

    # Create new PostgreSQL connection
    _connection = _create_postgresql_connection()
    _db_type = DatabaseType.POSTGRESQL
    logger.info("Using PostgreSQL database")

    return _connection


def _create_postgresql_connection() -> PostgreSQLAdapter:
    """Create PostgreSQL connection adapter"""
    from database.pg_connection import get_pg as get_postgresql_db
    pg_conn = get_postgresql_db()
    return PostgreSQLAdapter(pg_conn)


def init_database(
    db_type: Optional[str] = None,
    schema_file: Optional[str] = None
) -> bool:
    """
    Initialize PostgreSQL database with schema

    Args:
        db_type: Database type (always 'postgresql')
        schema_file: Optional schema file path

    Returns:
        True if successful
    """
    if db_type is None:
        db_type = detect_database_type()

    try:
        return _init_postgresql(schema_file)
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


def _init_postgresql(schema_file: Optional[str]) -> bool:
    """Initialize PostgreSQL database"""
    try:
        from database.pg_connection import init_postgresql, PostgreSQLConfig
        import os

        # Build configuration from environment
        if schema_file is None:
            schema_file = "database/schema_pg.sql"

        config = PostgreSQLConfig(
            host=os.getenv('PGHOST', 'localhost'),
            port=int(os.getenv('PGPORT', '5432')),
            database=os.getenv('PGDATABASE', 'linker-mind'),
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', ''),
            min_connections=2,
            max_connections=10
        )

        return init_postgresql(config, schema_file)

    except Exception as e:
        logger.error(f"PostgreSQL initialization failed: {e}")
        return False


def get_database_type() -> str:
    """Get current database type being used"""
    global _db_type
    if _db_type is None:
        _db_type = detect_database_type()
    return _db_type


def is_postgresql() -> bool:
    """Check if currently using PostgreSQL (always True)"""
    return get_database_type() == DatabaseType.POSTGRESQL


def reset_connection():
    """Reset global connection (for testing or switching databases)"""
    global _connection, _db_type
    if _connection:
        _connection.close()
    _connection = None
    _db_type = None
    logger.info("Database connection reset")


# JSON helper functions for PostgreSQL compatibility
# These functions work with PostgreSQL's JSONB type which automatically
# serializes/deserializes JSON data

def json_dumps(obj: Any) -> str:
    """
    Convert object to JSON string for storage

    Note: PostgreSQL JSONB handles JSON natively, but this function
    is kept for backward compatibility with existing code.
    """
    return json.dumps(obj, ensure_ascii=False)


def json_loads(value: Optional[str]) -> Any:
    """
    Parse JSON string from storage

    Note: PostgreSQL JSONB returns Python dict/list directly,
    but this function is kept for backward compatibility.
    """
    if value is None or value == '':
        return None
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def json_list(value: Optional[str]) -> List[Any]:
    """
    Parse JSON to list (or return list if already a list)

    Handles PostgreSQL JSONB (already deserialized) and strings.
    """
    if value is None or value == '':
        return []
    if isinstance(value, list):
        return value
    result = json_loads(value)
    return result if isinstance(result, list) else []


def json_dict(value: Optional[str]) -> Dict[str, Any]:
    """
    Parse JSON to dict (or return dict if already a dict)

    Handles PostgreSQL JSONB (already deserialized) and strings.
    """
    if value is None or value == '':
        return {}
    if isinstance(value, dict):
        return value
    result = json_loads(value)
    return result if isinstance(result, dict) else {}


if __name__ == "__main__":
    print("Unified Database Interface - PostgreSQL Only")
    print("=" * 50)

    # Test database detection
    detected = detect_database_type()
    print(f"Detected database type: {detected}")

    # Get connection
    db = get_connection()
    print(f"Active database: {get_database_type()}")
    print(f"Is PostgreSQL: {is_postgresql()}")

    # Test basic operations
    tables = db.get_tables()
    print(f"Tables: {tables}")

    print("\n✓ Database interface test complete!")
    print("\nPostgreSQL environment variables:")
    print("  export PGHOST=your_host")
    print("  export PGPORT=5432")
    print("  export PGDATABASE=linker-mind")
    print("  export PGUSER=postgres")
    print("  export PGPASSWORD=your_password")
