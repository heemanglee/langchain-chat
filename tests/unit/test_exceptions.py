"""Tests for custom exception classes."""

from app.core.exceptions import (
    AccountLockedError,
    AppException,
    AuthenticationError,
    AuthorizationError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenBlacklistedError,
    TokenExpiredError,
    UserAlreadyExistsError,
    UserNotFoundError,
)


class TestExceptions:
    """Verify exception status codes and messages."""

    def test_app_exception_defaults(self) -> None:
        exc = AppException(message="err", code="ERR")
        assert exc.status_code == 400
        assert exc.code == "ERR"

    def test_authentication_error(self) -> None:
        exc = AuthenticationError()
        assert exc.status_code == 401

    def test_token_expired_error(self) -> None:
        exc = TokenExpiredError()
        assert exc.status_code == 401
        assert exc.code == "TOKEN_EXPIRED"

    def test_token_blacklisted_error(self) -> None:
        exc = TokenBlacklistedError()
        assert exc.status_code == 401

    def test_invalid_token_error(self) -> None:
        exc = InvalidTokenError()
        assert exc.status_code == 401

    def test_invalid_credentials_error(self) -> None:
        exc = InvalidCredentialsError()
        assert exc.status_code == 401

    def test_authorization_error(self) -> None:
        exc = AuthorizationError()
        assert exc.status_code == 403

    def test_user_already_exists_error(self) -> None:
        exc = UserAlreadyExistsError()
        assert exc.status_code == 409

    def test_user_not_found_error(self) -> None:
        exc = UserNotFoundError()
        assert exc.status_code == 404

    def test_account_locked_error(self) -> None:
        exc = AccountLockedError()
        assert exc.status_code == 429
