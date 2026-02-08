"""Integration tests for GET /api/v1/conversations."""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.user import User
from tests.conftest import make_auth_headers, test_session_factory


async def _seed_user(email: str = "conv@test.com") -> int:
    """Insert a user and return its id."""
    async with test_session_factory() as session:
        user = User(
            email=email, hashed_password="hashed", username=email.split("@")[0]
        )
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


async def _seed_message(session_id: int, role: str, content: str) -> None:
    """Insert a chat message."""
    async with test_session_factory() as session:
        msg = ChatMessage(session_id=session_id, role=role, content=content)
        session.add(msg)
        await session.commit()


class TestUnauthenticated:
    """Unauthenticated requests should be rejected."""

    @pytest.mark.asyncio
    async def test_returns_401_without_token(
        self, async_client: AsyncClient
    ) -> None:
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
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)

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
        await _seed_session(user_id, "old", datetime(2026, 1, 1, tzinfo=timezone.utc))
        await _seed_session(user_id, "mid", datetime(2026, 1, 2, tzinfo=timezone.utc))
        await _seed_session(user_id, "new", datetime(2026, 1, 3, tzinfo=timezone.utc))

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
            ts = datetime(2026, 1, i + 1, tzinfo=timezone.utc)
            await _seed_session(user_id, f"p-{i}", ts)

        headers = make_auth_headers(fake_redis, user_id=user_id, email="page@test.com")

        # Page 1: limit=2
        resp = await async_client.get(
            "/api/v1/conversations?limit=2", headers=headers
        )
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
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
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
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
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


class TestValidation:
    """Input validation."""

    @pytest.mark.asyncio
    async def test_invalid_cursor_returns_400(
        self, authed_client: AsyncClient
    ) -> None:
        resp = await authed_client.get(
            "/api/v1/conversations?cursor=not-valid!!!"
        )
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
