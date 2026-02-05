"""Pytest configuration and fixtures."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for synchronous tests."""
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for async tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


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
        '[snippet: 오늘 서울 날씨는 맑고 기온은 15도입니다., '
        'title: 서울 날씨, link: https://weather.com/seoul]'
    )
