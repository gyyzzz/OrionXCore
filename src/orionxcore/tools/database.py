from typing import Any

from sqlalchemy import create_engine, text

from orionxcore.config import Settings
from orionxcore.llm.openai_compat import OpenAICompatibleClient
from orionxcore.tools.base import Tool


class DatabaseTool(Tool):
    name = "database_query"
    description = "Run read-only queries and schema introspection against the configured ClickHouse connection."
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["query", "list_tables", "describe_table", "text_to_sql"],
                "description": "Database operation to perform.",
            },
            "question": {
                "type": "string",
                "description": "Natural language database question for text_to_sql.",
            },
            "statement": {
                "type": "string",
                "description": "Read-only SQL statement for ClickHouse.",
            },
            "database": {
                "type": "string",
                "description": "Optional ClickHouse database name for schema operations.",
            },
            "table": {
                "type": "string",
                "description": "Table name for describe_table.",
            },
            "tables": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of table names to narrow schema context for text_to_sql.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of rows to return.",
                "minimum": 1,
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._llm_client = OpenAICompatibleClient(settings)

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        database_url = self._settings.database_url
        if not database_url:
            return {"ok": False, "error": "Database is not configured."}
        if not self._is_clickhouse_url(database_url):
            return {
                "ok": False,
                "error": "Only ClickHouse connections are currently supported.",
                "dialect": self._safe_dialect_name(database_url),
            }
        operation = arguments.get("operation") or "query"
        if operation == "list_tables":
            return self._list_tables(arguments)
        if operation == "describe_table":
            return self._describe_table(arguments)
        if operation == "text_to_sql":
            return await self._text_to_sql(arguments)
        return self._execute_sql(arguments)

    def _execute_sql(self, arguments: dict[str, Any]) -> dict[str, Any]:
        statement = (arguments.get("statement") or "").strip()
        if not statement:
            return {"ok": False, "error": "Missing SQL statement."}
        validation_error = self._validate_read_only_statement(statement)
        if validation_error is not None:
            return validation_error

        limit = min(
            int(arguments.get("limit") or self._settings.database_max_rows),
            self._settings.database_max_rows,
        )
        engine = create_engine(self._settings.database_url)
        with engine.connect() as connection:
            self._apply_query_timeout(connection)
            result = connection.execute(text(statement))
            rows = result.fetchmany(limit) if result.returns_rows else []
            columns = list(result.keys()) if result.returns_rows else []
        return {
            "ok": True,
            "dialect": "clickhouse",
            "row_count": len(rows),
            "columns": columns,
            "rows": [dict(row._mapping) for row in rows],
        }

    async def _text_to_sql(self, arguments: dict[str, Any]) -> dict[str, Any]:
        question = (arguments.get("question") or "").strip()
        if not question:
            return {"ok": False, "error": "Missing natural language question for text_to_sql."}

        schema_context = self._build_schema_context(arguments)
        trace: dict[str, Any] = {
            "question": question,
            "operation": "text_to_sql",
            "database": (arguments.get("database") or "").strip() or None,
            "tables": arguments.get("tables") or [],
            "schema_context": schema_context,
            "attempts": [],
        }
        sql = await self._generate_sql(question=question, schema_context=schema_context)
        trace["attempts"].append({"attempt": 1, "sql": sql})
        first_result = self._execute_sql(
            {
                "statement": sql,
                "limit": arguments.get("limit"),
            }
        )
        if first_result.get("ok"):
            trace["attempt_count"] = 1
            trace["final_sql"] = sql
            first_result["generated_sql"] = sql
            first_result["question"] = question
            first_result["attempts"] = 1
            first_result["trace"] = trace
            return first_result

        trace["attempts"][0]["error"] = first_result.get("error")
        retry_sql = await self._generate_sql(
            question=question,
            schema_context=schema_context,
            previous_sql=sql,
            previous_error=first_result.get("error", "Unknown SQL execution error."),
        )
        trace["attempts"].append(
            {
                "attempt": 2,
                "sql": retry_sql,
                "retry_reason": first_result.get("error"),
            }
        )
        second_result = self._execute_sql(
            {
                "statement": retry_sql,
                "limit": arguments.get("limit"),
            }
        )
        if not second_result.get("ok"):
            trace["attempts"][1]["error"] = second_result.get("error")
        trace["attempt_count"] = 2
        trace["final_sql"] = retry_sql
        second_result["generated_sql"] = retry_sql
        second_result["question"] = question
        second_result["attempts"] = 2
        second_result["previous_sql"] = sql
        second_result["previous_error"] = first_result.get("error")
        second_result["trace"] = trace
        return second_result

    def _list_tables(self, arguments: dict[str, Any]) -> dict[str, Any]:
        database = (arguments.get("database") or "").strip()
        allowed_databases = self._allowed_databases()
        if database and not self._is_database_allowed(database):
            return self._database_not_allowed(database)
        statement = """
        SELECT database, name, engine
        FROM system.tables
        {where_clause}
        ORDER BY database, name
        """
        params: dict[str, Any] = {}
        where_clause = ""
        if database:
            where_clause = "WHERE database = :database"
            params["database"] = database
        elif allowed_databases:
            placeholders = ", ".join(f":allowed_db_{index}" for index, _ in enumerate(allowed_databases))
            where_clause = f"WHERE database IN ({placeholders})"
            for index, name in enumerate(allowed_databases):
                params[f"allowed_db_{index}"] = name
        return self._execute_introspection(statement.format(where_clause=where_clause), params, arguments)

    def _describe_table(self, arguments: dict[str, Any]) -> dict[str, Any]:
        table = (arguments.get("table") or "").strip()
        if not table:
            return {"ok": False, "error": "Missing table name for describe_table."}

        database = (arguments.get("database") or "").strip()
        allowed_databases = self._allowed_databases()
        if database and not self._is_database_allowed(database):
            return self._database_not_allowed(database)
        statement = """
        SELECT database, table, name, type, is_in_primary_key, is_in_sorting_key
        FROM system.columns
        WHERE table = :table
        {database_clause}
        ORDER BY position
        """
        params: dict[str, Any] = {"table": table}
        database_clause = ""
        if database:
            database_clause = "AND database = :database"
            params["database"] = database
        elif allowed_databases:
            placeholders = ", ".join(f":allowed_db_{index}" for index, _ in enumerate(allowed_databases))
            database_clause = f"AND database IN ({placeholders})"
            for index, name in enumerate(allowed_databases):
                params[f"allowed_db_{index}"] = name
        return self._execute_introspection(statement.format(database_clause=database_clause), params, arguments)

    def _execute_introspection(
        self,
        statement: str,
        params: dict[str, Any],
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        limit = min(
            int(arguments.get("limit") or self._settings.database_max_rows),
            self._settings.database_max_rows,
        )
        engine = create_engine(self._settings.database_url)
        with engine.connect() as connection:
            self._apply_query_timeout(connection)
            result = connection.execute(text(statement), params)
            rows = result.fetchmany(limit) if result.returns_rows else []
            columns = list(result.keys()) if result.returns_rows else []
        return {
            "ok": True,
            "dialect": "clickhouse",
            "row_count": len(rows),
            "columns": columns,
            "rows": [dict(row._mapping) for row in rows],
        }

    def _build_schema_context(self, arguments: dict[str, Any]) -> str:
        database = (arguments.get("database") or "").strip()
        if database and not self._is_database_allowed(database):
            return f"Database '{database}' is not allowed by configuration."

        allowed_databases = self._allowed_databases()
        tables = arguments.get("tables") or []
        statement = """
        SELECT database, table, name, type
        FROM system.columns
        WHERE 1 = 1
        {database_clause}
        {table_clause}
        ORDER BY database, table, position
        """
        params: dict[str, Any] = {}
        database_clause = ""
        table_clause = ""
        if database:
            database_clause = "AND database = :database"
            params["database"] = database
        elif allowed_databases:
            placeholders = ", ".join(f":allowed_db_{index}" for index, _ in enumerate(allowed_databases))
            database_clause = f"AND database IN ({placeholders})"
            for index, name in enumerate(allowed_databases):
                params[f"allowed_db_{index}"] = name
        if tables:
            quoted = ", ".join(f":table_{index}" for index, _table in enumerate(tables))
            table_clause = f"AND table IN ({quoted})"
            for index, table in enumerate(tables):
                params[f"table_{index}"] = table
        result = self._execute_introspection(statement.format(database_clause=database_clause, table_clause=table_clause), params, arguments)
        if not result.get("ok"):
            return "Schema introspection failed."
        rows = result.get("rows", [])
        if not rows:
            return "No schema information found."
        lines = [
            f"{row['database']}.{row['table']}: {row['name']} {row['type']}"
            for row in rows
        ]
        return "\n".join(lines)

    async def _generate_sql(
        self,
        question: str,
        schema_context: str,
        previous_sql: str | None = None,
        previous_error: str | None = None,
    ) -> str:
        system_prompt = (
            "You write ClickHouse SQL only. Return a single read-only SQL query with no explanation. "
            "Never generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE."
        )
        user_prompt = f"Schema:\n{schema_context}\n\nQuestion:\n{question}\n"
        if previous_sql and previous_error:
            user_prompt += (
                f"\nPrevious SQL:\n{previous_sql}\n\nExecution error:\n{previous_error}\n"
                "Return a corrected read-only ClickHouse SQL query."
            )
        response = await self._llm_client.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=[],
            model=self._settings.model,
            temperature=0,
        )
        return self._normalize_sql(response.content)

    def _normalize_sql(self, content: str) -> str:
        normalized = content.strip()
        if normalized.startswith("```"):
            lines = normalized.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            normalized = "\n".join(lines).strip()
            if normalized.lower().startswith("sql"):
                normalized = normalized[3:].strip()
        return normalized.rstrip(";")

    def _looks_mutating(self, statement: str) -> bool:
        normalized = statement.strip().lower()
        return normalized.startswith(("insert", "update", "delete", "alter", "drop", "truncate", "create"))

    def _validate_read_only_statement(self, statement: str) -> dict[str, Any] | None:
        normalized = statement.strip()
        if self._contains_multiple_statements(normalized):
            return {"ok": False, "error": "Multiple SQL statements are not allowed."}
        lowered = normalized.lower().rstrip(";").lstrip()
        allowed_prefixes = ("select", "show", "describe", "desc", "explain", "with")
        if not lowered.startswith(allowed_prefixes):
            return {"ok": False, "error": "Only read-only ClickHouse statements are allowed."}
        if not self._settings.database_allow_mutation and self._looks_mutating(lowered):
            return {
                "ok": False,
                "error": "Mutation statements are blocked by configuration.",
                "requires_confirmation": True,
            }
        return None

    def _contains_multiple_statements(self, statement: str) -> bool:
        if ";" not in statement:
            return False
        return ";" in statement.rstrip(";")

    def _apply_query_timeout(self, connection: Any) -> None:
        timeout_seconds = max(int(self._settings.database_query_timeout_seconds), 1)
        connection.execute(text(f"SET max_execution_time = {timeout_seconds}"))

    def _allowed_databases(self) -> list[str]:
        raw = self._settings.database_allowed_databases.strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _is_database_allowed(self, database: str) -> bool:
        allowed = self._allowed_databases()
        return not allowed or database in allowed

    def _database_not_allowed(self, database: str) -> dict[str, Any]:
        return {
            "ok": False,
            "error": f"Database '{database}' is not allowed by configuration.",
            "allowed_databases": self._allowed_databases(),
        }

    def _is_clickhouse_url(self, database_url: str) -> bool:
        return database_url.startswith(("clickhouse://", "clickhousedb://"))

    def _safe_dialect_name(self, database_url: str) -> str:
        return database_url.split(":", 1)[0]
