from typing import Any

from orionxcore.config import Settings
from orionxcore.schemas import ToolDescriptor
from orionxcore.tools.base import Tool
from orionxcore.tools.database import DatabaseTool
from orionxcore.tools.terminal import TerminalTool


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def describe(self) -> list[ToolDescriptor]:
        return [
            ToolDescriptor(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
            )
            for tool in self._tools.values()
        ]

    def as_openai_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in self._tools.values()
        ]

    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        return await tool.execute(arguments)


def build_registry(settings: Settings) -> ToolRegistry:
    tools: list[Tool] = []
    if settings.enable_terminal:
        tools.append(TerminalTool(settings))
    if settings.enable_database:
        tools.append(DatabaseTool(settings))
    return ToolRegistry(tools)

