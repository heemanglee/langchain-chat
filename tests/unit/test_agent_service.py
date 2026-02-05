"""Unit tests for agent service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.schemas.chat_schema import ChatRequest, ChatResponse, StreamEvent
from app.services.agent_service import AgentService


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create a mock LLM."""
    mock = MagicMock()
    mock.bind_tools = MagicMock(return_value=mock)
    return mock


@pytest.fixture
def agent_service(mock_llm: MagicMock) -> AgentService:
    """Create an AgentService instance with mock LLM."""
    return AgentService(llm=mock_llm)


class TestAgentServiceInit:
    """Tests for AgentService initialization."""

    def test_agent_service_creates_with_llm(self, mock_llm: MagicMock) -> None:
        """Test that AgentService initializes with an LLM."""
        service = AgentService(llm=mock_llm)
        assert service._llm is mock_llm

    def test_agent_service_has_memory(self, agent_service: AgentService) -> None:
        """Test that AgentService has memory checkpointer."""
        assert agent_service._memory is not None

    def test_agent_service_has_tools(self, agent_service: AgentService) -> None:
        """Test that AgentService has tools configured."""
        assert agent_service._tools is not None
        assert len(agent_service._tools) > 0

    def test_agent_service_has_agent(self, agent_service: AgentService) -> None:
        """Test that AgentService creates a ReAct agent."""
        assert agent_service._agent is not None


class TestAgentServiceChat:
    """Tests for AgentService.chat method."""

    @pytest.mark.asyncio
    async def test_chat_returns_response(self, mock_llm: MagicMock) -> None:
        """Test that chat returns a ChatResponse."""
        with patch(
            "app.services.agent_service.create_react_agent"
        ) as mock_create_agent:
            mock_agent = MagicMock()
            mock_agent.ainvoke = AsyncMock(
                return_value={
                    "messages": [
                        HumanMessage(content="Hello"),
                        AIMessage(content="Hi there! How can I help you today?"),
                    ]
                }
            )
            mock_create_agent.return_value = mock_agent

            service = AgentService(llm=mock_llm)
            request = ChatRequest(message="Hello")

            response = await service.chat(request)

            assert isinstance(response, ChatResponse)
            assert response.message == "Hi there! How can I help you today?"
            assert response.conversation_id is not None

    @pytest.mark.asyncio
    async def test_chat_preserves_conversation_id(self, mock_llm: MagicMock) -> None:
        """Test that chat preserves provided conversation_id."""
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

            service = AgentService(llm=mock_llm)
            request = ChatRequest(
                message="Hello",
                conversation_id="existing-conv-123",
            )

            response = await service.chat(request)

            assert response.conversation_id == "existing-conv-123"

    @pytest.mark.asyncio
    async def test_chat_extracts_sources_from_tool_results(
        self,
        mock_llm: MagicMock,
    ) -> None:
        """Test that chat extracts sources from tool messages."""
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

            service = AgentService(llm=mock_llm)
            request = ChatRequest(message="Search for weather")

            response = await service.chat(request)

            assert "https://weather.com/seoul" in response.sources


class TestAgentServiceStreamChat:
    """Tests for AgentService.stream_chat method."""

    @pytest.mark.asyncio
    async def test_stream_chat_yields_events(self, mock_llm: MagicMock) -> None:
        """Test that stream_chat yields StreamEvent objects."""
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

            service = AgentService(llm=mock_llm)
            request = ChatRequest(message="Hello")

            events = []
            async for event in service.stream_chat(request):
                events.append(event)

            assert len(events) > 0
            assert all(isinstance(e, StreamEvent) for e in events)

    @pytest.mark.asyncio
    async def test_stream_chat_ends_with_done_event(
        self,
        mock_llm: MagicMock,
    ) -> None:
        """Test that stream_chat ends with a done event."""
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

            service = AgentService(llm=mock_llm)
            request = ChatRequest(message="Hello")

            events = []
            async for event in service.stream_chat(request):
                events.append(event)

            assert events[-1].event == "done"

    @pytest.mark.asyncio
    async def test_stream_chat_yields_token_events(
        self,
        mock_llm: MagicMock,
    ) -> None:
        """Test that stream_chat yields token events for LLM output."""
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

            service = AgentService(llm=mock_llm)
            request = ChatRequest(message="Hi")

            token_events = []
            async for event in service.stream_chat(request):
                if event.event == "token":
                    token_events.append(event)

            assert len(token_events) >= 1

    @pytest.mark.asyncio
    async def test_stream_chat_yields_tool_events(
        self,
        mock_llm: MagicMock,
    ) -> None:
        """Test that stream_chat yields tool call and result events."""
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
                    "data": {"output": "Search results..."},
                }

            mock_agent.astream_events = mock_astream_events
            mock_create_agent.return_value = mock_agent

            service = AgentService(llm=mock_llm)
            request = ChatRequest(message="Search test")

            tool_events = []
            async for event in service.stream_chat(request):
                if event.event in ("tool_call", "tool_result"):
                    tool_events.append(event)

            assert len(tool_events) >= 1
