"""Unit tests for agent service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.models.chat_message import ChatMessage
from app.repositories.chat_repo import ChatRepository
from app.schemas.chat_schema import ChatRequest, ChatResponse, StreamEvent
from app.services.agent_service import AgentService


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create a mock LLM."""
    mock = MagicMock()
    mock.bind_tools = MagicMock(return_value=mock)
    return mock


@pytest.fixture
def mock_chat_repo() -> MagicMock:
    """Create a mock ChatRepository."""
    mock = MagicMock(spec=ChatRepository)
    mock.find_session_by_conversation_id = AsyncMock(return_value=None)

    session_mock = MagicMock()
    session_mock.id = 1
    mock.create_session = AsyncMock(return_value=session_mock)
    mock.find_messages_by_session_id = AsyncMock(return_value=[])
    mock.create_messages_bulk = AsyncMock()
    return mock


@pytest.fixture
def agent_service(mock_llm: MagicMock, mock_chat_repo: MagicMock) -> AgentService:
    """Create an AgentService instance with mock dependencies."""
    return AgentService(llm=mock_llm, chat_repo=mock_chat_repo, user_id=1)


class TestAgentServiceInit:
    """Tests for AgentService initialization."""

    def test_agent_service_creates_with_dependencies(
        self, mock_llm: MagicMock, mock_chat_repo: MagicMock
    ) -> None:
        service = AgentService(llm=mock_llm, chat_repo=mock_chat_repo, user_id=42)
        assert service._llm is mock_llm
        assert service._chat_repo is mock_chat_repo
        assert service._user_id == 42

    def test_agent_service_has_memory(self, agent_service: AgentService) -> None:
        assert agent_service._memory is not None

    def test_agent_service_has_tools(self, agent_service: AgentService) -> None:
        assert agent_service._tools is not None
        assert len(agent_service._tools) > 0

    def test_agent_service_has_agent(self, agent_service: AgentService) -> None:
        assert agent_service._agent is not None


class TestAgentServiceChat:
    """Tests for AgentService.chat method."""

    @pytest.mark.asyncio
    async def test_chat_returns_response_and_is_new_flag(
        self, mock_llm: MagicMock, mock_chat_repo: MagicMock
    ) -> None:
        with patch(
            "app.services.agent_service.create_react_agent"
        ) as mock_create_agent:
            mock_agent = MagicMock()
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "messages": [
                        HumanMessage(content="Hello"),
                        AIMessage(content="Hi there!"),
                    ]
                }
            )
            mock_create_agent.return_value = mock_agent

            service = AgentService(llm=mock_llm, chat_repo=mock_chat_repo, user_id=1)
            request = ChatRequest(message="Hello")

            response, is_new = await service.chat(request)

            assert isinstance(response, ChatResponse)
            assert response.message == "Hi there!"
            assert response.conversation_id is not None
            assert response.session_id == 1
            assert is_new is True

    @pytest.mark.asyncio
    async def test_chat_preserves_conversation_id(
        self, mock_llm: MagicMock, mock_chat_repo: MagicMock
    ) -> None:
        with patch(
            "app.services.agent_service.create_react_agent"
        ) as mock_create_agent:
            mock_agent = MagicMock()
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "messages": [
                        HumanMessage(content="Hello"),
                        AIMessage(content="Hi!"),
                    ]
                }
            )
            mock_create_agent.return_value = mock_agent

            service = AgentService(llm=mock_llm, chat_repo=mock_chat_repo, user_id=1)
            request = ChatRequest(
                message="Hello",
                conversation_id="existing-conv-123",
            )

            response, _ = await service.chat(request)

            assert response.conversation_id == "existing-conv-123"

    @pytest.mark.asyncio
    async def test_chat_extracts_sources_from_tool_results(
        self, mock_llm: MagicMock, mock_chat_repo: MagicMock
    ) -> None:
        with patch(
            "app.services.agent_service.create_react_agent"
        ) as mock_create_agent:
            mock_agent = MagicMock()
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "messages": [
                        HumanMessage(content="Search for weather"),
                        ToolMessage(
                            content="[link: https://weather.com/seoul]",
                            tool_call_id="call_1",
                        ),
                        AIMessage(content="The weather is sunny."),
                    ]
                }
            )
            mock_create_agent.return_value = mock_agent

            service = AgentService(llm=mock_llm, chat_repo=mock_chat_repo, user_id=1)
            request = ChatRequest(message="Search for weather")

            response, _ = await service.chat(request)

            assert "https://weather.com/seoul" in response.sources

    @pytest.mark.asyncio
    async def test_chat_saves_messages_to_db(
        self, mock_llm: MagicMock, mock_chat_repo: MagicMock
    ) -> None:
        with patch(
            "app.services.agent_service.create_react_agent"
        ) as mock_create_agent:
            mock_agent = MagicMock()
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "messages": [
                        HumanMessage(content="Hello"),
                        AIMessage(content="Hi!"),
                    ]
                }
            )
            mock_create_agent.return_value = mock_agent

            service = AgentService(llm=mock_llm, chat_repo=mock_chat_repo, user_id=1)
            request = ChatRequest(message="Hello")
            await service.chat(request)

            mock_chat_repo.create_messages_bulk.assert_called_once()


class TestAgentServiceStreamChat:
    """Tests for AgentService.stream_chat method."""

    @pytest.mark.asyncio
    async def test_stream_chat_yields_events(
        self, mock_llm: MagicMock, mock_chat_repo: MagicMock
    ) -> None:
        with patch(
            "app.services.agent_service.create_react_agent"
        ) as mock_create_agent:
            mock_agent = MagicMock()

            async def mock_astream_events(*args, **kwargs):
                yield {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": AIMessage(content="Hello")},
                }
                yield {
                    "event": "on_chat_model_end",
                    "data": {"output": AIMessage(content="Hello")},
                }

            mock_agent.astream_events = mock_astream_events
            mock_create_agent.return_value = mock_agent

            service = AgentService(llm=mock_llm, chat_repo=mock_chat_repo, user_id=1)
            request = ChatRequest(message="Hello")

            events = []
            async for event in service.stream_chat(request):
                events.append(event)

            assert len(events) > 0
            assert all(isinstance(e, StreamEvent) for e in events)

    @pytest.mark.asyncio
    async def test_stream_chat_ends_with_done_event(
        self, mock_llm: MagicMock, mock_chat_repo: MagicMock
    ) -> None:
        with patch(
            "app.services.agent_service.create_react_agent"
        ) as mock_create_agent:
            mock_agent = MagicMock()

            async def mock_astream_events(*args, **kwargs):
                yield {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": AIMessage(content="Hi")},
                }

            mock_agent.astream_events = mock_astream_events
            mock_create_agent.return_value = mock_agent

            service = AgentService(llm=mock_llm, chat_repo=mock_chat_repo, user_id=1)
            request = ChatRequest(message="Hello")

            events = []
            async for event in service.stream_chat(request):
                events.append(event)

            assert events[-1].event == "done"

    @pytest.mark.asyncio
    async def test_stream_chat_yields_token_events(
        self, mock_llm: MagicMock, mock_chat_repo: MagicMock
    ) -> None:
        with patch(
            "app.services.agent_service.create_react_agent"
        ) as mock_create_agent:
            mock_agent = MagicMock()

            async def mock_astream_events(*args, **kwargs):
                yield {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": AIMessage(content="Hello")},
                }
                yield {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": AIMessage(content=" world")},
                }

            mock_agent.astream_events = mock_astream_events
            mock_create_agent.return_value = mock_agent

            service = AgentService(llm=mock_llm, chat_repo=mock_chat_repo, user_id=1)
            request = ChatRequest(message="Hi")

            token_events = []
            async for event in service.stream_chat(request):
                if event.event == "token":
                    token_events.append(event)

            assert len(token_events) >= 1

    @pytest.mark.asyncio
    async def test_stream_chat_yields_tool_events(
        self, mock_llm: MagicMock, mock_chat_repo: MagicMock
    ) -> None:
        with patch(
            "app.services.agent_service.create_react_agent"
        ) as mock_create_agent:
            mock_agent = MagicMock()

            async def mock_astream_events(*args, **kwargs):
                yield {
                    "event": "on_tool_start",
                    "name": "web_search",
                    "data": {"input": {"query": "test"}},
                }
                yield {
                    "event": "on_tool_end",
                    "name": "web_search",
                    "run_id": "run_1",
                    "data": {"output": "Search results..."},
                }

            mock_agent.astream_events = mock_astream_events
            mock_create_agent.return_value = mock_agent

            service = AgentService(llm=mock_llm, chat_repo=mock_chat_repo, user_id=1)
            request = ChatRequest(message="Search test")

            tool_events = []
            async for event in service.stream_chat(request):
                if event.event in ("tool_call", "tool_result"):
                    tool_events.append(event)

            assert len(tool_events) >= 1

    @pytest.mark.asyncio
    async def test_stream_chat_saves_messages_to_db(
        self, mock_llm: MagicMock, mock_chat_repo: MagicMock
    ) -> None:
        with patch(
            "app.services.agent_service.create_react_agent"
        ) as mock_create_agent:
            mock_agent = MagicMock()

            async def mock_astream_events(*args, **kwargs):
                yield {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": AIMessage(content="Done")},
                }

            mock_agent.astream_events = mock_astream_events
            mock_create_agent.return_value = mock_agent

            service = AgentService(llm=mock_llm, chat_repo=mock_chat_repo, user_id=1)
            request = ChatRequest(message="Hello")

            async for _ in service.stream_chat(request):
                pass

            mock_chat_repo.create_messages_bulk.assert_called_once()


class TestBuildLangchainMessages:
    """Tests for AgentService._build_langchain_messages static method."""

    def test_build_human_message(self) -> None:
        db_msg = ChatMessage(id=1, session_id=1, role="human", content="Hello")
        result = AgentService._build_langchain_messages([db_msg])

        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "Hello"

    def test_build_ai_message_without_tool_calls(self) -> None:
        db_msg = ChatMessage(id=2, session_id=1, role="ai", content="Hi there!")
        result = AgentService._build_langchain_messages([db_msg])

        assert len(result) == 1
        assert isinstance(result[0], AIMessage)
        assert result[0].content == "Hi there!"
        assert result[0].tool_calls == []

    def test_build_ai_message_with_tool_calls(self) -> None:
        tool_calls = [{"name": "web_search", "args": {"query": "test"}, "id": "call_1"}]
        db_msg = ChatMessage(
            id=3,
            session_id=1,
            role="ai",
            content="",
            tool_calls_json=json.dumps(tool_calls),
        )
        result = AgentService._build_langchain_messages([db_msg])

        assert len(result) == 1
        assert isinstance(result[0], AIMessage)
        assert len(result[0].tool_calls) == 1
        assert result[0].tool_calls[0]["name"] == "web_search"
        assert result[0].tool_calls[0]["args"] == {"query": "test"}
        assert result[0].tool_calls[0]["id"] == "call_1"

    def test_build_system_message(self) -> None:
        db_msg = ChatMessage(
            id=4, session_id=1, role="system", content="You are helpful."
        )
        result = AgentService._build_langchain_messages([db_msg])

        assert len(result) == 1
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == "You are helpful."

    def test_build_tool_message(self) -> None:
        db_msg = ChatMessage(
            id=5,
            session_id=1,
            role="tool",
            content="Search result",
            tool_call_id="call_1",
            tool_name="web_search",
        )
        result = AgentService._build_langchain_messages([db_msg])

        assert len(result) == 1
        assert isinstance(result[0], ToolMessage)
        assert result[0].content == "Search result"
        assert result[0].tool_call_id == "call_1"
        assert result[0].name == "web_search"

    def test_build_multiple_messages_preserves_order(self) -> None:
        db_messages = [
            ChatMessage(id=1, session_id=1, role="human", content="Q1"),
            ChatMessage(id=2, session_id=1, role="ai", content="A1"),
            ChatMessage(id=3, session_id=1, role="human", content="Q2"),
        ]
        result = AgentService._build_langchain_messages(db_messages)

        assert len(result) == 3
        assert isinstance(result[0], HumanMessage)
        assert isinstance(result[1], AIMessage)
        assert isinstance(result[2], HumanMessage)


class TestExtractNewMessages:
    """Tests for AgentService._extract_new_messages static method."""

    def test_extract_ai_message(self) -> None:
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi!"),
        ]
        result = AgentService._extract_new_messages(messages, history_len=0)

        assert len(result) == 1
        assert result[0]["role"] == "ai"
        assert result[0]["content"] == "Hi!"

    def test_extract_ai_with_tool_calls(self) -> None:
        ai_msg = AIMessage(
            content="",
            tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "c1"}],
        )
        messages = [HumanMessage(content="Search"), ai_msg]
        result = AgentService._extract_new_messages(messages, history_len=0)

        assert len(result) == 1
        assert "tool_calls_json" in result[0]

    def test_extract_tool_message(self) -> None:
        messages = [
            HumanMessage(content="Search"),
            ToolMessage(content="Results", tool_call_id="c1", name="search"),
            AIMessage(content="Here you go"),
        ]
        result = AgentService._extract_new_messages(messages, history_len=0)

        assert len(result) == 2
        assert result[0]["role"] == "tool"
        assert result[0]["tool_call_id"] == "c1"
        assert result[1]["role"] == "ai"

    def test_extract_skips_history(self) -> None:
        messages = [
            HumanMessage(content="Old Q"),
            AIMessage(content="Old A"),
            HumanMessage(content="New Q"),
            AIMessage(content="New A"),
        ]
        result = AgentService._extract_new_messages(messages, history_len=2)

        assert len(result) == 1
        assert result[0]["content"] == "New A"
