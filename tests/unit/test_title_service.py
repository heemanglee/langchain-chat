"""Unit tests for TitleService."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from app.services.title_service import TitleService


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create a mock LLM for title generation."""
    mock = MagicMock(spec=BaseChatModel)
    mock.ainvoke = AsyncMock(return_value=AIMessage(content="날씨 질문"))
    return mock


class TestTitleService:
    """Tests for TitleService.generate_title."""

    @pytest.mark.asyncio
    async def test_generate_title_returns_short_string(
        self, mock_llm: MagicMock
    ) -> None:
        service = TitleService(mock_llm)
        title = await service.generate_title("오늘 서울 날씨 어때?")

        assert len(title) <= 10
        assert title == "날씨 질문"

    @pytest.mark.asyncio
    async def test_generate_title_truncates_long_response(
        self,
    ) -> None:
        mock = MagicMock(spec=BaseChatModel)
        mock.ainvoke = AsyncMock(
            return_value=AIMessage(content="이것은매우긴제목입니다열자초과")
        )

        service = TitleService(mock)
        title = await service.generate_title("test")

        assert len(title) <= 10

    @pytest.mark.asyncio
    async def test_generate_title_strips_whitespace(self) -> None:
        mock = MagicMock(spec=BaseChatModel)
        mock.ainvoke = AsyncMock(return_value=AIMessage(content="  제목  \n"))

        service = TitleService(mock)
        title = await service.generate_title("test")

        assert title == "제목"

    @pytest.mark.asyncio
    async def test_generate_title_calls_llm_with_prompt(
        self, mock_llm: MagicMock
    ) -> None:
        service = TitleService(mock_llm)
        await service.generate_title("Python이 뭐야?")

        mock_llm.ainvoke.assert_called_once()
        prompt_arg = mock_llm.ainvoke.call_args[0][0]
        assert "10자 이내" in prompt_arg
        assert "Python이 뭐야?" in prompt_arg
