from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from sqlalchemy import create_engine, text

from orionxcore.config import Settings
from orionxcore.tools.base import Tool

try:
    from pymongo import MongoClient
except ImportError:  # pragma: no cover - optional dependency
    MongoClient = None


class DatabaseTool(Tool):
    name = "database_query"
    description = "Run a database query against the configured SQL database or MongoDB connection."
    input_schema = {
        "type": "object",
        "properties": {
            "statement": {
                "type": "string",
                "description": "SQL statement for SQLite, MySQL, or PostgreSQL.",
            },
            "collection": {
                "type": "string",
                "description": "MongoDB collection name when using a MongoDB connection.",
            },
            "operation": {
                "type": "string",
                "enum": ["find", "count_documents"],
                "description": "MongoDB operation.",
            },
            "filter": {
                "type": "object",
                "description": "MongoDB query filter.",
            },
            "projection": {
                "type": "object",
                "description": "MongoDB projection.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of rows or documents to return.",
                "minimum": 1,
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        database_url = self._settings.database_url
        if not database_url:
            return {"ok": False, "error": "Database is not configured."}

        if database_url.startswith("mongodb://") or database_url.startswith("mongodb+srv://"):
            return self._execute_mongodb(arguments)

        return self._execute_sql(arguments)

    def _execute_sql(self, arguments: dict[str, Any]) -> dict[str, Any]:
        statement = (arguments.get("statement") or "").strip()
        if not statement:
            return {"ok": False, "error": "Missing SQL statement."}
        if not self._settings.database_allow_mutation and self._looks_mutating(statement):
            return {
                "ok": False,
                "error": "Mutation statements are blocked by configuration.",
                "requires_confirmation": True,
            }

        limit = min(int(arguments.get("limit") or self._settings.database_max_rows), self._settings.database_max_rows)
        engine = create_engine(self._settings.database_url)
        with engine.connect() as connection:
            result = connection.execute(text(statement))
            rows = result.fetchmany(limit) if result.returns_rows else []
            columns = list(result.keys()) if result.returns_rows else []
        return {
            "ok": True,
            "dialect": self._safe_dialect_name(self._settings.database_url),
            "row_count": len(rows),
            "columns": columns,
            "rows": [dict(row._mapping) for row in rows],
        }

    def _execute_mongodb(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if MongoClient is None:
            return {
                "ok": False,
                "error": "pymongo is not installed. Install the mongodb extra to enable MongoDB support.",
            }

        collection_name = arguments.get("collection")
        operation = arguments.get("operation", "find")
        limit = min(int(arguments.get("limit") or self._settings.database_max_rows), self._settings.database_max_rows)
        if not collection_name:
            return {"ok": False, "error": "Missing MongoDB collection name."}

        parsed = urlparse(self._settings.database_url)
        database_name = parsed.path.lstrip("/")
        if not database_name:
            return {"ok": False, "error": "MongoDB URI must include a database name."}

        client = MongoClient(self._settings.database_url)
        collection = client[database_name][collection_name]
        query_filter = arguments.get("filter") or {}
        projection = arguments.get("projection")

        if operation == "count_documents":
            return {
                "ok": True,
                "dialect": "mongodb",
                "count": collection.count_documents(query_filter),
            }

        cursor = collection.find(query_filter, projection).limit(limit)
        documents = [{k: str(v) if k == "_id" else v for k, v in doc.items()} for doc in cursor]
        return {
            "ok": True,
            "dialect": "mongodb",
            "row_count": len(documents),
            "rows": documents,
        }

    def _looks_mutating(self, statement: str) -> bool:
        normalized = statement.strip().lower()
        return normalized.startswith(("insert", "update", "delete", "alter", "drop", "truncate", "create"))

    def _safe_dialect_name(self, database_url: str) -> str:
        return database_url.split(":", 1)[0]

