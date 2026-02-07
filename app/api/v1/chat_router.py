"""Chat API router for LangGraph agent interactions."""

import json
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import get_agent_service
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    agent_service: AgentServiceDep,
) -> ChatResponse:
    """Process a chat request and return a response.

    Args:
        request: The chat request containing the user message.
        agent_service: The agent service dependency.

    Returns:
        ChatResponse with the agent's reply.
    """
    return await agent_service.chat(request)


async def event_generator(
    agent_service: AgentService,
    request: ChatRequest,
) -> AsyncGenerator[str, None]:
    """Generate Server-Sent Events from agent stream.

    Args:
        agent_service: The agent service instance.
        request: The chat request.

    Yields:
        SSE formatted strings.
    """
    async for event in agent_service.stream_chat(request):
        event_data = event.model_dump()
        yield f"data: {json.dumps(event_data)}\n\n"


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    agent_service: AgentServiceDep,
) -> StreamingResponse:
    """Stream chat response as Server-Sent Events.

    Args:
        request: The chat request containing the user message.
        agent_service: The agent service dependency.

    Returns:
        StreamingResponse with SSE content.
    """
    return StreamingResponse(
        event_generator(agent_service, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
