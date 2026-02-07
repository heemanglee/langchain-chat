"""Unified API response schemas."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """Error response with status, message, and error code."""

    status: int
    message: str
    code: str


class ApiResponse(BaseModel, Generic[T]):
    """Success response with status, message, and data (no code field)."""

    status: int = 200
    message: str = "Success"
    data: T | None = None


def success_response(data: T, status: int = 200, message: str = "Success") -> dict:
    """Build a success response dict for returning from endpoints."""
    return {"status": status, "message": message, "data": data}
