"""
Unified Database Interface - Supports both SQLite and PostgreSQL

This module provides a unified interface that can work with either
SQLite or PostgreSQL based on environment configuration.

Usage:
    from database.db_interface import get_connection

    # Will auto-detect and use the correct database
    db = get_connection()

    # Or specify explicitly
    from database.db_interface import init_database
    init_database(db_type='postgresql')  # or 'sqlite'
"""
import os
import logging
from typing import Optional, Dict, List, Any, Tuple, Union
from abc import ABC, abstractmethod
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Database type enum
class DatabaseType:
    SQLITE = 'sqlite'
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
        """Close the database connection"""
        pass

    @abstractmethod
    def __enter__(self):
        """Context manager entry"""
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        pass


class SQLiteAdapter(DatabaseConnectionInterface):
    """Adapter for SQLite connection to match the unified interface"""

    def __init__(self, sqlite_conn):
        from database.connection import DatabaseConnection
        if not isinstance(sqlite_conn, DatabaseConnection):
            raise TypeError("Expected DatabaseConnection instance")
        self._conn = sqlite_conn

    def execute(self, sql: str, params: Optional[Tuple] = None, fetch: bool = False) -> Any:
        """Execute a SQL query"""
        return self._conn.execute(sql, params or ())

    def fetchall(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all results from a query"""
        rows = self._conn.fetchall(sql, params or ())
        return [dict(row) for row in rows]

    def fetchone(self, sql: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch one result from a query"""
        row = self._conn.fetchone(sql, params or ())
        return dict(row) if row else None

    def fetchval(self, sql: str, params: Optional[Tuple] = None) -> Any:
        """Fetch a single value from a query"""
        return self._conn.fetchval(sql, params or ())

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
        """Close the database connection"""
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class PostgreSQLAdapter(DatabaseConnectionInterface):
    """Adapter for PostgreSQL connection to match the unified interface"""

    def __init__(self, pg_conn):
        from database.pg_connection import PostgreSQLConnection
        if not isinstance(pg_conn, PostgreSQLConnection):
            raise TypeError("Expected PostgreSQLConnection instance")
        self._conn = pg_conn

    def execute(self, sql: str, params: Optional[Tuple] = None, fetch: bool = False) -> Any:
        """Execute a SQL query"""
        # Convert SQLite syntax to PostgreSQL where needed
        sql = self._convert_sql(sql)
        return self._conn.execute(sql, params, fetch)

    def fetchall(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all results from a query"""
        sql = self._convert_sql(sql)
        return self._conn.fetchall(sql, params)

    def fetchone(self, sql: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch one result from a query"""
        sql = self._convert_sql(sql)
        return self._conn.fetchone(sql, params)

    def fetchval(self, sql: str, params: Optional[Tuple] = None) -> Any:
        """Fetch a single value from a query"""
        sql = self._convert_sql(sql)
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
        """Close the database connection"""
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def _convert_sql(self, sql: str) -> str:
        """Convert SQLite-specific SQL to PostgreSQL"""
        # Convert ? placeholders to %s (PostgreSQL style)
        # But only if we detect ? placeholders
        if '?' in sql and '%s' not in sql:
            # Count placeholders to avoid replacing ? inside string literals
            # Simple approach: replace ? with %s for parameters
            import re
            # This is a simple conversion - for complex queries, manual conversion may be needed
            sql = sql.replace('?', '%s')

        # Convert SQLite specific syntax if needed
        # Add more conversions as needed

        return sql


# Global connection instance
_connection: Optional[DatabaseConnectionInterface] = None
_db_type: Optional[str] = None


def detect_database_type() -> str:
    """
    Auto-detect which database to use based on environment

    Checks in order:
    1. DATABASE_URL environment variable
    2. DB_TYPE environment variable
    3. Defaults to 'sqlite'

    Returns:
        'postgresql' or 'sqlite'
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
    elif db_type == DatabaseType.SQLITE:
        return DatabaseType.SQLITE

    # Check for other PostgreSQL environment variables
    if os.getenv('PGHOST') or os.getenv('PGDATABASE'):
        return DatabaseType.POSTGRESQL

    # Default to SQLite
    return DatabaseType.SQLITE


def get_connection(
    db_type: Optional[str] = None,
    db_path: str = "linker_mind.db"
) -> DatabaseConnectionInterface:
    """
    Get the global database connection

    Args:
        db_type: Force specific database type ('sqlite' or 'postgresql')
                 If None, will auto-detect from environment
        db_path: Path to SQLite database (only used for SQLite)

    Returns:
        DatabaseConnectionInterface instance
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

    # Create new connection based on type
    if db_type == DatabaseType.POSTGRESQL:
        _connection = _create_postgresql_connection()
        _db_type = DatabaseType.POSTGRESQL
        logger.info("Using PostgreSQL database")
    else:
        _connection = _create_sqlite_connection(db_path)
        _db_type = DatabaseType.SQLITE
        logger.info("Using SQLite database")

    return _connection


def _create_sqlite_connection(db_path: str) -> SQLiteAdapter:
    """Create SQLite connection adapter"""
    from database.connection import get_db as get_sqlite_db
    sqlite_conn = get_sqlite_db(db_path)
    return SQLiteAdapter(sqlite_conn)


def _create_postgresql_connection() -> PostgreSQLAdapter:
    """Create PostgreSQL connection adapter"""
    from database.pg_connection import get_pg as get_postgresql_db
    pg_conn = get_postgresql_db()
    return PostgreSQLAdapter(pg_conn)


def init_database(
    db_type: Optional[str] = None,
    db_path: str = "linker_mind.db",
    schema_file: Optional[str] = None
) -> bool:
    """
    Initialize the database with schema

    Args:
        db_type: Database type ('sqlite' or 'postgresql')
        db_path: Path to SQLite database (only for SQLite)
        schema_file: Optional schema file path

    Returns:
        True if successful
    """
    if db_type is None:
        db_type = detect_database_type()

    try:
        if db_type == DatabaseType.POSTGRESQL:
            return _init_postgresql(schema_file)
        else:
            return _init_sqlite(db_path, schema_file)
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


def _init_sqlite(db_path: str, schema_file: Optional[str]) -> bool:
    """Initialize SQLite database"""
    from database.connection import init_database as init_sqlite_db
    return init_sqlite_db(db_path, schema_file)


def _init_postgresql(schema_file: Optional[str]) -> bool:
    """Initialize PostgreSQL database"""
    try:
        from database.pg_connection import init_postgresql, PostgreSQLConfig, get_pg_connection
        import os

        # Build configuration from environment
        if schema_file is None:
            schema_file = "database/schema_pg.sql"

        config = PostgreSQLConfig(
            host=os.getenv('PGHOST', 'localhost'),
            port=int(os.getenv('PGPORT', 5432)),
            database=os.getenv('PGDATABASE', 'linker_mind'),
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
    """Get the current database type being used"""
    global _db_type
    if _db_type is None:
        _db_type = detect_database_type()
    return _db_type


def is_postgresql() -> bool:
    """Check if currently using PostgreSQL"""
    return get_database_type() == DatabaseType.POSTGRESQL


def is_sqlite() -> bool:
    """Check if currently using SQLite"""
    return get_database_type() == DatabaseType.SQLITE


def reset_connection():
    """Reset the global connection (for testing or switching databases)"""
    global _connection, _db_type
    if _connection:
        _connection.close()
    _connection = None
    _db_type = None
    logger.info("Database connection reset")


if __name__ == "__main__":
    print("Unified Database Interface")
    print("=" * 50)

    # Test database detection
    detected = detect_database_type()
    print(f"Detected database type: {detected}")

    # Get connection
    db = get_connection()
    print(f"Active database: {get_database_type()}")
    print(f"Is PostgreSQL: {is_postgresql()}")
    print(f"Is SQLite: {is_sqlite()}")

    # Test basic operations
    tables = db.get_tables()
    print(f"Tables: {tables}")

    print("\n✓ Database interface test complete!")
    print("\nTo use PostgreSQL, set environment variable:")
    print("  export DATABASE_URL=postgresql://user:pass@host:port/database")
    print("  export DB_TYPE=postgresql")
