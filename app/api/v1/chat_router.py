"""Chat API router for LangGraph agent interactions."""

import json
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import get_agent_service, get_llm, require_role
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.schemas.response_schema import ApiResponse, success_response
from app.services.agent_service import AgentService
from app.services.chat_title_task import generate_session_title

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
    background_tasks: BackgroundTasks,
) -> dict:
    """Process a chat request and return a response."""
    result, is_new_session = await agent_service.chat(request)
    if is_new_session:
        background_tasks.add_task(
            generate_session_title,
            session_id=result.session_id,
            message=request.message,
            llm=get_llm(),
        )
    return success_response(result)


async def event_generator(
    agent_service: AgentService,
    request: ChatRequest,
    background_tasks: BackgroundTasks,
) -> AsyncGenerator[str, None]:
    """Generate Server-Sent Events from agent stream."""
    async for event in agent_service.stream_chat(request):
        if event.event == "done":
            done_data = json.loads(event.data)
            if done_data.get("is_new_session"):
                background_tasks.add_task(
                    generate_session_title,
                    session_id=done_data["session_id"],
                    message=request.message,
                    llm=get_llm(),
                )
        event_data = event.model_dump()
        yield f"data: {json.dumps(event_data)}\n\n"


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    agent_service: AgentServiceDep,
    background_tasks: BackgroundTasks,
) -> StreamingResponse:
    """Stream chat response as Server-Sent Events."""
    return StreamingResponse(
        event_generator(agent_service, request, background_tasks),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
