"""Unit tests for ChatRepository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.repositories.chat_repo import ChatRepository


@pytest.fixture
def chat_repo(db_session: AsyncSession) -> ChatRepository:
    """Create a ChatRepository backed by the test DB session."""
    return ChatRepository(db_session)


async def _create_user(db_session: AsyncSession) -> int:
    """Helper: insert a minimal user row and return its id."""
    from app.models.user import User

    user = User(
        email="chatuser@test.com",
        hashed_password="hashed",
        username="chatuser",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user.id


class TestCreateSession:
    """Tests for ChatRepository.create_session."""

    @pytest.mark.asyncio
    async def test_create_session(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-001"
        )

        assert session.id is not None
        assert session.user_id == user_id
        assert session.conversation_id == "conv-001"
        assert session.title is None

    @pytest.mark.asyncio
    async def test_create_session_with_title(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session = await chat_repo.create_session(
            user_id=user_id,
            conversation_id="conv-002",
            title="Test Title",
        )

        assert session.title == "Test Title"


class TestFindSessionByConversationId:
    """Tests for ChatRepository.find_session_by_conversation_id."""

    @pytest.mark.asyncio
    async def test_find_existing_session(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        await chat_repo.create_session(user_id=user_id, conversation_id="conv-find")

        found = await chat_repo.find_session_by_conversation_id("conv-find")
        assert found is not None
        assert found.conversation_id == "conv-find"

    @pytest.mark.asyncio
    async def test_find_nonexistent_session(self, chat_repo: ChatRepository) -> None:
        found = await chat_repo.find_session_by_conversation_id("no-such")
        assert found is None


class TestCreateMessage:
    """Tests for ChatRepository.create_message."""

    @pytest.mark.asyncio
    async def test_create_human_message(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-msg"
        )

        msg = await chat_repo.create_message(
            session_id=session.id, role="human", content="Hello"
        )

        assert msg.id is not None
        assert msg.role == "human"
        assert msg.content == "Hello"
        assert msg.tool_calls_json is None

    @pytest.mark.asyncio
    async def test_create_ai_message_with_tool_calls(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-ai"
        )

        msg = await chat_repo.create_message(
            session_id=session.id,
            role="ai",
            content="Let me search",
            tool_calls_json='[{"name":"web_search","args":{"query":"test"}}]',
        )

        assert msg.role == "ai"
        assert msg.tool_calls_json is not None

    @pytest.mark.asyncio
    async def test_create_tool_message(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-tool"
        )

        msg = await chat_repo.create_message(
            session_id=session.id,
            role="tool",
            content="Search results...",
            tool_call_id="call_123",
            tool_name="web_search",
        )

        assert msg.role == "tool"
        assert msg.tool_call_id == "call_123"
        assert msg.tool_name == "web_search"


class TestFindMessagesBySessionId:
    """Tests for ChatRepository.find_messages_by_session_id."""

    @pytest.mark.asyncio
    async def test_find_messages_ordered_by_id(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-order"
        )

        await chat_repo.create_message(
            session_id=session.id, role="human", content="First"
        )
        await chat_repo.create_message(
            session_id=session.id, role="ai", content="Second"
        )
        await chat_repo.create_message(
            session_id=session.id, role="human", content="Third"
        )

        messages = await chat_repo.find_messages_by_session_id(session.id)

        assert len(messages) == 3
        assert messages[0].content == "First"
        assert messages[1].content == "Second"
        assert messages[2].content == "Third"

    @pytest.mark.asyncio
    async def test_find_messages_empty_session(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-empty"
        )

        messages = await chat_repo.find_messages_by_session_id(session.id)
        assert messages == []


class TestCreateMessagesBulk:
    """Tests for ChatRepository.create_messages_bulk."""

    @pytest.mark.asyncio
    async def test_create_messages_bulk(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-bulk"
        )

        records = [
            ChatMessage(session_id=session.id, role="human", content="Q1"),
            ChatMessage(session_id=session.id, role="ai", content="A1"),
            ChatMessage(session_id=session.id, role="human", content="Q2"),
        ]
        await chat_repo.create_messages_bulk(records)

        messages = await chat_repo.find_messages_by_session_id(session.id)
        assert len(messages) == 3


class TestUpdateSessionTitle:
    """Tests for ChatRepository.update_session_title."""

    @pytest.mark.asyncio
    async def test_update_session_title(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-title"
        )
        assert session.title is None

        await chat_repo.update_session_title(session.id, "New Title")

        updated = await chat_repo.find_session_by_conversation_id("conv-title")
        assert updated is not None
        assert updated.title == "New Title"
