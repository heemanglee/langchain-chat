"""Integration tests for chat router."""

from collections.abc import AsyncGenerator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.chat_router import get_agent_service
from app.core.database import get_async_session
from app.schemas.chat_schema import ChatResponse, StreamEvent
from app.services.agent_service import AgentService
from tests.conftest import make_auth_headers, override_get_async_session


@pytest.fixture
def mock_agent_service() -> MagicMock:
    """Create a mock AgentService."""
    mock = MagicMock(spec=AgentService)
    mock.chat = AsyncMock(
        return_value=ChatResponse(
            message="Hello! How can I help you?",
            conversation_id="test-conv-123",
            sources=[],
            created_at=datetime.now(),
        )
    )

    async def mock_stream_chat(request):
        yield StreamEvent(event="token", data="Hello")
        yield StreamEvent(event="token", data=" world")
        yield StreamEvent(event="done", data="test-conv-123")

    mock.stream_chat = mock_stream_chat
    return mock


@pytest.fixture
async def async_client_with_mock(
    mock_agent_service: MagicMock,
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with mocked AgentService and auth."""
    from app.main import app

    app.dependency_overrides[get_agent_service] = lambda: mock_agent_service
    app.dependency_overrides[get_async_session] = override_get_async_session
    headers = make_auth_headers(fake_redis)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=headers
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with auth."""
    from app.main import app

    app.dependency_overrides[get_async_session] = override_get_async_session
    headers = make_auth_headers(fake_redis)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=headers
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def unauthed_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client without auth (for public endpoints)."""
    from app.main import app

    app.dependency_overrides[get_async_session] = override_get_async_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


class TestChatEndpoint:
    """Tests for POST /api/v1/chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_success(
        self,
        async_client_with_mock: AsyncClient,
    ) -> None:
        """Test successful chat request."""
        response = await async_client_with_mock.post(
            "/api/v1/chat",
            json={"message": "Hello"},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "message" in data
        assert "conversation_id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_chat_with_conversation_id(
        self,
        async_client_with_mock: AsyncClient,
    ) -> None:
        """Test chat with existing conversation ID."""
        response = await async_client_with_mock.post(
            "/api/v1/chat",
            json={
                "message": "Continue our conversation",
                "conversation_id": "existing-conv",
            },
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_validation_error_empty_message(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test validation error for empty message."""
        response = await async_client.post(
            "/api/v1/chat",
            json={"message": ""},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_validation_error_message_too_long(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test validation error for message too long."""
        response = await async_client.post(
            "/api/v1/chat",
            json={"message": "a" * 4001},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_with_web_search_disabled(
        self,
        async_client_with_mock: AsyncClient,
    ) -> None:
        """Test chat with web search disabled."""
        response = await async_client_with_mock.post(
            "/api/v1/chat",
            json={
                "message": "Hello",
                "use_web_search": False,
            },
        )

        assert response.status_code == 200


class TestStreamChatEndpoint:
    """Tests for POST /api/v1/chat/stream endpoint."""

    @pytest.mark.asyncio
    async def test_stream_chat_returns_sse(
        self,
        async_client_with_mock: AsyncClient,
    ) -> None:
        """Test that stream_chat returns Server-Sent Events."""
        response = await async_client_with_mock.post(
            "/api/v1/chat/stream",
            json={"message": "Hello"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_stream_chat_event_format(
        self,
        async_client_with_mock: AsyncClient,
    ) -> None:
        """Test that stream events have correct format."""
        response = await async_client_with_mock.post(
            "/api/v1/chat/stream",
            json={"message": "Hello"},
        )

        content = response.text
        assert "data:" in content

    @pytest.mark.asyncio
    async def test_stream_chat_validation_error(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test validation error for stream chat."""
        response = await async_client.post(
            "/api/v1/chat/stream",
            json={"message": ""},
        )

        assert response.status_code == 422


class TestChatRouterIntegration:
    """Integration tests for chat router registration."""

    @pytest.mark.asyncio
    async def test_router_is_registered(
        self,
        unauthed_client: AsyncClient,
    ) -> None:
        """Test that chat router is registered on the app."""
        response = await unauthed_client.get("/openapi.json")
        assert response.status_code == 200

        openapi = response.json()
        paths = openapi.get("paths", {})

        assert "/api/v1/chat" in paths
        assert "/api/v1/chat/stream" in paths

    @pytest.mark.asyncio
    async def test_health_check_still_works(
        self,
        unauthed_client: AsyncClient,
    ) -> None:
        """Test that health check endpoint still works after router registration."""
        response = await unauthed_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["data"]["status"] == "healthy"
