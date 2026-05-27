from fastapi.testclient import TestClient

from orionxcore.api.routes import get_agent_service
from orionxcore.config import Settings
from orionxcore.llm.openai_compat import LLMResponse
from orionxcore.llm.openai_compat import ToolCall
from orionxcore.main import app
from orionxcore.schemas import AgentEvent, AgentResponse, ChatCompletionChunk
from orionxcore.schemas import ChatCompletionChoice, ChatCompletionMessage, ChatCompletionResponse
from orionxcore.schemas import ChatCompletionUsage, ChatMessage
from orionxcore.services.agent import AgentService
from orionxcore.tools.base import Tool
from orionxcore.tools.registry import ToolRegistry


class StubAgentService:
    async def run(self, request):  # pragma: no cover - compatibility stub
        return AgentResponse(
            message=ChatMessage(role="assistant", content="internal"),
            events=[AgentEvent(type="assistant", payload={"content": "internal"})],
            iterations=1,
        )

    async def run_chat_completion(self, request) -> ChatCompletionResponse:
        return ChatCompletionResponse(
            id="chatcmpl-test",
            object="chat.completion",
            created=1,
            model=request.model or "stub-model",
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionMessage(role="assistant", content="stubbed reply"),
                    finish_reason="stop",
                )
            ],
            usage=ChatCompletionUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5),
        )

    async def stream_chat_completion(self, request):
        yield ChatCompletionChunk(
            id="chatcmpl-test",
            object="chat.completion.chunk",
            created=1,
            model=request.model or "stub-model",
            choices=[{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        )
        yield ChatCompletionChunk(
            id="chatcmpl-test",
            object="chat.completion.chunk",
            created=1,
            model=request.model or "stub-model",
            choices=[{"index": 0, "delta": {"content": "stubbed "}, "finish_reason": None}],
        )
        yield ChatCompletionChunk(
            id="chatcmpl-test",
            object="chat.completion.chunk",
            created=1,
            model=request.model or "stub-model",
            choices=[{"index": 0, "delta": {"content": "reply"}, "finish_reason": None}],
        )
        yield ChatCompletionChunk(
            id="chatcmpl-test",
            object="chat.completion.chunk",
            created=1,
            model=request.model or "stub-model",
            choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}],
        )


def override_agent_service():
    return StubAgentService()


def test_chat_completions_response_shape() -> None:
    app.dependency_overrides[get_agent_service] = override_agent_service
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "test-model"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["choices"][0]["message"]["content"] == "stubbed reply"
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["usage"]["total_tokens"] == 5


def test_chat_completions_stream_shape() -> None:
    app.dependency_overrides[get_agent_service] = override_agent_service
    client = TestClient(app)

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
    ) as response:
        chunks = [line for line in response.iter_lines() if line]

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert chunks[0].startswith("data: ")
    assert '"object":"chat.completion.chunk"' in chunks[0]
    assert '"role":"assistant"' in chunks[0]
    assert '"content":"stubbed "' in chunks[1]
    assert '"content":"reply"' in chunks[2]
    assert chunks[-1] == "data: [DONE]"


class FakeTool(Tool):
    name = "fake_tool"
    description = "A fake tool."
    input_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    async def execute(self, arguments):
        return {"ok": True, "handled": True}


class CapturingClient:
    def __init__(self) -> None:
        self.calls = []

    async def complete(
        self,
        messages,
        tools,
        tool_choice=None,
        parallel_tool_calls=None,
        model=None,
        temperature=None,
        top_p=None,
        max_tokens=None,
        stop=None,
    ):
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "tool_choice": tool_choice,
                "parallel_tool_calls": parallel_tool_calls,
                "model": model,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
                "stop": stop,
            }
        )
        return LLMResponse(
            content="done",
            tool_calls=[],
            raw_message={"role": "assistant", "content": "done"},
        )


def test_chat_completions_forwards_openai_tool_fields() -> None:
    settings = Settings(api_key="test")
    registry = ToolRegistry([FakeTool()])
    service = AgentService(settings=settings, registry=registry)
    client = CapturingClient()
    service._client = client

    response = TestClient(app)
    app.dependency_overrides[get_agent_service] = lambda: service
    result = response.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "fake_tool",
                        "description": "A fake tool.",
                        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                    },
                }
            ],
            "tool_choice": {
                "type": "function",
                "function": {"name": "fake_tool"},
            },
            "parallel_tool_calls": False,
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 128,
            "stop": ["DONE"],
        },
    )
    app.dependency_overrides.clear()

    assert result.status_code == 200
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model"] == "test-model"
    assert call["tool_choice"] == {
        "type": "function",
        "function": {"name": "fake_tool"},
    }
    assert call["parallel_tool_calls"] is False
    assert call["temperature"] == 0.2
    assert call["top_p"] == 0.9
    assert call["max_tokens"] == 128
    assert call["stop"] == ["DONE"]
    assert len(call["tools"]) == 1
    assert call["tools"][0]["function"]["name"] == "fake_tool"


def test_chat_completions_rejects_unrequested_tool_calls() -> None:
    settings = Settings(api_key="test")
    registry = ToolRegistry([FakeTool()])
    service = AgentService(settings=settings, registry=registry)

    class ForcedToolClient:
        async def complete(
            self,
            messages,
            tools,
            tool_choice=None,
            parallel_tool_calls=None,
            model=None,
            temperature=None,
            top_p=None,
            max_tokens=None,
            stop=None,
        ):
            return LLMResponse(
                content="",
                tool_calls=[ToolCall(id="call_1", name="fake_tool", arguments={})],
                raw_message={"role": "assistant", "content": ""},
            )

    service._client = ForcedToolClient()
    final = response = None
    final = TestClient(app)
    app.dependency_overrides[get_agent_service] = lambda: service
    response = final.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [],
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["choices"][0]["message"]["tool_calls"] is None


def test_chat_completions_returns_tool_calls_and_finish_reason() -> None:
    settings = Settings(api_key="test")
    registry = ToolRegistry([FakeTool()])
    service = AgentService(settings=settings, registry=registry)

    class ToolCallingClient:
        async def complete(
            self,
            messages,
            tools,
            tool_choice=None,
            parallel_tool_calls=None,
            model=None,
            temperature=None,
            top_p=None,
            max_tokens=None,
            stop=None,
        ):
            return LLMResponse(
                content="",
                tool_calls=[ToolCall(id="call_1", name="fake_tool", arguments={"x": 1})],
                raw_message={"role": "assistant", "content": "", "reasoning_content": "Need tool output first."},
            )

    service._client = ToolCallingClient()
    client = TestClient(app)
    app.dependency_overrides[get_agent_service] = lambda: service
    response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "use the tool"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "fake_tool",
                        "description": "A fake tool.",
                        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                    },
                }
            ],
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["choices"][0]["finish_reason"] == "tool_calls"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["choices"][0]["message"]["content"] == ""
    assert body["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "fake_tool"
    assert body["choices"][0]["message"]["reasoning_content"] == "Need tool output first."


def test_chat_completions_streams_tool_calls() -> None:
    settings = Settings(api_key="test")
    registry = ToolRegistry([FakeTool()])
    service = AgentService(settings=settings, registry=registry)

    class ToolCallingClient:
        async def complete(
            self,
            messages,
            tools,
            tool_choice=None,
            parallel_tool_calls=None,
            model=None,
            temperature=None,
            top_p=None,
            max_tokens=None,
            stop=None,
        ):
            return LLMResponse(
                content="",
                tool_calls=[ToolCall(id="call_1", name="fake_tool", arguments={"x": 1})],
                raw_message={"role": "assistant", "content": ""},
            )

    service._client = ToolCallingClient()
    client = TestClient(app)
    app.dependency_overrides[get_agent_service] = lambda: service
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "stream": True,
            "messages": [{"role": "user", "content": "use the tool"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "fake_tool",
                        "description": "A fake tool.",
                        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                    },
                }
            ],
        },
    ) as response:
        chunks = [line for line in response.iter_lines() if line]
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"fake_tool","arguments":""}}]' in chunks[1]
    assert '"tool_calls":[{"index":0,"function":{"arguments":"{\\"x\\": 1}"}}]' in chunks[2]
    assert '"finish_reason":"tool_calls"' in chunks[3]


def test_chat_completions_continuation_with_tool_message() -> None:
    settings = Settings(api_key="test")
    registry = ToolRegistry([FakeTool()])
    service = AgentService(settings=settings, registry=registry)

    class ContinuationClient:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(
            self,
            messages,
            tools,
            tool_choice=None,
            parallel_tool_calls=None,
            model=None,
            temperature=None,
            top_p=None,
            max_tokens=None,
            stop=None,
        ):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCall(id="call_1", name="fake_tool", arguments={"path": "."})],
                    raw_message={"role": "assistant", "content": ""},
                )
            assert messages[-1]["role"] == "tool"
            assert messages[-1]["tool_call_id"] == "call_1"
            assert "handled" in messages[-1]["content"]
            return LLMResponse(
                content="The tool completed successfully.",
                tool_calls=[],
                raw_message={"role": "assistant", "content": "The tool completed successfully."},
            )

    service._client = ContinuationClient()
    client = TestClient(app)
    app.dependency_overrides[get_agent_service] = lambda: service

    first_response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "inspect the workspace"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "fake_tool",
                        "description": "A fake tool.",
                        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                    },
                }
            ],
        },
    )
    first_body = first_response.json()
    tool_call = first_body["choices"][0]["message"]["tool_calls"][0]

    second_response = client.post(
        "/v1/chat/completions",
        json={
            "messages": [
                {"role": "user", "content": "inspect the workspace"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [tool_call],
                },
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": tool_call["function"]["name"],
                    "content": "{\"ok\": true, \"handled\": true}",
                },
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "fake_tool",
                        "description": "A fake tool.",
                        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                    },
                }
            ],
        },
    )
    app.dependency_overrides.clear()

    assert first_response.status_code == 200
    assert first_body["choices"][0]["finish_reason"] == "tool_calls"
    assert second_response.status_code == 200
    second_body = second_response.json()
    assert second_body["choices"][0]["finish_reason"] == "stop"
    assert second_body["choices"][0]["message"]["content"] == "The tool completed successfully."
