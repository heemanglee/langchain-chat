"""Unit tests for ChatRepository."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.repositories.chat_repo import ChatRepository


@pytest.fixture
def chat_repo(db_session: AsyncSession) -> ChatRepository:
    """Create a ChatRepository backed by the test DB session."""
    return ChatRepository(db_session)


async def _create_user(
    db_session: AsyncSession, email: str = "chatuser@test.com"
) -> int:
    """Helper: insert a minimal user row and return its id."""
    from app.models.user import User

    user = User(
        email=email,
        hashed_password="hashed",
        username=email.split("@")[0],
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user.id


async def _create_session_with_ts(
    db_session: AsyncSession,
    user_id: int,
    conversation_id: str,
    updated_at: datetime,
    title: str | None = None,
) -> ChatSession:
    """Helper: insert a session with explicit updated_at for pagination tests."""
    session = ChatSession(
        user_id=user_id,
        conversation_id=conversation_id,
        title=title,
        updated_at=updated_at,
    )
    db_session.add(session)
    await db_session.flush()
    await db_session.refresh(session)
    return session


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


class TestFindMessageById:
    """Tests for ChatRepository.find_message_by_id."""

    @pytest.mark.asyncio
    async def test_find_existing_message(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-find-msg"
        )
        msg = await chat_repo.create_message(
            session_id=session.id, role="human", content="Hello"
        )

        found = await chat_repo.find_message_by_id(msg.id)
        assert found is not None
        assert found.id == msg.id
        assert found.content == "Hello"

    @pytest.mark.asyncio
    async def test_find_nonexistent_message(self, chat_repo: ChatRepository) -> None:
        found = await chat_repo.find_message_by_id(99999)
        assert found is None


class TestDeleteMessagesFromId:
    """Tests for ChatRepository.delete_messages_from_id."""

    @pytest.mark.asyncio
    async def test_delete_messages_from_id(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-del"
        )

        await chat_repo.create_message(
            session_id=session.id, role="human", content="Q1"
        )
        await chat_repo.create_message(session_id=session.id, role="ai", content="A1")
        msg3 = await chat_repo.create_message(
            session_id=session.id, role="human", content="Q2"
        )
        await chat_repo.create_message(session_id=session.id, role="ai", content="A2")

        # Delete from msg3 (Q2) onwards
        await chat_repo.delete_messages_from_id(session.id, msg3.id)

        remaining = await chat_repo.find_messages_by_session_id(session.id)
        assert len(remaining) == 2
        assert remaining[0].content == "Q1"
        assert remaining[1].content == "A1"

    @pytest.mark.asyncio
    async def test_delete_from_first_message(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-del-all"
        )

        msg1 = await chat_repo.create_message(
            session_id=session.id, role="human", content="Q1"
        )
        await chat_repo.create_message(session_id=session.id, role="ai", content="A1")

        await chat_repo.delete_messages_from_id(session.id, msg1.id)

        remaining = await chat_repo.find_messages_by_session_id(session.id)
        assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_delete_does_not_affect_other_sessions(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session1 = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-s1"
        )
        session2 = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-s2"
        )

        msg1 = await chat_repo.create_message(
            session_id=session1.id, role="human", content="S1-Q1"
        )
        await chat_repo.create_message(
            session_id=session2.id, role="human", content="S2-Q1"
        )

        await chat_repo.delete_messages_from_id(session1.id, msg1.id)

        s1_msgs = await chat_repo.find_messages_by_session_id(session1.id)
        s2_msgs = await chat_repo.find_messages_by_session_id(session2.id)
        assert len(s1_msgs) == 0
        assert len(s2_msgs) == 1


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


class TestFindSessionsByUser:
    """Tests for ChatRepository.find_sessions_by_user."""

    @pytest.mark.asyncio
    async def test_empty_result(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        rows = await chat_repo.find_sessions_by_user(user_id=user_id, limit=10)
        assert rows == []

    @pytest.mark.asyncio
    async def test_filters_by_user_id(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_a = await _create_user(db_session, email="a@test.com")
        user_b = await _create_user(db_session, email="b@test.com")

        await chat_repo.create_session(user_id=user_a, conversation_id="conv-a1")
        await chat_repo.create_session(user_id=user_b, conversation_id="conv-b1")
        await chat_repo.create_session(user_id=user_a, conversation_id="conv-a2")

        rows = await chat_repo.find_sessions_by_user(user_id=user_a, limit=10)
        assert len(rows) == 2
        assert all(r.conversation_id.startswith("conv-a") for r in rows)

    @pytest.mark.asyncio
    async def test_order_by_updated_at_desc(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        ts1 = datetime(2026, 1, 1, tzinfo=UTC)
        ts2 = datetime(2026, 1, 2, tzinfo=UTC)
        ts3 = datetime(2026, 1, 3, tzinfo=UTC)

        await _create_session_with_ts(db_session, user_id, "old", ts1)
        await _create_session_with_ts(db_session, user_id, "mid", ts2)
        await _create_session_with_ts(db_session, user_id, "new", ts3)

        rows = await chat_repo.find_sessions_by_user(user_id=user_id, limit=10)
        assert [r.conversation_id for r in rows] == ["new", "mid", "old"]

    @pytest.mark.asyncio
    async def test_limit_respected(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        for i in range(5):
            ts = datetime(2026, 1, i + 1, tzinfo=UTC)
            await _create_session_with_ts(db_session, user_id, f"c-{i}", ts)

        rows = await chat_repo.find_sessions_by_user(user_id=user_id, limit=3)
        assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_cursor_filtering(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        ts1 = datetime(2026, 1, 1, tzinfo=UTC)
        ts2 = datetime(2026, 1, 2, tzinfo=UTC)
        ts3 = datetime(2026, 1, 3, tzinfo=UTC)

        await _create_session_with_ts(db_session, user_id, "c1", ts1)
        await _create_session_with_ts(db_session, user_id, "c2", ts2)
        s3 = await _create_session_with_ts(db_session, user_id, "c3", ts3)

        # Cursor points at s3 → should return c2, c1
        rows = await chat_repo.find_sessions_by_user(
            user_id=user_id,
            limit=10,
            cursor_updated_at=s3.updated_at,
            cursor_id=s3.id,
        )
        assert [r.conversation_id for r in rows] == ["c2", "c1"]

    @pytest.mark.asyncio
    async def test_same_updated_at_tiebreak_by_id_desc(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        same_ts = datetime(2026, 6, 15, tzinfo=UTC)

        s1 = await _create_session_with_ts(db_session, user_id, "tie-1", same_ts)
        s2 = await _create_session_with_ts(db_session, user_id, "tie-2", same_ts)

        # Without cursor: higher id first
        rows = await chat_repo.find_sessions_by_user(user_id=user_id, limit=10)
        assert rows[0].id > rows[1].id

        # Cursor at s2 → should return s1 only (same updated_at, lower id)
        rows = await chat_repo.find_sessions_by_user(
            user_id=user_id,
            limit=10,
            cursor_updated_at=s2.updated_at,
            cursor_id=s2.id,
        )
        assert len(rows) == 1
        assert rows[0].id == s1.id

    @pytest.mark.asyncio
    async def test_preview_from_last_human_message(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        session = await chat_repo.create_session(
            user_id=user_id, conversation_id="conv-preview"
        )
        await chat_repo.create_message(
            session_id=session.id, role="human", content="첫 번째 질문"
        )
        await chat_repo.create_message(
            session_id=session.id, role="ai", content="AI 응답"
        )
        await chat_repo.create_message(
            session_id=session.id, role="human", content="마지막 질문"
        )

        rows = await chat_repo.find_sessions_by_user(user_id=user_id, limit=10)
        assert len(rows) == 1
        assert rows[0].last_message_preview == "마지막 질문"

    @pytest.mark.asyncio
    async def test_preview_none_when_no_messages(
        self, chat_repo: ChatRepository, db_session: AsyncSession
    ) -> None:
        user_id = await _create_user(db_session)
        await chat_repo.create_session(user_id=user_id, conversation_id="conv-no-msg")

        rows = await chat_repo.find_sessions_by_user(user_id=user_id, limit=10)
        assert len(rows) == 1
        assert rows[0].last_message_preview is None
