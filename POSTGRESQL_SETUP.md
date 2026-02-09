# Linker Mind - PostgreSQL Migration Guide

This guide helps you migrate Linker Mind from SQLite to PostgreSQL.

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install only PostgreSQL support:

```bash
pip install psycopg2-binary python-dotenv
```

### 2. Configure Environment

The `.env` file should already contain your PostgreSQL credentials:

```env
DB_TYPE=postgresql
DATABASE_URL=jdbc:postgresql://117.72.207.52:5432/linker-mind
PGHOST=117.72.207.52
PGPORT=5432
PGDATABASE=linker-mind
PGUSER=postgres
PGPASSWORD=LinkerAI@2026
```

### 3. Run Migration

```bash
python scripts/migrate_to_postgres.py
```

That's it! The migration script will:
- Connect to your PostgreSQL database
- Create the schema
- Migrate all data from SQLite to PostgreSQL
- Verify the migration

---

## Migration Options

### Dry Run (See what would be migrated)

```bash
python scripts/migrate_to_postgres.py --dry-run
```

### Skip Existing Records (Idempotent)

```bash
python scripts/migrate_to_postgres.py --skip-existing
```

### Custom Batch Size

```bash
python scripts/migrate_to_postgres.py --batch-size 50
```

### Initialize Schema Only

```bash
python scripts/migrate_to_postgres.py --init-only
```

---

## Switching Between Databases

You can switch between SQLite and PostgreSQL by changing the `DB_TYPE` in `.env`:

**Use PostgreSQL:**
```env
DB_TYPE=postgresql
```

**Use SQLite:**
```env
DB_TYPE=sqlite
SQLITE_DB_PATH=linker_mind.db
```

---

## What Gets Migrated

The migration transfers all data from SQLite to PostgreSQL:

| Table | Description |
|-------|-------------|
| `contents` | All collected content |
| `contents_fts` | Full-text search index |
| `inbox` | Quick capture items |
| `notes` | Progressive summaries |
| `nodes` | PARA organization |
| `links` | Bidirectional links |
| `creation_projects` | Creative projects |
| `learning_sessions` | Learning tracking |
| `review_schedules` | Spaced repetition |
| `skills` | Skill trees |
| `tags` | Tag management |
| `citations` | Citation tracking |

---

## Verification

After migration, the script automatically:

1. **Compares record counts** between SQLite and PostgreSQL
2. **Lists all tables** in both databases
3. **Reports any mismatches**

Example output:

```
Post-migration verification:
Record count comparison:
  ✓ contents: SQLite=150, PG=150
  ✓ inbox: SQLite=25, PG=25
  ✓ notes: SQLite=89, PG=89
  ...

✓ All records migrated successfully!
```

---

## Manual SQL Verification

Connect to your PostgreSQL database and run:

```sql
-- List all tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- Count records in each table
SELECT
    'contents' as table_name,
    COUNT(*) as count
FROM contents
UNION ALL
SELECT
    'inbox',
    COUNT(*)
FROM inbox
UNION ALL
SELECT
    'notes',
    COUNT(*)
FROM notes;

-- Check recent content
SELECT id, title, source_type, created_at
FROM contents
ORDER BY created_at DESC
LIMIT 10;
```

---

## Troubleshooting

### Connection Issues

**Error: `could not connect to server`**

- Check that PostgreSQL is running
- Verify host and port are correct
- Check firewall settings

**Error: `authentication failed`**

- Verify username and password
- Check PostgreSQL pg_hba.conf settings
- Ensure user has necessary permissions

### Schema Issues

**Error: `relation already exists`**

- The tables already exist. Use `--skip-existing` to migrate only new data
- Or drop and recreate the database

### Performance Issues

**Migration is slow**

- Reduce batch size: `--batch-size 50`
- Check network latency to PostgreSQL server
- Consider running migration closer to PostgreSQL server

---

## Architecture

### Database Layer

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                     │
│  (services, content_processor, web_interface, etc.)    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Unified Database Interface                 │
│                   (db_interface.py)                     │
│  - Auto-detects database type from environment          │
│  - Provides consistent API for both databases          │
└─────────────────────────────────────────────────────────┘
                    │                    │
        ┌───────────┴───────────┐  ┌────┴──────┐
        ▼                       ▼           ▼
┌──────────────┐      ┌─────────────────┐  ┌──────────────┐
│   SQLite     │      │   PostgreSQL    │  │  Future DB   │
│ (connection.py)│    │ (pg_connection.py)│  │              │
└──────────────┘      └─────────────────┘  └──────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `database/db_interface.py` | Unified database interface |
| `database/connection.py` | SQLite connection manager |
| `database/pg_connection.py` | PostgreSQL connection manager |
| `database/schema_pg.sql` | PostgreSQL schema |
| `database/migration_pg.py` | Migration logic |
| `scripts/migrate_to_postgres.py` | Migration runner script |

---

## Advantages of PostgreSQL

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| Concurrent writes | Limited | Excellent |
| Full-text search | FTS5 | pg_trgm + GIN |
| JSON support | TEXT | JSONB (binary) |
| Foreign keys | Yes | Yes + CASCADE |
| Indexes | B-tree | B-tree, GIN, GiST |
| Replication | No | Yes |
| Scale | Single file | Distributed |

---

## Next Steps

After migration:

1. **Test the application**
   ```bash
   python main.py --help
   ```

2. **Run web interface** (if using)
   ```bash
   python web_interface.py
   ```

3. **Backup PostgreSQL**
   ```bash
   pg_dump -h 117.72.207.52 -U postgres linker-mind > backup.sql
   ```

4. **Monitor performance**
   - Check query times
   - Monitor connection pool usage
   - Review slow query log

---

## Rollback

To switch back to SQLite:

1. Update `.env`:
   ```env
   DB_TYPE=sqlite
   ```

2. Restart application

The SQLite database (`linker_mind.db`) is untouched by migration.

---

## Support

For issues or questions:
- Check logs: `logs/linker_mind.log`
- Enable debug logging: Set `LOG_LEVEL=DEBUG` in `.env`
- Review migration output for specific errors

---

*Last updated: February 2026*
*Version: 2.0.0*
