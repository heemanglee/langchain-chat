"""Unit tests for web search tool."""

from unittest.mock import MagicMock, patch

from app.tools.web_search import web_search


class TestWebSearchTool:
    """Tests for web_search tool."""

    def test_web_search_is_tool(self) -> None:
        """Test that web_search is a LangChain tool."""
        assert hasattr(web_search, "invoke")
        assert hasattr(web_search, "name")
        assert web_search.name == "web_search"

    def test_web_search_has_description(self) -> None:
        """Test that web_search has a description."""
        assert web_search.description is not None
        assert len(web_search.description) > 0

    @patch("app.tools.web_search.DuckDuckGoSearchResults")
    def test_web_search_returns_results(
        self,
        mock_search_class: MagicMock,
    ) -> None:
        """Test that web_search returns search results."""
        mock_search_instance = MagicMock()
        mock_search_instance.invoke.return_value = (
            "[snippet: 오늘 서울 날씨는 맑음, title: 날씨, link: https://example.com]"
        )
        mock_search_class.return_value = mock_search_instance

        result = web_search.invoke("서울 날씨")

        assert "서울" in result or "날씨" in result or "example.com" in result
        mock_search_instance.invoke.assert_called_once_with("서울 날씨")

    @patch("app.tools.web_search.DuckDuckGoSearchResults")
    def test_web_search_handles_empty_query(
        self,
        mock_search_class: MagicMock,
    ) -> None:
        """Test web_search handles empty results gracefully."""
        mock_search_instance = MagicMock()
        mock_search_instance.invoke.return_value = "[]"
        mock_search_class.return_value = mock_search_instance

        result = web_search.invoke("asdfghjklqwerty")

        assert result is not None

    @patch("app.tools.web_search.DuckDuckGoSearchResults")
    def test_web_search_called_with_num_results(
        self,
        mock_search_class: MagicMock,
    ) -> None:
        """Test that DuckDuckGoSearchResults is created with num_results=5."""
        mock_search_instance = MagicMock()
        mock_search_instance.invoke.return_value = "[]"
        mock_search_class.return_value = mock_search_instance

        web_search.invoke("test query")

        mock_search_class.assert_called_once_with(num_results=5)
