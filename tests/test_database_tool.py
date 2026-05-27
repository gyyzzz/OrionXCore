import asyncio
from types import SimpleNamespace

from orionxcore.llm.openai_compat import LLMResponse
from orionxcore.config import Settings
from orionxcore.tools.database import DatabaseTool


class FakeConnection:
    def __init__(self, result):
        self._result = result
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def execute(self, statement, params=None):
        self.calls.append({"statement": statement, "params": params})
        self.statement = statement
        self.params = params
        return self._result


class FakeEngine:
    def __init__(self, result):
        self._result = result
        self.connection = FakeConnection(self._result)

    def connect(self):
        return self.connection


class FakeResult:
    returns_rows = True

    def __init__(self):
        self._rows = [
            SimpleNamespace(_mapping={"id": 1, "name": "alpha"}),
            SimpleNamespace(_mapping={"id": 2, "name": "beta"}),
        ]

    def fetchmany(self, limit):
        return self._rows[:limit]

    def keys(self):
        return ["id", "name"]


def test_database_tool_rejects_non_clickhouse_url() -> None:
    tool = DatabaseTool(Settings(database_url="postgresql://localhost/db"))
    result = asyncio.run(tool.execute({"statement": "select 1"}))

    assert result["ok"] is False
    assert result["dialect"] == "postgresql"
    assert "Only ClickHouse connections" in result["error"]


def test_database_tool_blocks_mutation_statements() -> None:
    tool = DatabaseTool(
        Settings(
            database_url="clickhousedb://default:@localhost:8123/default",
            database_allow_mutation=False,
        )
    )
    result = asyncio.run(tool.execute({"statement": "DROP TABLE events"}))

    assert result["ok"] is False
    assert "read-only" in result["error"] or "blocked" in result["error"]


def test_database_tool_blocks_multiple_statements() -> None:
    tool = DatabaseTool(Settings(database_url="clickhousedb://default:@localhost:8123/default"))
    result = asyncio.run(tool.execute({"statement": "SELECT 1; SELECT 2"}))

    assert result["ok"] is False
    assert "Multiple SQL statements" in result["error"]


def test_database_tool_executes_clickhouse_query(monkeypatch) -> None:
    tool = DatabaseTool(
        Settings(
            database_url="clickhousedb://default:@localhost:8123/default",
            database_max_rows=1,
        )
    )

    fake_engine = None
    def fake_create_engine(url):
        assert url == "clickhousedb://default:@localhost:8123/default"
        nonlocal fake_engine
        fake_engine = FakeEngine(FakeResult())
        return fake_engine

    monkeypatch.setattr("orionxcore.tools.database.create_engine", fake_create_engine)
    result = asyncio.run(tool.execute({"statement": "SELECT id, name FROM items", "limit": 5}))

    assert result["ok"] is True
    assert result["dialect"] == "clickhouse"
    assert result["row_count"] == 1
    assert result["columns"] == ["id", "name"]
    assert result["rows"] == [{"id": 1, "name": "alpha"}]
    assert "SET max_execution_time = 30" in str(fake_engine.connection.calls[0]["statement"])


def test_database_tool_lists_tables(monkeypatch) -> None:
    tool = DatabaseTool(
        Settings(
            database_url="clickhousedb://default:@localhost:8123/default",
            database_max_rows=10,
            database_allowed_databases="",
        )
    )

    def fake_create_engine(url):
        return FakeEngine(FakeResult())

    monkeypatch.setattr("orionxcore.tools.database.create_engine", fake_create_engine)
    result = asyncio.run(tool.execute({"operation": "list_tables", "database": "default"}))

    assert result["ok"] is True
    assert result["dialect"] == "clickhouse"
    assert result["columns"] == ["id", "name"]


def test_database_tool_describe_table_requires_table() -> None:
    tool = DatabaseTool(Settings(database_url="clickhousedb://default:@localhost:8123/default"))
    result = asyncio.run(tool.execute({"operation": "describe_table"}))

    assert result["ok"] is False
    assert "Missing table name" in result["error"]


def test_database_tool_rejects_disallowed_database() -> None:
    tool = DatabaseTool(
        Settings(
            database_url="clickhousedb://default:@localhost:8123/default",
            database_allowed_databases="default,analytics",
        )
    )
    result = asyncio.run(tool.execute({"operation": "list_tables", "database": "internal"}))

    assert result["ok"] is False
    assert result["allowed_databases"] == ["default", "analytics"]
    assert "not allowed" in result["error"]


def test_database_tool_text_to_sql_executes_generated_sql(monkeypatch) -> None:
    tool = DatabaseTool(
        Settings(
            database_url="clickhousedb://default:@localhost:8123/default",
            database_max_rows=5,
            model="test-model",
        )
    )

    responses = [
        {
            "ok": True,
            "dialect": "clickhouse",
            "row_count": 1,
            "columns": ["users"],
            "rows": [{"users": 42}],
        },
    ]
    executed_statements = []

    def fake_execute_sql(arguments):
        executed_statements.append(arguments["statement"])
        return responses.pop(0)

    async def fake_complete(messages, tools, **kwargs):
        return LLMResponse(content="SELECT count() AS users FROM events", tool_calls=[], raw_message={})

    monkeypatch.setattr(tool, "_execute_sql", fake_execute_sql)
    monkeypatch.setattr(tool, "_build_schema_context", lambda arguments: "default.events: user_id UInt64")
    monkeypatch.setattr(tool, "_llm_client", SimpleNamespace(complete=fake_complete))

    result = asyncio.run(
        tool.execute(
            {
                "operation": "text_to_sql",
                "question": "How many users are in events?",
                "database": "default",
                "tables": ["events"],
            }
        )
    )

    assert result["ok"] is True
    assert result["generated_sql"] == "SELECT count() AS users FROM events"
    assert result["attempts"] == 1
    assert result["trace"]["question"] == "How many users are in events?"
    assert result["trace"]["schema_context"] == "default.events: user_id UInt64"
    assert result["trace"]["attempt_count"] == 1
    assert result["trace"]["final_sql"] == "SELECT count() AS users FROM events"
    assert result["trace"]["attempts"][0]["sql"] == "SELECT count() AS users FROM events"
    assert executed_statements == ["SELECT count() AS users FROM events"]


def test_database_tool_text_to_sql_retries_after_execution_error(monkeypatch) -> None:
    tool = DatabaseTool(
        Settings(
            database_url="clickhousedb://default:@localhost:8123/default",
            database_max_rows=5,
            model="test-model",
        )
    )

    responses = [
        {"ok": False, "error": "Unknown identifier users_id"},
        {
            "ok": True,
            "dialect": "clickhouse",
            "row_count": 1,
            "columns": ["users"],
            "rows": [{"users": 42}],
        },
    ]
    generated_sql = [
        "SELECT count(users_id) AS users FROM events",
        "SELECT count(user_id) AS users FROM events",
    ]

    def fake_execute_sql(arguments):
        return responses.pop(0)

    async def fake_complete(messages, tools, **kwargs):
        return LLMResponse(content=generated_sql.pop(0), tool_calls=[], raw_message={})

    monkeypatch.setattr(tool, "_execute_sql", fake_execute_sql)
    monkeypatch.setattr(tool, "_build_schema_context", lambda arguments: "default.events: user_id UInt64")
    monkeypatch.setattr(tool, "_llm_client", SimpleNamespace(complete=fake_complete))

    result = asyncio.run(
        tool.execute(
            {
                "operation": "text_to_sql",
                "question": "How many users are in events?",
                "database": "default",
                "tables": ["events"],
            }
        )
    )

    assert result["ok"] is True
    assert result["generated_sql"] == "SELECT count(user_id) AS users FROM events"
    assert result["attempts"] == 2
    assert result["previous_sql"] == "SELECT count(users_id) AS users FROM events"
    assert result["previous_error"] == "Unknown identifier users_id"
    assert result["trace"]["attempt_count"] == 2
    assert result["trace"]["final_sql"] == "SELECT count(user_id) AS users FROM events"
    assert result["trace"]["attempts"][0]["sql"] == "SELECT count(users_id) AS users FROM events"
    assert result["trace"]["attempts"][0]["error"] == "Unknown identifier users_id"
    assert result["trace"]["attempts"][1]["sql"] == "SELECT count(user_id) AS users FROM events"
    assert result["trace"]["attempts"][1]["retry_reason"] == "Unknown identifier users_id"


def test_database_tool_schema_context_uses_whitelist(monkeypatch) -> None:
    tool = DatabaseTool(
        Settings(
            database_url="clickhousedb://default:@localhost:8123/default",
            database_allowed_databases="default,analytics",
        )
    )
    captured = {}

    def fake_execute_introspection(statement, params, arguments):
        captured["statement"] = statement
        captured["params"] = params
        return {
            "ok": True,
            "dialect": "clickhouse",
            "row_count": 1,
            "columns": ["database", "table", "name", "type"],
            "rows": [{"database": "default", "table": "events", "name": "user_id", "type": "UInt64"}],
        }

    monkeypatch.setattr(tool, "_execute_introspection", fake_execute_introspection)
    context = tool._build_schema_context({"tables": ["events"]})

    assert "default.events: user_id UInt64" == context
    assert "allowed_db_0" in captured["params"]
    assert "allowed_db_1" in captured["params"]
