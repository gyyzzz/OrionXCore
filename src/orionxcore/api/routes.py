import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from orionxcore.api.playground import render_playground
from orionxcore.config import Settings, get_settings
from orionxcore.schemas import AgentRequest, AgentResponse, ChatCompletionRequest
from orionxcore.schemas import ChatCompletionResponse
from orionxcore.schemas import ToolDescriptor
from orionxcore.services.agent import AgentService
from orionxcore.tools.registry import build_registry

router = APIRouter()


def get_agent_service(settings: Settings = Depends(get_settings)) -> AgentService:
    return AgentService(settings=settings, registry=build_registry(settings))


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict[str, str | bool]:
    return {
        "name": settings.app_name,
        "status": "ok",
        "terminal_enabled": settings.enable_terminal,
        "database_enabled": settings.enable_database,
    }


@router.get("/v1/tools", response_model=list[ToolDescriptor])
async def list_tools(settings: Settings = Depends(get_settings)) -> list[ToolDescriptor]:
    registry = build_registry(settings)
    return registry.describe()


@router.post("/v1/agent/respond", response_model=AgentResponse)
async def respond(
    request: AgentRequest,
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    return await agent_service.run(request)


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    agent_service: AgentService = Depends(get_agent_service),
) -> ChatCompletionResponse | StreamingResponse:
    if request.stream:
        async def event_stream() -> AsyncIterator[str]:
            async for chunk in agent_service.stream_chat_completion(request):
                yield f"data: {chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return await agent_service.run_chat_completion(request)


@router.post("/v1/agent/stream")
async def stream(
    request: AgentRequest,
    agent_service: AgentService = Depends(get_agent_service),
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        async for event in agent_service.stream(request):
            yield f"event: {event.type}\n"
            yield f"data: {json.dumps(event.payload, ensure_ascii=True)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/")
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "service": "OrionXCore",
            "docs_hint": "Use /health, /v1/tools, /v1/agent/respond, /v1/agent/stream, or /playground.",
        }
    )


@router.get("/playground", response_class=HTMLResponse)
async def playground() -> HTMLResponse:
    return render_playground()
