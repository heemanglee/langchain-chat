"""Chat repository for session and message database operations."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession


@dataclass(frozen=True)
class SessionWithPreview:
    """Immutable result object for session list queries."""

    id: int
    conversation_id: str
    title: str | None
    last_message_preview: str | None
    created_at: datetime
    updated_at: datetime


class ChatRepository:
    """Encapsulates chat session and message database queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_session_by_conversation_id(
        self, conversation_id: str
    ) -> ChatSession | None:
        """Find a chat session by its conversation UUID."""
        result = await self._session.execute(
            select(ChatSession).where(ChatSession.conversation_id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def create_session(
        self,
        user_id: int,
        conversation_id: str,
        title: str | None = None,
    ) -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(
            user_id=user_id,
            conversation_id=conversation_id,
            title=title,
        )
        self._session.add(session)
        await self._session.flush()
        await self._session.refresh(session)
        return session

    async def find_messages_by_session_id(self, session_id: int) -> list[ChatMessage]:
        """Retrieve all messages for a session in chronological order."""
        result = await self._session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.asc())
        )
        return list(result.scalars().all())

    async def create_message(
        self,
        session_id: int,
        role: str,
        content: str,
        tool_calls_json: str | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
    ) -> ChatMessage:
        """Create a single chat message."""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls_json=tool_calls_json,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )
        self._session.add(message)
        await self._session.flush()
        await self._session.refresh(message)
        return message

    async def create_messages_bulk(self, messages: list[ChatMessage]) -> None:
        """Save multiple messages in a single batch."""
        self._session.add_all(messages)
        await self._session.flush()

    async def find_sessions_by_user(
        self,
        user_id: int,
        limit: int,
        cursor_updated_at: datetime | None = None,
        cursor_id: int | None = None,
    ) -> list[SessionWithPreview]:
        """Fetch user sessions with keyset pagination (updated_at DESC, id DESC).

        Returns ``limit`` rows. The caller should request ``limit + 1`` to
        detect whether a next page exists.
        """
        # Correlated scalar subquery: latest human message content per session
        preview_subq = (
            select(ChatMessage.content)
            .where(
                and_(
                    ChatMessage.session_id == ChatSession.id,
                    ChatMessage.role == "human",
                )
            )
            .order_by(ChatMessage.id.desc())
            .limit(1)
            .correlate(ChatSession)
            .scalar_subquery()
        )

        stmt = select(
            ChatSession.id,
            ChatSession.conversation_id,
            ChatSession.title,
            preview_subq.label("last_message_preview"),
            ChatSession.created_at,
            ChatSession.updated_at,
        ).where(ChatSession.user_id == user_id)

        if cursor_updated_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    ChatSession.updated_at < cursor_updated_at,
                    and_(
                        ChatSession.updated_at == cursor_updated_at,
                        ChatSession.id < cursor_id,
                    ),
                )
            )

        stmt = stmt.order_by(
            ChatSession.updated_at.desc(),
            ChatSession.id.desc(),
        ).limit(limit)

        result = await self._session.execute(stmt)
        return [
            SessionWithPreview(
                id=row.id,
                conversation_id=row.conversation_id,
                title=row.title,
                last_message_preview=row.last_message_preview,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in result
        ]

    async def find_message_by_id(self, message_id: int) -> ChatMessage | None:
        """Find a chat message by its primary key."""
        result = await self._session.execute(
            select(ChatMessage).where(ChatMessage.id == message_id)
        )
        return result.scalar_one_or_none()

    async def delete_messages_from_id(
        self, session_id: int, from_message_id: int
    ) -> None:
        """Hard-delete all messages in a session with id >= from_message_id."""
        await self._session.execute(
            delete(ChatMessage).where(
                and_(
                    ChatMessage.session_id == session_id,
                    ChatMessage.id >= from_message_id,
                )
            )
        )

    async def update_session_title(self, session_id: int, title: str) -> None:
        """Update the title of an existing session."""
        await self._session.execute(
            update(ChatSession).where(ChatSession.id == session_id).values(title=title)
        )
