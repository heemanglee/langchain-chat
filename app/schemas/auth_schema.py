"""Authentication request/response schemas."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr = Field(description="User email address")
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Password (8-128 chars, must include uppercase, lowercase, digit, special char)",
    )
    username: str = Field(
        min_length=2,
        max_length=100,
        description="Display name",
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr = Field(description="User email address")
    password: str = Field(description="User password")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(description="Refresh token")


class LogoutRequest(BaseModel):
    """Logout request."""

    refresh_token: str | None = Field(
        default=None, description="Optional refresh token to revoke"
    )


class TokenResponse(BaseModel):
    """Token pair response."""

    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token TTL in seconds")


class UserResponse(BaseModel):
    """Public user representation."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    email: str
    username: str
    role: str
    is_active: bool
    created_at: datetime


class RegisterResponse(BaseModel):
    """Registration response with user info and tokens."""

    model_config = ConfigDict(frozen=True)

    user: UserResponse
    tokens: TokenResponse


class MessageResponse(BaseModel):
    """Simple message response."""

    model_config = ConfigDict(frozen=True)

    message: str


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    model_config = ConfigDict(frozen=True)

    sub: str
    email: str
    role: str
    type: str
    jti: str
    exp: int
