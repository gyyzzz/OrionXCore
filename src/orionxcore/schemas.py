from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["system", "user", "assistant", "tool"]
    content: Any
    name: str | None = None
    tool_call_id: str | None = None


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    messages: list[ChatMessage]
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentEvent(BaseModel):
    type: str
    payload: dict[str, Any]


class AgentResponse(BaseModel):
    message: ChatMessage
    events: list[AgentEvent] = Field(default_factory=list)
    iterations: int
    session_id: str | None = None


class ToolDescriptor(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]

