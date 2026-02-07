"""Application exception classes and handlers."""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, code: str, status_code: int = 400) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


# --- Authentication (401) ---


class AuthenticationError(AppException):
    """Base authentication error."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message=message, code="AUTHENTICATION_ERROR", status_code=401)


class TokenExpiredError(AppException):
    """Token has expired."""

    def __init__(self) -> None:
        super().__init__(
            message="Token has expired",
            code="TOKEN_EXPIRED",
            status_code=401,
        )


class TokenBlacklistedError(AppException):
    """Token has been revoked."""

    def __init__(self) -> None:
        super().__init__(
            message="Token has been revoked",
            code="TOKEN_BLACKLISTED",
            status_code=401,
        )


class InvalidTokenError(AppException):
    """Token is invalid."""

    def __init__(self) -> None:
        super().__init__(
            message="Invalid token",
            code="INVALID_TOKEN",
            status_code=401,
        )


class InvalidCredentialsError(AppException):
    """Invalid email or password."""

    def __init__(self) -> None:
        super().__init__(
            message="Invalid email or password",
            code="INVALID_CREDENTIALS",
            status_code=401,
        )


# --- Authorization (403) ---


class AuthorizationError(AppException):
    """Insufficient permissions."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message=message, code="AUTHORIZATION_ERROR", status_code=403)


# --- Conflict (409) ---


class UserAlreadyExistsError(AppException):
    """User with this email already exists."""

    def __init__(self) -> None:
        super().__init__(
            message="User with this email already exists",
            code="USER_ALREADY_EXISTS",
            status_code=409,
        )


# --- Not Found (404) ---


class UserNotFoundError(AppException):
    """User not found."""

    def __init__(self) -> None:
        super().__init__(
            message="User not found",
            code="USER_NOT_FOUND",
            status_code=404,
        )


# --- Rate Limit (429) ---


class AccountLockedError(AppException):
    """Too many failed login attempts."""

    def __init__(self) -> None:
        super().__init__(
            message="Too many failed login attempts. Please try again later.",
            code="ACCOUNT_LOCKED",
            status_code=429,
        )


# --- Exception Handler ---


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Central exception handler for AppException."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
            },
        },
    )
