"""Unit tests for conversation_schema.py."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.conversation_schema import (
    ConversationListResponse,
    ConversationSummary,
)


class TestConversationSummary:
    """Tests for ConversationSummary schema."""

    def test_from_attributes(self) -> None:
        class FakeRow:
            conversation_id = "abc-123"
            title = "서울 날씨"
            last_message_preview = "오늘 날씨 어때?"
            created_at = datetime(2026, 1, 1, tzinfo=UTC)
            updated_at = datetime(2026, 1, 2, tzinfo=UTC)

        summary = ConversationSummary.model_validate(FakeRow())
        assert summary.conversation_id == "abc-123"
        assert summary.title == "서울 날씨"
        assert summary.last_message_preview == "오늘 날씨 어때?"

    def test_defaults(self) -> None:
        summary = ConversationSummary(
            conversation_id="x",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert summary.title is None
        assert summary.last_message_preview is None

    def test_frozen(self) -> None:
        summary = ConversationSummary(
            conversation_id="x",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        with pytest.raises(ValidationError):
            summary.title = "changed"  # type: ignore[misc]


class TestConversationListResponse:
    """Tests for ConversationListResponse schema."""

    def test_empty_list(self) -> None:
        resp = ConversationListResponse(conversations=[])
        assert resp.conversations == []
        assert resp.next_cursor is None
        assert resp.has_next is False

    def test_with_cursor(self) -> None:
        summary = ConversationSummary(
            conversation_id="a",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        resp = ConversationListResponse(
            conversations=[summary],
            next_cursor="abc123",
            has_next=True,
        )
        assert resp.has_next is True
        assert resp.next_cursor == "abc123"
        assert len(resp.conversations) == 1

    def test_frozen(self) -> None:
        resp = ConversationListResponse(conversations=[])
        with pytest.raises(ValidationError):
            resp.has_next = True  # type: ignore[misc]
