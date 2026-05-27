import json
from typing import Any, AsyncIterator, Callable

from orionxcore.config import Settings
from orionxcore.llm.openai_compat import OpenAICompatibleClient
from orionxcore.schemas import AgentEvent, AgentRequest, AgentResponse, ChatMessage
from orionxcore.tools.registry import ToolRegistry


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

    async def _run_loop(
        self,
        request: AgentRequest,
        emit: Callable[[AgentEvent], None],
    ) -> tuple[ChatMessage, int]:
        messages = self._build_messages(request)
        tools = self._registry.as_openai_tools()

        for iteration in range(1, self._settings.max_iterations + 1):
            emit(AgentEvent(type="iteration", payload={"iteration": iteration}))
            llm_response = await self._client.complete(messages=messages, tools=tools)

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
                messages.append(assistant_message)

                for call in llm_response.tool_calls:
                    emit(
                        AgentEvent(
                            type="tool_call",
                            payload={"name": call.name, "arguments": call.arguments},
                        )
                    )
                    result = await self._registry.execute(call.name, call.arguments)
                    emit(
                        AgentEvent(
                            type="tool_result",
                            payload={"name": call.name, "result": result},
                        )
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.name,
                            "content": json.dumps(result, ensure_ascii=True),
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
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self._settings.system_prompt
                + "\nUse tools when they help. Explain risky actions before requesting them.",
            }
        ]
        messages.extend(message.model_dump(exclude_none=True) for message in request.messages)
        return messages
