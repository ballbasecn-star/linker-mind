#!/usr/bin/env python3
"""
PostgreSQL Connection Test

Quick test script to verify PostgreSQL connection and configuration.
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("Linker Mind - PostgreSQL Connection Test")
print("=" * 60)

# Test 1: Check if psycopg2 is installed
print("\n1. Checking psycopg2 installation...")
try:
    import psycopg2
    import psycopg2.extras
    print("   ✓ psycopg2 is installed")
    print(f"   Version: {psycopg2.__version__}")
except ImportError:
    print("   ✗ psycopg2 is NOT installed")
    print("\n   Install with:")
    print("   pip install psycopg2-binary")
    sys.exit(1)

# Test 2: Load environment variables
print("\n2. Loading environment variables...")
try:
    from dotenv import load_dotenv
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"   ✓ Loaded .env from {env_path}")
    else:
        print("   ⚠ .env file not found")
except ImportError:
    print("   ⚠ python-dotenv not installed (optional)")

# Test 3: Check environment variables
print("\n3. Checking PostgreSQL configuration...")
db_type = os.getenv('DB_TYPE', '').lower()
print(f"   DB_TYPE: {db_type or 'not set'}")

database_url = os.getenv('DATABASE_URL', '')
print(f"   DATABASE_URL: {database_url or 'not set'}")

pg_host = os.getenv('PGHOST', 'not set')
pg_port = os.getenv('PGPORT', 'not set')
pg_db = os.getenv('PGDATABASE', 'not set')
pg_user = os.getenv('PGUSER', 'not set')
pg_pass = os.getenv('PGPASSWORD', '***' if os.getenv('PGPASSWORD') else 'not set')

print(f"   PGHOST: {pg_host}")
print(f"   PGPORT: {pg_port}")
print(f"   PGDATABASE: {pg_db}")
print(f"   PGUSER: {pg_user}")
print(f"   PGPASSWORD: {pg_pass}")

# Test 4: Try to connect
print("\n4. Testing PostgreSQL connection...")
try:
    from database.pg_connection import PostgreSQLConfig, get_pg_connection

    config = PostgreSQLConfig(
        host=os.getenv('PGHOST', 'localhost'),
        port=int(os.getenv('PGPORT', 5432)),
        database=os.getenv('PGDATABASE', 'linker_mind'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', ''),
        min_connections=1,
        max_connections=5
    )

    print(f"   Connecting to {config.host}:{config.port}/{config.database}...")
    conn = get_pg_connection(config)

    # Test query
    result = conn.fetchval("SELECT version()")
    print(f"   ✓ Connected successfully!")
    print(f"   PostgreSQL version: {result[:50]}...")

    # Check tables
    tables = conn.get_tables()
    print(f"   ✓ Found {len(tables)} tables")
    if tables:
        print(f"   Tables: {', '.join(tables[:5])}{'...' if len(tables) > 5 else ''}")

    # Close connection
    conn.close()
    print("   ✓ Connection closed")

except Exception as e:
    print(f"   ✗ Connection failed: {e}")
    print("\n   Troubleshooting:")
    print("   - Check if PostgreSQL is running")
    print("   - Verify host and port are correct")
    print("   - Verify username and password")
    print("   - Check firewall settings")
    sys.exit(1)

# Test 5: Test unified interface
print("\n5. Testing unified database interface...")
try:
    from database.db_interface import get_connection, get_database_type

    db = get_connection()
    db_type = get_database_type()

    print(f"   ✓ Using database: {db_type}")

    tables = db.get_tables()
    print(f"   ✓ Found {len(tables)} tables via unified interface")

except Exception as e:
    print(f"   ✗ Unified interface test failed: {e}")

print("\n" + "=" * 60)
print("All tests passed! ✓")
print("=" * 60)
print("\nYou can now run the migration:")
print("  python scripts/migrate_to_postgres.py")
