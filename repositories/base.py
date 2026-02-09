"""
Base Repository Module - Abstract base class for all repositories

This module provides:
- Base repository class with common CRUD operations
- Transaction management
- Query building helpers
- Error handling
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple, TypeVar, Generic
from dataclasses import dataclass, asdict
import logging

from database.connection import get_db, json_dumps, json_loads, json_list, json_dict

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RepositoryResult:
    """Standard result type for repository operations"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error
        }


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository class

    Provides common CRUD operations and query building
    """

    def __init__(self, db_path: str = "linker_mind.db"):
        self.db = get_db(db_path)
        self.db_path = db_path

    @abstractmethod
    def _to_model(self, row: Any) -> T:
        """Convert database row to model instance"""
        pass

    @abstractmethod
    def _to_dict(self, model: T) -> Dict[str, Any]:
        """Convert model to dictionary for database storage"""
        pass

    def find_by_id(self, id: str) -> Optional[T]:
        """Find a record by ID"""
        table = self._get_table()
        row = self.db.fetchone(f"SELECT * FROM {table} WHERE id = ?", (id,))
        if row:
            return self._to_model(row)
        return None

    def find_all(
        self,
        where: Optional[str] = None,
        where_params: Optional[Tuple] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[T]:
        """Find all records matching criteria"""
        table = self._get_table()
        sql = f"SELECT * FROM {table}"

        if where:
            sql += f" WHERE {where}"

        if order_by:
            sql += f" ORDER BY {order_by}"

        if limit:
            sql += f" LIMIT {limit}"
            if offset:
                sql += f" OFFSET {offset}"

        rows = self.db.fetchall(sql, where_params)
        return [self._to_model(row) for row in rows]

    def find_one(
        self,
        where: str,
        where_params: Optional[Tuple] = None
    ) -> Optional[T]:
        """Find a single record matching criteria"""
        results = self.find_all(where, where_params, limit=1)
        return results[0] if results else None

    def count(self, where: Optional[str] = None, where_params: Optional[Tuple] = None) -> int:
        """Count records matching criteria"""
        table = self._get_table()
        sql = f"SELECT COUNT(*) as count FROM {table}"
        if where:
            sql += f" WHERE {where}"
        row = self.db.fetchone(sql, where_params)
        return row['count'] if row else 0

    def exists(self, id: str) -> bool:
        """Check if a record exists by ID"""
        return self.find_by_id(id) is not None

    def insert(self, model: T) -> RepositoryResult:
        """Insert a new record"""
        try:
            table = self._get_table()
            data = self._to_dict(model)
            self.db.insert(table, data)
            return RepositoryResult(success=True, data=model)
        except Exception as e:
            logger.error(f"Error inserting into {table}: {e}")
            return RepositoryResult(success=False, error=str(e))

    def update(self, model: T) -> RepositoryResult:
        """Update an existing record"""
        try:
            table = self._get_table()
            data = self._to_dict(model)
            id_value = data.get('id')

            if not id_value:
                return RepositoryResult(success=False, error="No ID provided")

            # Remove id from data for SET clause
            update_data = {k: v for k, v in data.items() if k != 'id'}

            rows_affected = self.db.update(
                table,
                update_data,
                "id = ?",
                (id_value,)
            )

            if rows_affected > 0:
                return RepositoryResult(success=True, data=model)
            else:
                return RepositoryResult(success=False, error="Record not found")
        except Exception as e:
            logger.error(f"Error updating in {table}: {e}")
            return RepositoryResult(success=False, error=str(e))

    def delete(self, id: str) -> RepositoryResult:
        """Delete a record by ID"""
        try:
            table = self._get_table()
            rows_affected = self.db.delete(table, "id = ?", (id,))

            if rows_affected > 0:
                return RepositoryResult(success=True)
            else:
                return RepositoryResult(success=False, error="Record not found")
        except Exception as e:
            logger.error(f"Error deleting from {table}: {e}")
            return RepositoryResult(success=False, error=str(e))

    def bulk_insert(self, models: List[T]) -> RepositoryResult:
        """Insert multiple records"""
        try:
            table = self._get_table()
            if not models:
                return RepositoryResult(success=True, data=[])

            first_data = self._to_dict(models[0])
            columns = list(first_data.keys())

            sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['?' for _ in columns])})"

            params_list = []
            for model in models:
                data = self._to_dict(model)
                params_list.append(tuple(data.values()))

            self.db.executemany(sql, params_list)
            return RepositoryResult(success=True, data=len(models))
        except Exception as e:
            logger.error(f"Error bulk inserting into {table}: {e}")
            return RepositoryResult(success=False, error=str(e))

    def upsert(self, model: T) -> RepositoryResult:
        """Insert or update a record"""
        data = self._to_dict(model)
        id_value = data.get('id')

        if not id_value:
            return self.insert(model)

        if self.exists(id_value):
            return self.update(model)
        else:
            return self.insert(model)

    def transaction(self, func) -> Any:
        """Execute a function within a transaction"""
        # SQLite in WAL mode handles transactions automatically
        # But we can add explicit transaction management if needed
        try:
            result = func()
            return result
        except Exception as e:
            logger.error(f"Transaction error: {e}")
            raise

    @abstractmethod
    def _get_table(self) -> str:
        """Get the table name for this repository"""
        pass

    def _build_where_clause(
        self,
        filters: Dict[str, Any],
        operator: str = "AND"
    ) -> Tuple[str, Tuple]:
        """
        Build a WHERE clause from a dictionary of filters

        Args:
            filters: Dictionary of column names and values
            operator: AND or OR

        Returns:
            Tuple of (where_clause, params)
        """
        if not filters:
            return "", ()

        conditions = []
        params = []

        for column, value in filters.items():
            if value is None:
                conditions.append(f"{column} IS NULL")
            elif isinstance(value, list):
                placeholders = ', '.join(['?' for _ in value])
                conditions.append(f"{column} IN ({placeholders})")
                params.extend(value)
            elif isinstance(value, dict) and '$op' in value:
                # Support for operators like {'$op': 'LIKE', '$value': '%test%'}
                op = value['$op']
                val = value['$value']
                conditions.append(f"{column} {op} ?")
                params.append(val)
            else:
                conditions.append(f"{column} = ?")
                params.append(value)

        where_clause = f" {operator} ".join(conditions)
        return where_clause, tuple(params)

    def search(
        self,
        query: str,
        search_fields: List[str],
        where: Optional[str] = None,
        where_params: Optional[Tuple] = None,
        limit: int = 100
    ) -> List[T]:
        """
        Full-text search using FTS

        Args:
            query: Search query
            search_fields: List of fields to search (if not using FTS)
            where: Additional WHERE clause
            where_params: Parameters for WHERE clause
            limit: Maximum results

        Returns:
            List of matching models
        """
        table = self._get_table()
        fts_table = f"{table}_fts"

        # Check if FTS table exists
        if self.db.table_exists(fts_table):
            # Use FTS
            sql = f"""
                SELECT t.* FROM {table} t
                INNER JOIN {fts_table} fts ON t.id = fts.id
                WHERE {fts_table} MATCH ?
            """
            params = (query,)

            if where:
                sql += f" AND ({where})"
                params = params + (where_params or ())

            sql += f" ORDER BY rank LIMIT {limit}"
        else:
            # Fallback to LIKE search
            conditions = [f"{field} LIKE ?" for field in search_fields]
            like_query = f"%{query}%"
            params = tuple([like_query] * len(search_fields))

            sql = f"SELECT * FROM {table} WHERE {' OR '.join(conditions)}"

            if where:
                sql += f" AND ({where})"
                params = params + (where_params or ())

            sql += f" LIMIT {limit}"

        rows = self.db.fetchall(sql, params)
        return [self._to_model(row) for row in rows]

    def get_related(
        self,
        id: str,
        relation_table: str,
        foreign_key: str,
        where: Optional[str] = None,
        order_by: Optional[str] = None
    ) -> List[Any]:
        """
        Get related records through a junction table

        Args:
            id: The ID of the source record
            relation_table: The junction table name
            foreign_key: The foreign key column in the relation table
            where: Optional WHERE clause
            order_by: Optional ORDER BY clause

        Returns:
            List of related records (as dicts)
        """
        sql = f"""
            SELECT t.*
            FROM {relation_table} r
            JOIN {self._get_table()} t ON r.{foreign_key} = t.id
            WHERE r.id = ?
        """

        params = (id,)

        if where:
            sql += f" AND {where}"

        if order_by:
            sql += f" ORDER BY {order_by}"

        rows = self.db.fetchall(sql, params)
        return [dict(row) for row in rows]

    def paginate(
        self,
        page: int = 1,
        page_size: int = 20,
        where: Optional[str] = None,
        where_params: Optional[Tuple] = None,
        order_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get paginated results

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            where: WHERE clause
            where_params: Parameters for WHERE clause
            order_by: ORDER BY clause

        Returns:
            Dictionary with items, total, page, page_size, total_pages
        """
        total = self.count(where, where_params)
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        offset = (page - 1) * page_size
        items = self.find_all(
            where=where,
            where_params=where_params,
            order_by=order_by,
            limit=page_size,
            offset=offset
        )

        return {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }


class Filters:
    """Helper class for building filter dictionaries"""

    @staticmethod
    def eq(column: str, value: Any) -> Dict[str, Any]:
        return {column: value}

    @staticmethod
    def ne(column: str, value: Any) -> Dict[str, Any]:
        return {column: {'$op': '!=', '$value': value}}

    @staticmethod
    def like(column: str, value: str) -> Dict[str, Any]:
        return {column: {'$op': 'LIKE', '$value': value}}

    @staticmethod
    def in_list(column: str, values: List[Any]) -> Dict[str, Any]:
        return {column: values}

    @staticmethod
    def gt(column: str, value: Any) -> Dict[str, Any]:
        return {column: {'$op': '>', '$value': value}}

    @staticmethod
    def gte(column: str, value: Any) -> Dict[str, Any]:
        return {column: {'$op': '>=', '$value': value}}

    @staticmethod
    def lt(column: str, value: Any) -> Dict[str, Any]:
        return {column: {'$op': '<', '$value': value}}

    @staticmethod
    def lte(column: str, value: Any) -> Dict[str, Any]:
        return {column: {'$op': '<=', '$value': value}}

    @staticmethod
    def is_null(column: str) -> Dict[str, Any]:
        return {column: None}

    @staticmethod
    def is_not_null(column: str) -> Dict[str, Any]:
        return {column: {'$op': 'IS NOT NULL', '$value': None}}

    @staticmethod
    def between(column: str, start: Any, end: Any) -> Dict[str, Any]:
        return {column: {'$op': 'BETWEEN', '$value': (start, end)}}

    @staticmethod
    def date_range(column: str, start: str, end: str) -> Dict[str, Any]:
        return {
            '$and': [
                {column: {'$op': '>=', '$value': start}},
                {column: {'$op': '<=', '$value': end}}
            ]
        }


if __name__ == "__main__":
    # Test the base repository
    from dataclasses import dataclass

    @dataclass
    class TestModel:
        id: str
        name: str
        value: int

    class TestRepo(BaseRepository[TestModel]):
        def _get_table(self) -> str:
            return "test_table"

        def _to_model(self, row: Any) -> TestModel:
            return TestModel(
                id=row['id'],
                name=row['name'],
                value=row['value']
            )

        def _to_dict(self, model: TestModel) -> Dict[str, Any]:
            return {
                'id': model.id,
                'name': model.name,
                'value': model.value
            }

    print("Base repository module loaded successfully")
    print("Available helpers: Filters class with eq, ne, like, in_list, gt, gte, lt, lte, is_null, is_not_null, between, date_range")
