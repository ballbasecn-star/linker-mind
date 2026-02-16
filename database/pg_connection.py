"""
PostgreSQL Database Connection Module

This module provides PostgreSQL-specific database operations
for Linker Mind v2.0, using psycopg2 with connection pooling.
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from contextlib import contextmanager
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

# Try to import psycopg2 with extras
try:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import pool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 not available. Install with: pip install psycopg2-binary")


@dataclass
class PostgreSQLConfig:
    """PostgreSQL connection configuration"""
    host: str
    port: int
    database: str
    user: str
    password: str
    min_connections: int = 1
    max_connections: int = 10
    connection_timeout: int = 30

    @classmethod
    def from_url(cls, url: str) -> 'PostgreSQLConfig':
        """Create config from JDBC URL format"""
        # Parse URL: jdbc:postgresql://host:port/database
        import re
        pattern = r'jdbc:postgresql://([^:]+):(\d+)/([^/]+)(?:\?([^=]+)=([^&]+))?'
        match = re.match(pattern, url)
        if not match:
            raise ValueError(f"Invalid PostgreSQL URL: {url}")

        config = cls(
            host=match.group(1),
            port=int(match.group(2)),
            database=match.group(3),
            user='',
            password=''
        )

        # Extract username and password from query params if present
        if match.group(4):
            params = match.group(4)
            if 'user=' in params:
                config.user = params.split('user=')[1].split('&')[0]
            if 'password=' in params:
                config.password = params.split('password=')[1].split('&')[0]

        return config


class PostgreSQLConnection:
    """
    PostgreSQL connection manager with connection pooling

    Provides thread-safe database operations with automatic
    connection pooling and query execution.
    """

    def __init__(self, config: PostgreSQLConfig):
        """Initialize PostgreSQL connection with pooling"""
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError(
                "PostgreSQL support not available. "
                "Install with: pip install psycopg2-binary"
            )

        self.config = config
        self._pool = None
        self._connect()

    def _connect(self):
        """Initialize connection pool"""
        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=self.config.min_connections,
                maxconn=self.config.max_connections,
                dsn=self._build_dsn(),
            )
            logger.info(f"PostgreSQL connection pool created: {self.config.database}")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

    def _build_dsn(self) -> str:
        """Build DSN string from config"""
        return (
            f"host={self.config.host} "
            f"port={self.config.port} "
            f"dbname={self.config.database} "
            f"user={self.config.user} "
            f"password={self.config.password}"
        )

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        if not self._pool:
            raise RuntimeError("Connection pool not initialized")

        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def _convert_sql(self, sql: str) -> str:
        """
        Convert SQLite-style SQL to PostgreSQL

        Converts ? placeholders to %s
        """
        # Convert ? placeholders to %s (PostgreSQL style)
        # But only if we detect ? placeholders
        if '?' in sql and '%s' not in sql:
            sql = sql.replace('?', '%s')
        return sql

    def execute(self, sql: str, params: Tuple = None, fetch: bool = False) -> Any:
        """
        Execute a SQL query

        Args:
            sql: SQL query string
            params: Query parameters
            fetch: Whether to fetch results

        Returns:
            Query results if fetch=True, else row count
        """
        # Convert SQLite-style placeholders to PostgreSQL
        sql = self._convert_sql(sql)

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                try:
                    cursor.execute(sql, params)
                    conn.commit()

                    if fetch:
                        columns = [desc[0] for desc in cursor.description]
                        results = cursor.fetchall()
                        # Convert to list of dicts
                        return [dict(row) for row in results]

                    return cursor.rowcount

                except Exception as e:
                    conn.rollback()
                    logger.error(f"Query failed: {sql}, Error: {e}")
                    raise

    def execute_many(self, sql: str, params_list: List[Tuple]) -> int:
        """Execute multiple queries (batch insert)"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.executemany(sql, params_list)
                    conn.commit()
                    return cursor.rowcount
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Batch execute failed: {e}")
                    raise

    def fetchall(self, sql: str, params: Tuple = None) -> List[Dict[str, Any]]:
        """Fetch all results from a query"""
        return self.execute(sql, params, fetch=True)

    def fetchone(self, sql: str, params: Tuple = None) -> Optional[Dict[str, Any]]:
        """Fetch one result from a query"""
        results = self.fetchall(sql, params)
        return results[0] if results else None

    def fetchval(self, sql: str, params: Tuple = None) -> Any:
        """Fetch a single value from a query"""
        result = self.fetchone(sql, params)
        if result:
            # Return first column value
            return list(result.values())[0] if result else None
        return None

    def insert(self, table: str, data: Dict[str, Any]) -> str:
        """
        Insert a row into a table

        Returns:
            ID of inserted row
        """
        columns = list(data.keys())
        values = list(data.values())
        placeholders = ', '.join(['%s'] * len(values))

        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) RETURNING id"

        result = self.fetchone(sql, tuple(values))
        return result['id'] if result else None

    def update(self, table: str, data: Dict[str, Any],
               where: str = None, where_params: Tuple = None) -> int:
        """Update rows in a table"""
        if not data:
            return 0

        updates = [f"{k} = %s" for k in data.keys()]
        sql = f"UPDATE {table} SET {', '.join(updates)}"

        if where:
            sql += f" WHERE {where}"

        # Combine data values with where_params
        params = list(data.values())
        if where_params:
            params.extend(list(where_params))

        return self.execute(sql, tuple(params))

    def delete(self, table: str, where: str = None, params: Tuple = None) -> int:
        """Delete rows from a table"""
        sql = f"DELETE FROM {table}"
        if where:
            sql += f" WHERE {where}"

        return self.execute(sql, params)

    def table_exists(self, table: str) -> bool:
        """Check if a table exists"""
        sql = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = %s
            )
        """
        result = self.fetchval(sql, (table,))
        return result if isinstance(result, bool) else result == 1

    def get_tables(self) -> List[str]:
        """Get list of all tables"""
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        results = self.fetchall(sql)
        return [r['table_name'] for r in results]

    def vacuum(self) -> None:
        """Vacuum database to reclaim space"""
        self.execute("VACUUM ANALYZE")

    def close(self) -> None:
        """Close all connections"""
        if self._pool:
            self._pool.closeall()
            logger.info("PostgreSQL connection pool closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Global connection instance
_pg_connection: Optional[PostgreSQLConnection] = None


def get_pg_connection(config: PostgreSQLConfig = None) -> PostgreSQLConnection:
    """
    Get or create global PostgreSQL connection

    Args:
        config: PostgreSQL configuration (uses default if None)

    Returns:
        PostgreSQLConnection instance
    """
    global _pg_connection

    if _pg_connection is None:
        if config is None:
            raise ValueError("PostgreSQL configuration required for first connection")

        _pg_connection = PostgreSQLConnection(config)

    return _pg_connection


def get_pg(db_path: str = "linker_mind") -> PostgreSQLConnection:
    """
    Convenience function to get PG connection by database name

    Args:
        db_path: Database name (not full path, used for default config)

    Returns:
        PostgreSQLConnection instance
    """
    # Load from environment if available
    import os
    from urllib.parse import parse_qs

    db_url = os.getenv('DATABASE_URL')

    if db_url:
        # Support both jdbc:postgresql:// and postgresql:// formats
        if db_url.startswith('jdbc:'):
            config = PostgreSQLConfig.from_url(db_url)
            # Override with individual environment variables if present
            # This allows credentials to be specified separately
            if os.getenv('PGUSER'):
                config.user = os.getenv('PGUSER')
            if os.getenv('PGPASSWORD'):
                config.password = os.getenv('PGPASSWORD')
            if os.getenv('PGHOST'):
                config.host = os.getenv('PGHOST')
            if os.getenv('PGPORT'):
                config.port = int(os.getenv('PGPORT'))
            if os.getenv('PGDATABASE'):
                config.database = os.getenv('PGDATABASE')
            logger.debug(f"Using JDBC URL with env override: host={config.host}, db={config.database}, user={config.user}")
        else:
            # Parse postgresql:// format
            from urllib.parse import urlparse
            parsed = urlparse(db_url)

            # Get credentials from URL or environment
            username = parsed.username or os.getenv('PGUSER', 'postgres')
            password = parsed.password or os.getenv('PGPASSWORD', '')

            config = PostgreSQLConfig(
                host=parsed.hostname or os.getenv('PGHOST', 'localhost'),
                port=parsed.port or int(os.getenv('PGPORT', 5432)),
                database=parsed.path.lstrip('/') if parsed.path else os.getenv('PGDATABASE', db_path),
                user=username,
                password=password,
                min_connections=2,
                max_connections=10
            )
            logger.debug(f"Using postgresql:// URL: host={config.host}, db={config.database}, user={config.user}")
    else:
        # Build config from environment variables or use defaults
        config = PostgreSQLConfig(
            host=os.getenv('PGHOST', 'localhost'),
            port=int(os.getenv('PGPORT', 5432)),
            database=os.getenv('PGDATABASE', db_path),
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', ''),
            min_connections=2,
            max_connections=10
        )
        logger.debug(f"Using env vars: host={config.host}, db={config.database}, user={config.user}")

    logger.info(f"Connecting to PostgreSQL: {config.host}:{config.port}/{config.database} as {config.user}")
    return get_pg_connection(config)


def _split_postgresql_sql(sql: str) -> list:
    """
    Split PostgreSQL SQL into individual statements, respecting $$ quoting

    This properly handles:
    - $$ dollar-quoted strings
    - Nested functions
    - CREATE FUNCTION, CREATE TRIGGER, etc.
    """
    statements = []
    current_statement = []
    in_dollar_quote = False
    dollar_tag = None
    paren_depth = 0
    i = 0

    while i < len(sql):
        char = sql[i]

        # Check for dollar quoting start/end
        if not in_dollar_quote and char == '$':
            # Check if this is the start of a dollar quote
            if i + 1 < len(sql) and sql[i + 1] == '$':
                # Found $$
                in_dollar_quote = True
                dollar_tag = '$$'
                current_statement.append('$$')
                i += 2
                continue
            elif i + 1 < len(sql) and sql[i + 1].isalpha():
                # Check for $tag$ format
                j = i + 1
                while j < len(sql) and (sql[j].isalpha() or sql[j] == '_'):
                    j += 1
                if j < len(sql) and sql[j] == '$' and j + 1 < len(sql) and sql[j + 1] == '$':
                    tag = sql[i:j+2]
                    in_dollar_quote = True
                    dollar_tag = tag
                    current_statement.append(tag)
                    i = j + 2
                    continue

        if in_dollar_quote:
            # Check for end of dollar quote
            if char == '$' and i + len(dollar_tag) <= len(sql):
                end_tag = sql[i:i+len(dollar_tag)]
                if end_tag == dollar_tag:
                    in_dollar_quote = False
                    current_statement.append(dollar_tag)
                    i += len(dollar_tag)
                    continue
            current_statement.append(char)
            i += 1
            continue

        # Track parentheses for function bodies
        if char == '(':
            paren_depth += 1
        elif char == ')':
            paren_depth -= 1

        # Split on semicolons (but not inside functions/triggers)
        if char == ';' and paren_depth == 0:
            current_statement.append(char)
            statement = ''.join(current_statement).strip()
            if statement and not statement.startswith('--'):
                statements.append(statement)
            current_statement = []
            i += 1
            # Skip whitespace after semicolon
            while i < len(sql) and sql[i].isspace():
                i += 1
            continue

        current_statement.append(char)
        i += 1

    # Add remaining statement
    if current_statement:
        statement = ''.join(current_statement).strip()
        if statement and not statement.startswith('--'):
            statements.append(statement)

    return statements


def init_postgresql(config: PostgreSQLConfig, schema_file: str = None) -> bool:
    """
    Initialize PostgreSQL database with schema

    Args:
        config: PostgreSQL configuration
        schema_file: Optional SQL schema file

    Returns:
        True if successful
    """
    try:
        pg = get_pg_connection(config)

        # Read schema file
        if schema_file is None:
            schema_file = "database/schema_pg.sql"

        import os
        if not os.path.exists(schema_file):
            logger.warning(f"Schema file not found: {schema_file}")
            return False

        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        # Split and execute schema statements
        # Need to handle PostgreSQL's $$ quoting properly
        statements = _split_postgresql_sql(schema_sql)

        with pg.get_connection() as conn:
            with conn.cursor() as cursor:
                for statement in statements:
                    if statement.strip():
                        try:
                            cursor.execute(statement)
                            conn.commit()
                        except Exception as e:
                            logger.warning(f"Schema statement failed: {e}")
                            logger.debug(f"Statement: {statement[:100]}")
                            # Continue with other statements

        logger.info(f"PostgreSQL database initialized: {config.database}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL: {e}")
        return False


def json_dumps(obj: Any) -> str:
    """
    Convert Python object to JSON string for PostgreSQL

    Args:
        obj: Python object to serialize

    Returns:
        JSON string
    """
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False)


def json_list(value: Optional[str]) -> List[Any]:
    """
    Parse JSON string to list for PostgreSQL

    Handles both JSON strings and already-deserialized Python lists
    (PostgreSQL JSONB columns are automatically deserialized by psycopg2)

    Args:
        value: JSON string, Python list, or None

    Returns:
        Parsed list or empty list
    """
    if value is None or value == '':
        return []
    # If already a list (PostgreSQL JSONB), return as-is
    if isinstance(value, list):
        return value
    # Otherwise parse as JSON string
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def json_dict(value: Optional[str]) -> Dict[str, Any]:
    """
    Parse JSON string to dict for PostgreSQL

    Handles both JSON strings and already-deserialized Python dicts
    (PostgreSQL JSONB columns are automatically deserialized by psycopg2)

    Args:
        value: JSON string, Python dict, or None

    Returns:
        Parsed dict or empty dict
    """
    if value is None or value == '':
        return {}
    # If already a dict (PostgreSQL JSONB), return as-is
    if isinstance(value, dict):
        return value
    # Otherwise parse as JSON string
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


if __name__ == "__main__":
    # Test PostgreSQL connection
    print("PostgreSQL Connection Module")
    print("=" * 50)

    if not PSYCOPG2_AVAILABLE:
        print("❌ psycopg2 not available")
        print("\nInstall with:")
        print("  pip install psycopg2-binary")
        print("\nOr with full features:")
        print("  pip install psycopg2")
    else:
        print("✅ psycopg2 is available")
        print("\nEnvironment variables for connection:")
        print("  DATABASE_URL - Full PostgreSQL URL")
        print("  PGHOST - Database host")
        print("  PGPORT - Database port (default: 5432)")
        print("  PGDATABASE - Database name")
        print("  PGUSER - Database user")
        print("  PGPASSWORD - Database password")

        print("\n✓ PostgreSQL connection module loaded!")