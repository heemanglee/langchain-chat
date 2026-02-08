"""Conversation list API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationSummary(BaseModel):
    """Single conversation entry in the list response."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    conversation_id: str
    title: str | None = None
    last_message_preview: str | None = None
    created_at: datetime
    updated_at: datetime


class UpdateTitleRequest(BaseModel):
    """Request to update conversation title."""

    title: str = Field(..., min_length=1, max_length=20)


class ConversationListResponse(BaseModel):
    """Paginated conversation list with cursor metadata."""

    model_config = ConfigDict(frozen=True)

    conversations: list[ConversationSummary]
    next_cursor: str | None = None
    has_next: bool = False
