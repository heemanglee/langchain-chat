"""Pytest configuration and fixtures."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base
from app.models.chat_message import ChatMessage  # noqa: F401
from app.models.chat_session import ChatSession  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services.token_service import TokenService

# --- Test DB (SQLite in-memory) ---

test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(autouse=True)
async def setup_db() -> AsyncGenerator[None, None]:
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# --- Test Redis (fakeredis) ---


@pytest.fixture
def fake_redis() -> fakeredis.aioredis.FakeRedis:
    """Create a fresh fake Redis client."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def patch_redis(
    fake_redis: fakeredis.aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Patch the global redis_client for middleware and get_redis()."""
    monkeypatch.setattr("app.core.redis.redis_client", fake_redis)
    monkeypatch.setattr("app.core.middleware.redis_client", fake_redis)


# --- Token helpers ---


@pytest.fixture
def token_service(fake_redis: fakeredis.aioredis.FakeRedis) -> TokenService:
    """Create a TokenService backed by fake Redis."""
    return TokenService(fake_redis)


def make_auth_headers(
    fake_redis: fakeredis.aioredis.FakeRedis,
    user_id: int = 1,
    email: str = "test@test.com",
    role: str = "user",
) -> dict[str, str]:
    """Generate Authorization headers with a valid access token."""
    ts = TokenService(fake_redis)
    token = ts.create_access_token(user_id=user_id, email=email, role=role)
    return {"Authorization": f"Bearer {token}"}


# --- App override & client fixtures ---


def _get_app():  # type: ignore[no-untyped-def]
    """Import app lazily and apply overrides."""
    from app.core.database import get_async_session as original_dep
    from app.main import app

    app.dependency_overrides[original_dep] = override_get_async_session
    return app


@pytest.fixture
async def async_client(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for async tests."""
    application = _get_app()
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def authed_client(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with auth headers."""
    application = _get_app()
    headers = make_auth_headers(fake_redis)
    transport = ASGITransport(app=application)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=headers
    ) as ac:
        yield ac


@pytest.fixture
async def admin_client(
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with admin auth headers."""
    application = _get_app()
    headers = make_auth_headers(fake_redis, role="admin")
    transport = ASGITransport(app=application)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=headers
    ) as ac:
        yield ac


# --- DB session for tests ---


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a raw async session for repository tests."""
    async with test_session_factory() as session:
        yield session


# --- Mock LLM ---


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create a mock LLM for testing."""
    mock = MagicMock(spec=BaseChatModel)
    mock.ainvoke = AsyncMock(return_value=AIMessage(content="Test response"))
    mock.astream = AsyncMock()
    return mock


@pytest.fixture
def mock_web_search_result() -> str:
    """Mock web search result for testing."""
    return (
        "[snippet: 오늘 서울 날씨는 맑고 기온은 15도입니다., "
        "title: 서울 날씨, link: https://weather.com/seoul]"
    )
