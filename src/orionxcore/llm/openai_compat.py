import json
from dataclasses import dataclass
from typing import Any

import httpx

from orionxcore.config import Settings


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall]
    raw_message: dict[str, Any]


class OpenAICompatibleClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        payload = {
            "model": self._settings.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto" if tools else "none",
        }
        headers = {
            "Authorization": f"Bearer {self._settings.api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(self._settings.http_timeout)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self._settings.api_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        message = data["choices"][0]["message"]
        tool_calls = [self._parse_tool_call(item) for item in message.get("tool_calls", [])]
        return LLMResponse(
            content=self._flatten_content(message.get("content")),
            tool_calls=tool_calls,
            raw_message=message,
        )

    def _parse_tool_call(self, item: dict[str, Any]) -> ToolCall:
        function = item.get("function", {})
        arguments = function.get("arguments") or "{}"
        if isinstance(arguments, str):
            parsed_arguments = json.loads(arguments)
        else:
            parsed_arguments = arguments
        return ToolCall(
            id=item["id"],
            name=function["name"],
            arguments=parsed_arguments,
        )

    def _flatten_content(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "\n".join(part for part in parts if part)
        return str(content)

