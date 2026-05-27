from orionxcore.config import Settings
from orionxcore.llm.openai_compat import LLMResponse, ToolCall
from orionxcore.schemas import AgentRequest, ChatMessage
from orionxcore.services.agent import AgentService
from orionxcore.tools.base import Tool
from orionxcore.tools.registry import ToolRegistry


class FakeDatabaseTool(Tool):
    name = "database_query"
    description = "Fake database tool."
    input_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def execute(self, arguments):
        return {
            "ok": True,
            "row_count": 1,
            "columns": ["users"],
            "rows": [{"users": 42}],
            "generated_sql": "SELECT count() AS users FROM events",
            "trace": {
                "question": "How many users are in events?",
                "database": "default",
                "tables": ["events"],
                "schema_context": "default.events: user_id UInt64",
                "attempt_count": 1,
                "final_sql": "SELECT count() AS users FROM events",
                "attempts": [
                    {
                        "attempt": 1,
                        "sql": "SELECT count() AS users FROM events",
                    }
                ],
            },
        }


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0
        self.second_messages = None

    async def complete(self, messages, tools, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content="",
                tool_calls=[ToolCall(id="call_1", name="database_query", arguments={"operation": "text_to_sql"})],
                raw_message={"reasoning_content": "I should inspect the database first."},
            )
        self.second_messages = messages
        return LLMResponse(
            content="There are 42 users.",
            tool_calls=[],
            raw_message={},
        )


def test_agent_response_emits_database_trace_events() -> None:
    service = AgentService(
        settings=Settings(api_key="test"),
        registry=ToolRegistry([FakeDatabaseTool()]),
    )
    service._client = FakeClient()

    response = __import__("asyncio").run(
        service.run(
            AgentRequest(
                messages=[ChatMessage(role="user", content="How many users are in events?")]
            )
        )
    )

    event_types = [event.type for event in response.events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "database_trace" in event_types
    assert "database_schema_context" in event_types
    assert "database_sql_attempt" in event_types
    assert "database_result_summary" in event_types

    trace_event = next(event for event in response.events if event.type == "database_trace")
    assert trace_event.payload["final_sql"] == "SELECT count() AS users FROM events"
    summary_event = next(event for event in response.events if event.type == "database_result_summary")
    assert summary_event.payload["row_count"] == 1
    assert service._client.second_messages[2]["reasoning_content"] == "I should inspect the database first."
