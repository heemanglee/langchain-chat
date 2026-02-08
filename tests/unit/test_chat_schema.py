"""Unit tests for chat schemas."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.chat_schema import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EditMessageRequest,
    RegenerateRequest,
    StreamEvent,
)


class TestChatMessage:
    """Tests for ChatMessage schema."""

    def test_valid_user_message(self) -> None:
        """Test creating a valid user message."""
        message = ChatMessage(role="user", content="Hello")
        assert message.role == "user"
        assert message.content == "Hello"

    def test_valid_assistant_message(self) -> None:
        """Test creating a valid assistant message."""
        message = ChatMessage(role="assistant", content="Hi there!")
        assert message.role == "assistant"
        assert message.content == "Hi there!"

    def test_valid_system_message(self) -> None:
        """Test creating a valid system message."""
        message = ChatMessage(role="system", content="You are a helpful assistant.")
        assert message.role == "system"

    def test_invalid_role(self) -> None:
        """Test that invalid role raises ValidationError."""
        with pytest.raises(ValidationError):
            ChatMessage(role="invalid", content="Hello")


class TestChatRequest:
    """Tests for ChatRequest schema."""

    def test_valid_request_minimal(self) -> None:
        """Test creating a valid request with minimal fields."""
        request = ChatRequest(message="Hello")
        assert request.message == "Hello"
        assert request.conversation_id is None
        assert request.use_web_search is True

    def test_valid_request_full(self) -> None:
        """Test creating a valid request with all fields."""
        request = ChatRequest(
            message="What's the weather?",
            conversation_id="test-conversation-123",
            use_web_search=False,
        )
        assert request.message == "What's the weather?"
        assert request.conversation_id == "test-conversation-123"
        assert request.use_web_search is False

    def test_empty_message_fails(self) -> None:
        """Test that empty message raises ValidationError."""
        with pytest.raises(ValidationError):
            ChatRequest(message="")

    def test_message_too_long_fails(self) -> None:
        """Test that message over 4000 chars raises ValidationError."""
        long_message = "a" * 4001
        with pytest.raises(ValidationError):
            ChatRequest(message=long_message)

    def test_message_at_max_length_succeeds(self) -> None:
        """Test that message at exactly 4000 chars succeeds."""
        max_message = "a" * 4000
        request = ChatRequest(message=max_message)
        assert len(request.message) == 4000


class TestChatResponse:
    """Tests for ChatResponse schema."""

    def test_valid_response(self) -> None:
        """Test creating a valid response."""
        now = datetime.now()
        response = ChatResponse(
            message="Hello! How can I help?",
            conversation_id="test-123",
            session_id=1,
            sources=["https://example.com"],
            created_at=now,
        )
        assert response.message == "Hello! How can I help?"
        assert response.conversation_id == "test-123"
        assert response.session_id == 1
        assert response.sources == ["https://example.com"]
        assert response.created_at == now

    def test_response_empty_sources(self) -> None:
        """Test response with empty sources list."""
        response = ChatResponse(
            message="Hello!",
            conversation_id="test-123",
            session_id=1,
            sources=[],
            created_at=datetime.now(),
        )
        assert response.sources == []

    def test_response_default_sources(self) -> None:
        """Test response with default sources list."""
        response = ChatResponse(
            message="Hello!",
            conversation_id="test-123",
            session_id=1,
            created_at=datetime.now(),
        )
        assert response.sources == []


class TestRegenerateRequest:
    """Tests for RegenerateRequest schema."""

    def test_valid_request(self) -> None:
        request = RegenerateRequest(message_id=5, conversation_id="conv-123")
        assert request.message_id == 5
        assert request.conversation_id == "conv-123"

    def test_empty_conversation_id_fails(self) -> None:
        with pytest.raises(ValidationError):
            RegenerateRequest(message_id=5, conversation_id="")

    def test_missing_message_id_fails(self) -> None:
        with pytest.raises(ValidationError):
            RegenerateRequest(conversation_id="conv-123")  # type: ignore[call-arg]

    def test_missing_conversation_id_fails(self) -> None:
        with pytest.raises(ValidationError):
            RegenerateRequest(message_id=5)  # type: ignore[call-arg]


class TestEditMessageRequest:
    """Tests for EditMessageRequest schema."""

    def test_valid_request(self) -> None:
        request = EditMessageRequest(
            message_id=3,
            conversation_id="conv-456",
            message="Updated question",
        )
        assert request.message_id == 3
        assert request.conversation_id == "conv-456"
        assert request.message == "Updated question"

    def test_empty_message_fails(self) -> None:
        with pytest.raises(ValidationError):
            EditMessageRequest(
                message_id=3,
                conversation_id="conv-456",
                message="",
            )

    def test_message_too_long_fails(self) -> None:
        with pytest.raises(ValidationError):
            EditMessageRequest(
                message_id=3,
                conversation_id="conv-456",
                message="a" * 4001,
            )

    def test_message_at_max_length_succeeds(self) -> None:
        request = EditMessageRequest(
            message_id=3,
            conversation_id="conv-456",
            message="a" * 4000,
        )
        assert len(request.message) == 4000

    def test_empty_conversation_id_fails(self) -> None:
        with pytest.raises(ValidationError):
            EditMessageRequest(
                message_id=3,
                conversation_id="",
                message="Hello",
            )

    def test_missing_fields_fails(self) -> None:
        with pytest.raises(ValidationError):
            EditMessageRequest(message_id=3)  # type: ignore[call-arg]


class TestStreamEvent:
    """Tests for StreamEvent schema."""

    def test_token_event(self) -> None:
        """Test creating a token event."""
        event = StreamEvent(event="token", data="Hello")
        assert event.event == "token"
        assert event.data == "Hello"

    def test_tool_call_event(self) -> None:
        """Test creating a tool_call event."""
        event = StreamEvent(
            event="tool_call",
            data='web_search: {"query": "서울 날씨"}',
        )
        assert event.event == "tool_call"

    def test_tool_result_event(self) -> None:
        """Test creating a tool_result event."""
        event = StreamEvent(event="tool_result", data="오늘 서울은 맑음, 15도")
        assert event.event == "tool_result"

    def test_done_event(self) -> None:
        """Test creating a done event."""
        event = StreamEvent(event="done", data="conversation-id-123")
        assert event.event == "done"

    def test_error_event(self) -> None:
        """Test creating an error event."""
        event = StreamEvent(event="error", data="An error occurred")
        assert event.event == "error"

    def test_invalid_event_type(self) -> None:
        """Test that invalid event type raises ValidationError."""
        with pytest.raises(ValidationError):
            StreamEvent(event="invalid", data="test")
