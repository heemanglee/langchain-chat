"""Service layer for conversation list with cursor-based pagination."""

import base64
import json
from datetime import UTC, datetime

from app.core.exceptions import AppException, AuthorizationError, SessionNotFoundError
from app.repositories.chat_repo import ChatRepository
from app.schemas.conversation_schema import (
    ConversationListResponse,
    ConversationMessagesResponse,
    ConversationSummary,
    MessageResponse,
)


def encode_cursor(updated_at: datetime, session_id: int) -> str:
    """Encode pagination cursor as base64url JSON."""
    payload = {"u": updated_at.isoformat(), "i": session_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    """Decode pagination cursor. Raises AppException on invalid input."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        data = json.loads(raw)
        updated_at = datetime.fromisoformat(data["u"])
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        session_id = int(data["i"])
        return updated_at, session_id
    except Exception as exc:
        raise AppException(
            message=f"Invalid cursor: {exc}",
            code="INVALID_CURSOR",
            status_code=400,
        ) from exc


class ConversationService:
    """Orchestrates conversation list queries with cursor pagination."""

    def __init__(self, chat_repo: ChatRepository, user_id: int) -> None:
        self._chat_repo = chat_repo
        self._user_id = user_id

    async def get_messages(self, conversation_id: str) -> ConversationMessagesResponse:
        """Retrieve all messages for a conversation owned by the current user."""
        session = await self._chat_repo.find_session_by_conversation_id(conversation_id)
        if session is None:
            raise SessionNotFoundError()
        if session.user_id != self._user_id:
            raise AuthorizationError(message="Not authorized to view this conversation")
        messages = await self._chat_repo.find_messages_by_session_id(session.id)
        return ConversationMessagesResponse(
            conversation_id=conversation_id,
            messages=[MessageResponse.model_validate(msg) for msg in messages],
        )

    async def update_title(self, conversation_id: str, title: str) -> None:
        """Update the title of a conversation owned by the current user."""
        session = await self._chat_repo.find_session_by_conversation_id(conversation_id)
        if session is None:
            raise SessionNotFoundError()
        if session.user_id != self._user_id:
            raise AuthorizationError(
                message="Not authorized to update this conversation"
            )
        await self._chat_repo.update_session_title(session.id, title)

    async def list_conversations(
        self,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ConversationListResponse:
        """Return a paginated list of the user's conversations."""
        cursor_updated_at: datetime | None = None
        cursor_id: int | None = None

        if cursor is not None:
            cursor_updated_at, cursor_id = decode_cursor(cursor)

        rows = await self._chat_repo.find_sessions_by_user(
            user_id=self._user_id,
            limit=limit + 1,
            cursor_updated_at=cursor_updated_at,
            cursor_id=cursor_id,
        )

        has_next = len(rows) > limit
        page_rows = rows[:limit]

        next_cursor: str | None = None
        if has_next and page_rows:
            last = page_rows[-1]
            next_cursor = encode_cursor(last.updated_at, last.id)

        conversations = [
            ConversationSummary(
                conversation_id=r.conversation_id,
                title=r.title,
                last_message_preview=r.last_message_preview,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in page_rows
        ]

        return ConversationListResponse(
            conversations=conversations,
            next_cursor=next_cursor,
            has_next=has_next,
        )
