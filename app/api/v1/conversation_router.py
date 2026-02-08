"""Conversation list API router."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_conversation_service, require_role
from app.schemas.conversation_schema import ConversationListResponse
from app.schemas.response_schema import ApiResponse, success_response
from app.services.conversation_service import ConversationService

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["conversations"],
    dependencies=[Depends(require_role("user", "admin"))],
)

ConversationServiceDep = Annotated[
    ConversationService, Depends(get_conversation_service)
]


@router.get("", response_model=ApiResponse[ConversationListResponse])
async def list_conversations(
    service: ConversationServiceDep,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """List the current user's conversations with cursor-based pagination."""
    result = await service.list_conversations(limit=limit, cursor=cursor)
    return success_response(result)
