"""Chat API router for LangGraph agent interactions."""

import json
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import get_agent_service, require_role
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.schemas.response_schema import ApiResponse, success_response
from app.services.agent_service import AgentService

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["chat"],
    dependencies=[Depends(require_role("user", "admin"))],
)

AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]


@router.post("", response_model=ApiResponse[ChatResponse])
async def chat(
    request: ChatRequest,
    agent_service: AgentServiceDep,
) -> dict:
    """Process a chat request and return a response.

    Args:
        request: The chat request containing the user message.
        agent_service: The agent service dependency.

    Returns:
        ApiResponse wrapping ChatResponse with the agent's reply.
    """
    result = await agent_service.chat(request)
    return success_response(result)


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
