"""Chat repository for session and message database operations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession


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

    async def update_session_title(self, session_id: int, title: str) -> None:
        """Update the title of an existing session."""
        result = await self._session.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            session.title = title
            await self._session.flush()
