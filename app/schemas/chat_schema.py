"""Chat request and response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Individual chat message."""

    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    """Chat API request schema."""

    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None
    use_web_search: bool = True


class ChatResponse(BaseModel):
    """Chat API response schema."""

    message: str
    conversation_id: str
    sources: list[str] = Field(default_factory=list)
    created_at: datetime


class StreamEvent(BaseModel):
    """Server-Sent Event for streaming responses."""

    event: Literal["token", "tool_call", "tool_result", "done", "error"]
    data: str
