"""
Database Connection Module - SQLite database management

This module handles:
- SQLite database connection management
- Connection pooling
- Database initialization
- Migration support
"""
import sqlite3
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Thread-safe SQLite database connection manager with connection pooling
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = "linker_mind.db"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = "linker_mind.db"):
        if self._initialized:
            return

        self.db_path = Path(db_path)
        self._local = threading.local()
        self._initialized = True
        self._ensure_database_exists()

    def _ensure_database_exists(self):
        """Create database directory if it doesn't exist"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            # Enable foreign keys
            self._local.conn.execute("PRAGMA foreign_keys = ON")
            # Set WAL mode for better concurrency
            self._local.conn.execute("PRAGMA journal_mode = WAL")
            # Set optimization settings
            self._local.conn.execute("PRAGMA synchronous = NORMAL")
            self._local.conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()

    def execute(self, sql: str, params: Optional[Tuple] = None) -> sqlite3.Cursor:
        """Execute a SQL statement"""
        conn = self._get_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        conn.commit()
        return cursor

    def executemany(self, sql: str, params: List[Tuple]) -> sqlite3.Cursor:
        """Execute a SQL statement with multiple parameter sets"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.executemany(sql, params)
        conn.commit()
        return cursor

    def fetchone(self, sql: str, params: Optional[Tuple] = None) -> Optional[sqlite3.Row]:
        """Fetch a single row"""
        cursor = self.execute(sql, params)
        return cursor.fetchone()

    def fetchall(self, sql: str, params: Optional[Tuple] = None) -> List[sqlite3.Row]:
        """Fetch all rows"""
        cursor = self.execute(sql, params)
        return cursor.fetchall()

    def fetchval(self, sql: str, params: Optional[Tuple] = None) -> Any:
        """Fetch a single value from the first column"""
        row = self.fetchone(sql, params)
        return row[0] if row else None

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """
        Insert a row into a table

        Args:
            table: Table name
            data: Dictionary of column names and values

        Returns:
            Last inserted row ID
        """
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        cursor = self.execute(sql, tuple(data.values()))
        return cursor.lastrowid

    def update(self, table: str, data: Dict[str, Any], where: str, where_params: Optional[Tuple] = None) -> int:
        """
        Update rows in a table

        Args:
            table: Table name
            data: Dictionary of column names and values to update
            where: WHERE clause (without the WHERE keyword)
            where_params: Parameters for the WHERE clause

        Returns:
            Number of rows updated
        """
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        params = tuple(data.values()) + (where_params or ())
        cursor = self.execute(sql, params)
        return cursor.rowcount

    def delete(self, table: str, where: str, where_params: Optional[Tuple] = None) -> int:
        """
        Delete rows from a table

        Args:
            table: Table name
            where: WHERE clause (without the WHERE keyword)
            where_params: Parameters for the WHERE clause

        Returns:
            Number of rows deleted
        """
        sql = f"DELETE FROM {table} WHERE {where}"
        cursor = self.execute(sql, where_params)
        return cursor.rowcount

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        result = self.fetchval(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return result is not None

    def get_tables(self) -> List[str]:
        """Get list of all tables"""
        rows = self.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row['name'] for row in rows]

    def close(self):
        """Close the database connection for the current thread"""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    def backup(self, backup_path: str) -> bool:
        """
        Create a backup of the database

        Args:
            backup_path: Path for the backup file

        Returns:
            True if successful
        """
        try:
            backup = sqlite3.connect(backup_path)
            conn = self._get_connection()
            conn.backup(backup)
            backup.close()
            logger.info(f"Database backed up to {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False

    def vacuum(self):
        """Vacuum the database to reclaim space"""
        self.execute("VACUUM")
        logger.info("Database vacuumed")

    def analyze(self):
        """Run ANALYZE to update statistics"""
        self.execute("ANALYZE")
        logger.info("Database analyzed")


# Global database connection instance
_db_connection: Optional[DatabaseConnection] = None


def get_db(db_path: str = "linker_mind.db") -> DatabaseConnection:
    """Get the global database connection instance"""
    global _db_connection
    if _db_connection is None:
        _db_connection = DatabaseConnection(db_path)
    return _db_connection


def init_database(db_path: str = "linker_mind.db", schema_path: Optional[str] = None) -> bool:
    """
    Initialize the database with schema

    Args:
        db_path: Path to the database file
        schema_path: Path to the schema SQL file (optional)

    Returns:
        True if successful
    """
    db = get_db(db_path)

    # Check if database is already initialized
    if db.table_exists('contents'):
        logger.info("Database already initialized")
        return True

    # Load and execute schema
    if schema_path is None:
        schema_path = Path(__file__).parent / "schema.sql"

    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        # Split and execute individual statements
        # SQLite doesn't support multiple statements in execute()
        for statement in schema_sql.split(';'):
            statement = statement.strip()
            if statement:
                db.execute(statement)

        logger.info(f"Database initialized at {db_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


def reset_database(db_path: str = "linker_mind.db") -> bool:
    """
    Reset the database (delete and recreate)

    Args:
        db_path: Path to the database file

    Returns:
        True if successful
    """
    global _db_connection

    # Close existing connection
    if _db_connection:
        _db_connection.close()
        _db_connection = None

    # Delete the database file
    db_file = Path(db_path)
    wal_file = db_file.with_suffix('.db-wal')
    shm_file = db_file.with_suffix('.db-shm')

    try:
        if db_file.exists():
            db_file.unlink()
        if wal_file.exists():
            wal_file.unlink()
        if shm_file.exists():
            shm_file.unlink()

        # Reinitialize
        return init_database(db_path)
    except Exception as e:
        logger.error(f"Failed to reset database: {e}")
        return False


# JSON helper functions for SQLite
def json_dumps(obj: Any) -> str:
    """Convert object to JSON string for storage"""
    return json.dumps(obj, ensure_ascii=False)


def json_loads(value: Optional[str]) -> Any:
    """Parse JSON string from storage"""
    if value is None or value == '':
        return None
    return json.loads(value)


def json_list(value: Optional[str]) -> List[Any]:
    """
    Parse JSON string to list (or return list if already a list)

    Handles both SQLite (JSON string) and PostgreSQL (already deserialized)
    """
    if value is None or value == '':
        return []
    # If already a list (PostgreSQL JSONB), return as-is
    if isinstance(value, list):
        return value
    # Otherwise parse as JSON string (SQLite)
    result = json_loads(value)
    return result if isinstance(result, list) else []


def json_dict(value: Optional[str]) -> Dict[str, Any]:
    """
    Parse JSON string to dict (or return dict if already a dict)

    Handles both SQLite (JSON string) and PostgreSQL (already deserialized)
    """
    if value is None or value == '':
        return {}
    # If already a dict (PostgreSQL JSONB), return as-is
    if isinstance(value, dict):
        return value
    # Otherwise parse as JSON string (SQLite)
    result = json_loads(value)
    return result if isinstance(result, dict) else {}


if __name__ == "__main__":
    # Test the database connection
    print("Testing database connection...")

    # Initialize database
    if init_database(":memory:"):
        print("✓ Database initialized successfully")

        db = get_db(":memory:")

        # Test basic operations
        db.insert("contents", {
            "id": "test_001",
            "source_type": "test",
            "content_type": "article",
            "title": "Test Content",
            "url": "https://example.com",
            "summary": "This is a test",
            "main_content": "Test content body",
            "archived": 0,
            "favorited": 0,
            "reading_progress": 0.0
        })

        # Query the test content
        row = db.fetchone("SELECT * FROM contents WHERE id = ?", ("test_001",))
        if row:
            print(f"✓ Inserted and retrieved content: {row['title']}")

        # List all tables
        tables = db.get_tables()
        print(f"✓ Tables created: {len(tables)}")

        # Test JSON helpers
        test_list = ["tag1", "tag2", "tag3"]
        json_str = json_dumps(test_list)
        parsed = json_list(json_str)
        print(f"✓ JSON helpers work: {parsed}")

        print("\n✓ All database tests passed!")
    else:
        print("✗ Database initialization failed")
