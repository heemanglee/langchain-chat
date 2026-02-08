"""Unit tests for ConversationService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import AppException
from app.repositories.chat_repo import ChatRepository, SessionWithPreview
from app.services.conversation_service import (
    ConversationService,
    decode_cursor,
    encode_cursor,
)


def _make_preview(
    session_id: int,
    conversation_id: str,
    updated_at: datetime,
    title: str | None = None,
    preview: str | None = None,
) -> SessionWithPreview:
    return SessionWithPreview(
        id=session_id,
        conversation_id=conversation_id,
        title=title,
        last_message_preview=preview,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=updated_at,
    )


class TestCursorEncoding:
    """Tests for encode_cursor / decode_cursor round-trip."""

    def test_roundtrip(self) -> None:
        ts = datetime(2026, 2, 8, 14, 30, 0, tzinfo=timezone.utc)
        cursor = encode_cursor(ts, 42)
        decoded_ts, decoded_id = decode_cursor(cursor)
        assert decoded_ts == ts
        assert decoded_id == 42

    def test_invalid_cursor_raises(self) -> None:
        with pytest.raises(AppException) as exc_info:
            decode_cursor("not-valid-base64!!!")
        assert exc_info.value.code == "INVALID_CURSOR"
        assert exc_info.value.status_code == 400

    def test_missing_fields_raises(self) -> None:
        import base64
        import json

        bad = base64.urlsafe_b64encode(json.dumps({"x": 1}).encode()).decode()
        with pytest.raises(AppException) as exc_info:
            decode_cursor(bad)
        assert exc_info.value.code == "INVALID_CURSOR"


class TestConversationService:
    """Tests for ConversationService.list_conversations."""

    @pytest.fixture
    def mock_repo(self) -> ChatRepository:
        repo = AsyncMock(spec=ChatRepository)
        return repo

    @pytest.fixture
    def service(self, mock_repo: ChatRepository) -> ConversationService:
        return ConversationService(chat_repo=mock_repo, user_id=1)

    @pytest.mark.asyncio
    async def test_empty_list(
        self, service: ConversationService, mock_repo: AsyncMock
    ) -> None:
        mock_repo.find_sessions_by_user.return_value = []
        result = await service.list_conversations(limit=20)

        assert result.conversations == []
        assert result.has_next is False
        assert result.next_cursor is None

    @pytest.mark.asyncio
    async def test_single_page_no_next(
        self, service: ConversationService, mock_repo: AsyncMock
    ) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = [_make_preview(1, "c1", ts)]
        mock_repo.find_sessions_by_user.return_value = rows

        result = await service.list_conversations(limit=20)

        assert len(result.conversations) == 1
        assert result.has_next is False
        assert result.next_cursor is None

    @pytest.mark.asyncio
    async def test_has_next_page(
        self, service: ConversationService, mock_repo: AsyncMock
    ) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # limit=2 → service requests 3 rows. Return 3 means has_next=True
        rows = [
            _make_preview(3, "c3", ts),
            _make_preview(2, "c2", ts),
            _make_preview(1, "c1", ts),
        ]
        mock_repo.find_sessions_by_user.return_value = rows

        result = await service.list_conversations(limit=2)

        assert len(result.conversations) == 2
        assert result.has_next is True
        assert result.next_cursor is not None

        # Verify cursor encodes last returned row
        decoded_ts, decoded_id = decode_cursor(result.next_cursor)
        assert decoded_id == 2

    @pytest.mark.asyncio
    async def test_cursor_passed_to_repo(
        self, service: ConversationService, mock_repo: AsyncMock
    ) -> None:
        ts = datetime(2026, 2, 8, 14, 30, 0, tzinfo=timezone.utc)
        cursor = encode_cursor(ts, 42)
        mock_repo.find_sessions_by_user.return_value = []

        await service.list_conversations(limit=20, cursor=cursor)

        mock_repo.find_sessions_by_user.assert_called_once_with(
            user_id=1,
            limit=21,
            cursor_updated_at=ts,
            cursor_id=42,
        )

    @pytest.mark.asyncio
    async def test_preview_forwarded(
        self, service: ConversationService, mock_repo: AsyncMock
    ) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = [_make_preview(1, "c1", ts, preview="안녕하세요")]
        mock_repo.find_sessions_by_user.return_value = rows

        result = await service.list_conversations(limit=20)
        assert result.conversations[0].last_message_preview == "안녕하세요"
