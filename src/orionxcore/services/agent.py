import json
import time
import uuid
from datetime import datetime, date
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable

from orionxcore.config import Settings
from orionxcore.llm.openai_compat import OpenAICompatibleClient
from orionxcore.schemas import AgentEvent, AgentRequest, AgentResponse
from orionxcore.schemas import ChatCompletionChunk, ChatCompletionChunkChoice, ChatCompletionDelta
from orionxcore.schemas import ChatCompletionMessage, ChatCompletionRequest, ChatCompletionResponse
from orionxcore.schemas import ChatCompletionChoice, ChatCompletionUsage, ChatMessage
from orionxcore.tools.registry import ToolRegistry


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime and date objects."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """JSON dumps that handles datetime objects."""
    return json.dumps(obj, cls=DateTimeEncoder, **kwargs)


@dataclass
class ChatCompletionTurnResult:
    content: str
    tool_calls: list[dict[str, Any]]
    finish_reason: str
    model: str
    reasoning_content: str | None = None


class AgentService:
    def __init__(self, settings: Settings, registry: ToolRegistry) -> None:
        self._settings = settings
        self._registry = registry
        self._client = OpenAICompatibleClient(settings)

    async def run(self, request: AgentRequest) -> AgentResponse:
        events: list[AgentEvent] = []
        final_message, iterations = await self._run_loop(request, events.append)
        return AgentResponse(
            message=final_message,
            events=events,
            iterations=iterations,
            session_id=request.session_id,
        )

    async def stream(self, request: AgentRequest) -> AsyncIterator[AgentEvent]:
        events: list[AgentEvent] = []

        def emit(event: AgentEvent) -> None:
            events.append(event)

        final_message, iterations = await self._run_loop(request, emit)
        for event in events:
            yield event
        yield AgentEvent(
            type="final",
            payload={
                "message": final_message.model_dump(),
                "iterations": iterations,
                "session_id": request.session_id,
            },
        )

    async def run_chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        turn = await self._run_chat_completion_turn(request)
        created = int(time.time())
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        usage = self._estimate_usage(request.messages, turn.content)
        return ChatCompletionResponse(
            id=completion_id,
            object="chat.completion",
            created=created,
            model=turn.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=turn.content,
                        tool_calls=turn.tool_calls or None,
                        reasoning_content=turn.reasoning_content,
                    ),
                    finish_reason=turn.finish_reason,
                )
            ],
            usage=usage,
        )

    async def stream_chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatCompletionChunk]:
        response = await self.run_chat_completion(request)
        content_parts = self._split_stream_content(response.choices[0].message.content or "")
        yield ChatCompletionChunk(
            id=response.id,
            object="chat.completion.chunk",
            created=response.created,
            model=response.model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionDelta(role="assistant"),
                    finish_reason=None,
                )
            ],
        )
        tool_calls = response.choices[0].message.tool_calls or []
        if tool_calls:
            for delta_tool_call in self._stream_tool_call_deltas(tool_calls):
                yield ChatCompletionChunk(
                    id=response.id,
                    object="chat.completion.chunk",
                    created=response.created,
                    model=response.model,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta=ChatCompletionDelta(tool_calls=[delta_tool_call]),
                            finish_reason=None,
                        )
                    ],
                )
        for part in content_parts:
            yield ChatCompletionChunk(
                id=response.id,
                object="chat.completion.chunk",
                created=response.created,
                model=response.model,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionDelta(content=part),
                        finish_reason=None,
                    )
                ],
            )
        yield ChatCompletionChunk(
            id=response.id,
            object="chat.completion.chunk",
            created=response.created,
            model=response.model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionDelta(),
                    finish_reason=response.choices[0].finish_reason,
                )
            ],
        )

    async def _run_chat_completion_turn(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionTurnResult:
        messages = self._build_messages(
            AgentRequest(messages=request.messages, metadata=request.metadata),
            include_system_prompt=False,
        )
        registry = self._registry.filtered(request.tools)
        tools = registry.as_openai_tools()
        llm_response = await self._client.complete(
            messages=messages,
            tools=tools,
            tool_choice=request.tool_choice,
            parallel_tool_calls=request.parallel_tool_calls,
            model=request.model,
            temperature=request.temperature,
            top_p=request.top_p,
            max_tokens=request.max_tokens,
            stop=request.stop,
        )
        allowed_tool_names = {tool["function"]["name"] for tool in tools}
        valid_tool_calls = [
            call for call in llm_response.tool_calls if call.name in allowed_tool_names
        ]
        if valid_tool_calls:
            return ChatCompletionTurnResult(
                content=llm_response.content,
                tool_calls=[
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=True),
                        },
                    }
                    for call in valid_tool_calls
                ],
                finish_reason="tool_calls",
                model=request.model or self._settings.model,
                reasoning_content=llm_response.raw_message.get("reasoning_content"),
            )
        return ChatCompletionTurnResult(
            content=llm_response.content,
            tool_calls=[],
            finish_reason="stop",
            model=request.model or self._settings.model,
            reasoning_content=llm_response.raw_message.get("reasoning_content"),
        )

    async def _run_loop(
        self,
        request: AgentRequest,
        emit: Callable[[AgentEvent], None],
        requested_tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        model: str | None = None,
    ) -> tuple[ChatMessage, int]:
        messages = self._build_messages(request)
        registry = self._registry.filtered(requested_tools)
        tools = registry.as_openai_tools()

        for iteration in range(1, self._settings.max_iterations + 1):
            emit(AgentEvent(type="iteration", payload={"iteration": iteration}))
            llm_response = await self._client.complete(
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                parallel_tool_calls=parallel_tool_calls,
                model=model,
            )

            if llm_response.tool_calls:
                assistant_message = {
                    "role": "assistant",
                    "content": llm_response.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments, ensure_ascii=True),
                            },
                        }
                        for call in llm_response.tool_calls
                    ],
                }
                reasoning_content = llm_response.raw_message.get("reasoning_content")
                if reasoning_content is not None:
                    assistant_message["reasoning_content"] = reasoning_content
                messages.append(assistant_message)

                for call in llm_response.tool_calls:
                    emit(
                        AgentEvent(
                            type="tool_call",
                            payload={"name": call.name, "arguments": call.arguments},
                        )
                    )
                    result = await registry.execute(call.name, call.arguments)
                    emit(
                        AgentEvent(
                            type="tool_result",
                            payload={"name": call.name, "result": result},
                        )
                    )
                    self._emit_tool_trace_events(call.name, result, emit)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.name,
                            "content": safe_json_dumps(result, ensure_ascii=True),
                        }
                    )
                continue

            final_message = ChatMessage(role="assistant", content=llm_response.content)
            emit(AgentEvent(type="assistant", payload={"content": llm_response.content}))
            return final_message, iteration

        content = (
            "The agent stopped because the maximum iteration count was reached before a final "
            "answer was produced."
        )
        final_message = ChatMessage(role="assistant", content=content)
        emit(AgentEvent(type="assistant", payload={"content": content}))
        return final_message, self._settings.max_iterations

    def _build_messages(self, request: AgentRequest) -> list[dict[str, Any]]:
        return self._build_messages_with_options(request, include_system_prompt=True)

    def _build_messages_with_options(
        self,
        request: AgentRequest,
        include_system_prompt: bool,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if include_system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": self._settings.system_prompt
                    + "\nUse tools when they help. Explain risky actions before requesting them.",
                }
            )
        messages.extend(message.model_dump(exclude_none=True) for message in request.messages)
        return messages

    def _build_messages(
        self,
        request: AgentRequest,
        include_system_prompt: bool = True,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if include_system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": self._settings.system_prompt
                    + "\nUse tools when they help. Explain risky actions before requesting them.",
                }
            )
        messages.extend(message.model_dump(exclude_none=True) for message in request.messages)
        return messages

    def _estimate_usage(
        self,
        request_messages: list[ChatMessage],
        completion_content: Any,
    ) -> ChatCompletionUsage:
        prompt_text = " ".join(str(message.content) for message in request_messages)
        completion_text = str(completion_content or "")
        prompt_tokens = self._estimate_tokens(prompt_text)
        completion_tokens = self._estimate_tokens(completion_text)
        return ChatCompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    def _estimate_tokens(self, text: str) -> int:
        stripped = text.strip()
        if not stripped:
            return 0
        return len(stripped.split())

    def _emit_tool_trace_events(
        self,
        tool_name: str,
        result: dict[str, Any],
        emit: Callable[[AgentEvent], None],
    ) -> None:
        if tool_name != "database_query":
            return
        trace = result.get("trace")
        if not isinstance(trace, dict):
            return

        emit(
            AgentEvent(
                type="database_trace",
                payload={
                    "question": trace.get("question"),
                    "database": trace.get("database"),
                    "tables": trace.get("tables", []),
                    "attempt_count": trace.get("attempt_count"),
                    "final_sql": trace.get("final_sql"),
                },
            )
        )
        schema_context = trace.get("schema_context")
        if schema_context:
            emit(
                AgentEvent(
                    type="database_schema_context",
                    payload={"schema_context": schema_context},
                )
            )
        for attempt in trace.get("attempts", []):
            emit(
                AgentEvent(
                    type="database_sql_attempt",
                    payload={
                        "attempt": attempt.get("attempt"),
                        "sql": attempt.get("sql"),
                        "retry_reason": attempt.get("retry_reason"),
                        "error": attempt.get("error"),
                    },
                )
            )
        emit(
            AgentEvent(
                type="database_result_summary",
                payload={
                    "ok": result.get("ok"),
                    "row_count": result.get("row_count"),
                    "columns": result.get("columns", []),
                    "generated_sql": result.get("generated_sql"),
                },
            )
        )

    def _split_stream_content(self, content: str) -> list[str]:
        if not content:
            return []
        words = content.split(" ")
        if len(words) <= 1:
            return [content]
        parts: list[str] = []
        for index, word in enumerate(words):
            if index < len(words) - 1:
                parts.append(f"{word} ")
            else:
                parts.append(word)
        return parts

    def _stream_tool_call_deltas(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deltas: list[dict[str, Any]] = []
        for index, tool_call in enumerate(tool_calls):
            function = tool_call.get("function", {})
            arguments = function.get("arguments", "")
            deltas.append(
                {
                    "index": index,
                    "id": tool_call.get("id"),
                    "type": tool_call.get("type", "function"),
                    "function": {
                        "name": function.get("name"),
                        "arguments": "",
                    },
                }
            )
            for part in self._split_argument_stream(arguments):
                deltas.append(
                    {
                        "index": index,
                        "function": {
                            "arguments": part,
                        },
                    }
                )
        return deltas

    def _split_argument_stream(self, arguments: str) -> list[str]:
        if not arguments:
            return []
        chunk_size = 12
        return [arguments[i : i + chunk_size] for i in range(0, len(arguments), chunk_size)]
