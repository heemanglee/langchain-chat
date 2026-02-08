"""Integration tests for conversation router endpoints."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.user import User
from tests.conftest import make_auth_headers, test_session_factory


async def _seed_user(email: str = "conv@test.com") -> int:
    """Insert a user and return its id."""
    async with test_session_factory() as session:
        user = User(email=email, hashed_password="hashed", username=email.split("@")[0])
        session.add(user)
        await session.flush()
        await session.refresh(user)
        user_id = user.id
        await session.commit()
    return user_id


async def _seed_session(
    user_id: int,
    conversation_id: str,
    updated_at: datetime,
    title: str | None = None,
) -> int:
    """Insert a chat session with explicit updated_at."""
    async with test_session_factory() as session:
        cs = ChatSession(
            user_id=user_id,
            conversation_id=conversation_id,
            title=title,
            updated_at=updated_at,
        )
        session.add(cs)
        await session.flush()
        await session.refresh(cs)
        session_id = cs.id
        await session.commit()
    return session_id


async def _seed_message(
    session_id: int,
    role: str,
    content: str,
    tool_call_id: str | None = None,
    tool_name: str | None = None,
) -> int:
    """Insert a chat message and return its id."""
    async with test_session_factory() as session:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )
        session.add(msg)
        await session.flush()
        await session.refresh(msg)
        msg_id = msg.id
        await session.commit()
    return msg_id


class TestUnauthenticated:
    """Unauthenticated requests should be rejected."""

    @pytest.mark.asyncio
    async def test_returns_401_without_token(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/v1/conversations")
        assert resp.status_code == 401


class TestEmptyList:
    """Empty conversation list."""

    @pytest.mark.asyncio
    async def test_returns_empty(self, authed_client: AsyncClient) -> None:
        resp = await authed_client.get("/api/v1/conversations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["conversations"] == []
        assert body["data"]["has_next"] is False
        assert body["data"]["next_cursor"] is None


class TestListConversations:
    """Conversation list with data."""

    @pytest.mark.asyncio
    async def test_only_own_sessions(
        self, fake_redis: object, async_client: AsyncClient
    ) -> None:
        user_a = await _seed_user("a@test.com")
        user_b = await _seed_user("b@test.com")
        ts = datetime(2026, 1, 1, tzinfo=UTC)

        await _seed_session(user_a, "conv-a", ts)
        await _seed_session(user_b, "conv-b", ts)

        headers = make_auth_headers(fake_redis, user_id=user_a, email="a@test.com")
        resp = await async_client.get("/api/v1/conversations", headers=headers)
        assert resp.status_code == 200
        convs = resp.json()["data"]["conversations"]
        assert len(convs) == 1
        assert convs[0]["conversation_id"] == "conv-a"

    @pytest.mark.asyncio
    async def test_sorted_by_updated_at_desc(
        self, fake_redis: object, async_client: AsyncClient
    ) -> None:
        user_id = await _seed_user("sort@test.com")
        await _seed_session(user_id, "old", datetime(2026, 1, 1, tzinfo=UTC))
        await _seed_session(user_id, "mid", datetime(2026, 1, 2, tzinfo=UTC))
        await _seed_session(user_id, "new", datetime(2026, 1, 3, tzinfo=UTC))

        headers = make_auth_headers(fake_redis, user_id=user_id, email="sort@test.com")
        resp = await async_client.get("/api/v1/conversations", headers=headers)
        ids = [c["conversation_id"] for c in resp.json()["data"]["conversations"]]
        assert ids == ["new", "mid", "old"]

    @pytest.mark.asyncio
    async def test_pagination_flow(
        self, fake_redis: object, async_client: AsyncClient
    ) -> None:
        user_id = await _seed_user("page@test.com")
        for i in range(5):
            ts = datetime(2026, 1, i + 1, tzinfo=UTC)
            await _seed_session(user_id, f"p-{i}", ts)

        headers = make_auth_headers(fake_redis, user_id=user_id, email="page@test.com")

        # Page 1: limit=2
        resp = await async_client.get("/api/v1/conversations?limit=2", headers=headers)
        body = resp.json()["data"]
        assert len(body["conversations"]) == 2
        assert body["has_next"] is True
        cursor = body["next_cursor"]

        # Page 2
        resp = await async_client.get(
            f"/api/v1/conversations?limit=2&cursor={cursor}", headers=headers
        )
        body = resp.json()["data"]
        assert len(body["conversations"]) == 2
        assert body["has_next"] is True
        cursor = body["next_cursor"]

        # Page 3 (last)
        resp = await async_client.get(
            f"/api/v1/conversations?limit=2&cursor={cursor}", headers=headers
        )
        body = resp.json()["data"]
        assert len(body["conversations"]) == 1
        assert body["has_next"] is False
        assert body["next_cursor"] is None

    @pytest.mark.asyncio
    async def test_default_limit(
        self, fake_redis: object, async_client: AsyncClient
    ) -> None:
        user_id = await _seed_user("deflimit@test.com")
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        await _seed_session(user_id, "dl-1", ts)

        headers = make_auth_headers(
            fake_redis, user_id=user_id, email="deflimit@test.com"
        )
        resp = await async_client.get("/api/v1/conversations", headers=headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_preview_included(
        self, fake_redis: object, async_client: AsyncClient
    ) -> None:
        user_id = await _seed_user("preview@test.com")
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        session_id = await _seed_session(user_id, "conv-prev", ts, title="제목")
        await _seed_message(session_id, "human", "첫 번째 메시지")
        await _seed_message(session_id, "ai", "AI 응답")
        await _seed_message(session_id, "human", "마지막 메시지")

        headers = make_auth_headers(
            fake_redis, user_id=user_id, email="preview@test.com"
        )
        resp = await async_client.get("/api/v1/conversations", headers=headers)
        conv = resp.json()["data"]["conversations"][0]
        assert conv["title"] == "제목"
        assert conv["last_message_preview"] == "마지막 메시지"


class TestGetConversationMessages:
    """Tests for GET /api/v1/conversations/{conversation_id}/messages."""

    @pytest.mark.asyncio
    async def test_get_messages_success(
        self, fake_redis: object, async_client: AsyncClient
    ) -> None:
        user_id = await _seed_user("msg@test.com")
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        session_id = await _seed_session(user_id, "conv-msg", ts)
        await _seed_message(session_id, "human", "질문입니다")
        await _seed_message(
            session_id,
            "tool",
            "검색 결과",
            tool_call_id="call_1",
            tool_name="web_search",
        )
        await _seed_message(session_id, "ai", "AI 응답입니다")

        headers = make_auth_headers(fake_redis, user_id=user_id, email="msg@test.com")
        resp = await async_client.get(
            "/api/v1/conversations/conv-msg/messages", headers=headers
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["conversation_id"] == "conv-msg"
        assert len(body["messages"]) == 3
        assert body["messages"][0]["role"] == "human"
        assert body["messages"][1]["role"] == "tool"
        assert body["messages"][2]["role"] == "ai"

    @pytest.mark.asyncio
    async def test_get_messages_empty_conversation(
        self, fake_redis: object, async_client: AsyncClient
    ) -> None:
        user_id = await _seed_user("empty-msg@test.com")
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        await _seed_session(user_id, "conv-empty-msg", ts)

        headers = make_auth_headers(
            fake_redis, user_id=user_id, email="empty-msg@test.com"
        )
        resp = await async_client.get(
            "/api/v1/conversations/conv-empty-msg/messages", headers=headers
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["conversation_id"] == "conv-empty-msg"
        assert body["messages"] == []

    @pytest.mark.asyncio
    async def test_get_messages_not_found(
        self, fake_redis: object, async_client: AsyncClient
    ) -> None:
        user_id = await _seed_user("nf-msg@test.com")
        headers = make_auth_headers(
            fake_redis, user_id=user_id, email="nf-msg@test.com"
        )
        resp = await async_client.get(
            "/api/v1/conversations/non-existent/messages", headers=headers
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "SESSION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_messages_not_authorized(
        self, fake_redis: object, async_client: AsyncClient
    ) -> None:
        owner_id = await _seed_user("msg-owner@test.com")
        other_id = await _seed_user("msg-other@test.com")
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        session_id = await _seed_session(owner_id, "conv-msg-auth", ts)
        await _seed_message(session_id, "human", "비밀 메시지")

        headers = make_auth_headers(
            fake_redis, user_id=other_id, email="msg-other@test.com"
        )
        resp = await async_client.get(
            "/api/v1/conversations/conv-msg-auth/messages", headers=headers
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_get_messages_unauthenticated(
        self, async_client: AsyncClient
    ) -> None:
        resp = await async_client.get("/api/v1/conversations/any-conv/messages")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_messages_with_tool_fields(
        self, fake_redis: object, async_client: AsyncClient
    ) -> None:
        user_id = await _seed_user("tool-msg@test.com")
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        session_id = await _seed_session(user_id, "conv-tool-msg", ts)
        await _seed_message(
            session_id,
            "tool",
            "검색 결과 내용",
            tool_call_id="call_abc",
            tool_name="web_search",
        )

        headers = make_auth_headers(
            fake_redis, user_id=user_id, email="tool-msg@test.com"
        )
        resp = await async_client.get(
            "/api/v1/conversations/conv-tool-msg/messages", headers=headers
        )
        assert resp.status_code == 200
        msg = resp.json()["data"]["messages"][0]
        assert msg["tool_call_id"] == "call_abc"
        assert msg["tool_name"] == "web_search"


class TestUpdateTitle:
    """Tests for PATCH /api/v1/conversations/{conversation_id}/title."""

    @pytest.mark.asyncio
    async def test_update_title_success(
        self, fake_redis: object, async_client: AsyncClient
    ) -> None:
        user_id = await _seed_user("title@test.com")
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        await _seed_session(user_id, "conv-title-up", ts, title="기존 제목")

        headers = make_auth_headers(fake_redis, user_id=user_id, email="title@test.com")
        resp = await async_client.patch(
            "/api/v1/conversations/conv-title-up/title",
            json={"title": "새 제목"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Title updated"

    @pytest.mark.asyncio
    async def test_update_title_not_found(
        self, fake_redis: object, async_client: AsyncClient
    ) -> None:
        user_id = await _seed_user("nf@test.com")
        headers = make_auth_headers(fake_redis, user_id=user_id, email="nf@test.com")
        resp = await async_client.patch(
            "/api/v1/conversations/non-existent/title",
            json={"title": "새 제목"},
            headers=headers,
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "SESSION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_update_title_not_authorized(
        self, fake_redis: object, async_client: AsyncClient
    ) -> None:
        owner_id = await _seed_user("owner@test.com")
        other_id = await _seed_user("other@test.com")
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        await _seed_session(owner_id, "conv-auth-test", ts)

        headers = make_auth_headers(
            fake_redis, user_id=other_id, email="other@test.com"
        )
        resp = await async_client.patch(
            "/api/v1/conversations/conv-auth-test/title",
            json={"title": "새 제목"},
            headers=headers,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_update_title_validation_too_long(
        self, authed_client: AsyncClient
    ) -> None:
        resp = await authed_client.patch(
            "/api/v1/conversations/any-conv/title",
            json={"title": "a" * 21},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_title_validation_empty(
        self, authed_client: AsyncClient
    ) -> None:
        resp = await authed_client.patch(
            "/api/v1/conversations/any-conv/title",
            json={"title": ""},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_title_unauthenticated(
        self, async_client: AsyncClient
    ) -> None:
        resp = await async_client.patch(
            "/api/v1/conversations/any-conv/title",
            json={"title": "새 제목"},
        )
        assert resp.status_code == 401


class TestValidation:
    """Input validation."""

    @pytest.mark.asyncio
    async def test_invalid_cursor_returns_400(self, authed_client: AsyncClient) -> None:
        resp = await authed_client.get("/api/v1/conversations?cursor=not-valid!!!")
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_CURSOR"

    @pytest.mark.asyncio
    async def test_limit_below_min_returns_422(
        self, authed_client: AsyncClient
    ) -> None:
        resp = await authed_client.get("/api/v1/conversations?limit=0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_limit_above_max_returns_422(
        self, authed_client: AsyncClient
    ) -> None:
        resp = await authed_client.get("/api/v1/conversations?limit=101")
        assert resp.status_code == 422
