"""Tests for authentication schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.auth_schema import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenPayload,
    TokenResponse,
)


class TestRegisterRequest:
    """Tests for RegisterRequest validation."""

    def test_valid_register(self) -> None:
        req = RegisterRequest(
            email="Test@Example.com",
            password="Test1234!",
            username="tester",
        )
        assert req.email == "test@example.com"

    def test_email_normalization(self) -> None:
        req = RegisterRequest(
            email="  USER@GMAIL.COM  ",
            password="Abc12345!",
            username="user",
        )
        assert req.email == "user@gmail.com"

    def test_password_too_short(self) -> None:
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="Ab1!", username="user")

    def test_password_missing_uppercase(self) -> None:
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="abcdefgh1!", username="user")

    def test_password_missing_lowercase(self) -> None:
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="ABCDEFGH1!", username="user")

    def test_password_missing_digit(self) -> None:
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="Abcdefgh!", username="user")

    def test_password_missing_special_char(self) -> None:
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="Abcdefgh1", username="user")

    def test_username_too_short(self) -> None:
        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="Test1234!", username="a")

    def test_invalid_email(self) -> None:
        with pytest.raises(ValidationError):
            RegisterRequest(email="not-an-email", password="Test1234!", username="user")


class TestLoginRequest:
    """Tests for LoginRequest."""

    def test_valid_login(self) -> None:
        req = LoginRequest(email="test@test.com", password="password123")
        assert req.email == "test@test.com"

    def test_email_normalization(self) -> None:
        req = LoginRequest(email="  USER@GMAIL.COM  ", password="password")
        assert req.email == "user@gmail.com"


class TestTokenResponse:
    """Tests for TokenResponse."""

    def test_frozen(self) -> None:
        resp = TokenResponse(access_token="a", refresh_token="b", expires_in=1800)
        with pytest.raises(ValidationError):
            resp.access_token = "c"  # type: ignore[misc]

    def test_default_token_type(self) -> None:
        resp = TokenResponse(access_token="a", refresh_token="b", expires_in=1800)
        assert resp.token_type == "bearer"


class TestRefreshRequest:
    """Tests for RefreshRequest."""

    def test_valid_refresh(self) -> None:
        req = RefreshRequest(refresh_token="some-token")
        assert req.refresh_token == "some-token"


class TestLogoutRequest:
    """Tests for LogoutRequest."""

    def test_optional_refresh_token(self) -> None:
        req = LogoutRequest()
        assert req.refresh_token is None

    def test_with_refresh_token(self) -> None:
        req = LogoutRequest(refresh_token="rt")
        assert req.refresh_token == "rt"


class TestMessageResponse:
    """Tests for MessageResponse."""

    def test_frozen(self) -> None:
        resp = MessageResponse(message="ok")
        assert resp.message == "ok"
        with pytest.raises(ValidationError):
            resp.message = "changed"  # type: ignore[misc]


class TestTokenPayload:
    """Tests for TokenPayload."""

    def test_create_payload(self) -> None:
        p = TokenPayload(
            sub="1", email="a@b.com", role="user", type="access", jti="abc", exp=99999
        )
        assert p.sub == "1"
        assert p.role == "user"
