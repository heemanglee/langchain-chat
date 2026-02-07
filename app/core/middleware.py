"""ASGI authentication middleware."""

import json
from typing import Any

import jwt
import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.redis import redis_client
from app.services.token_service import BLACKLIST_PREFIX

logger = structlog.get_logger()

PUBLIC_PATHS: set[str] = {
    "",
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/refresh",
}


class AuthMiddleware:
    """Pure ASGI middleware for JWT validation (SSE-compatible)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        normalized = path.rstrip("/") or "/"
        if normalized in PUBLIC_PATHS or path.startswith(("/docs", "/redoc")):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()

        if not auth_header.startswith("Bearer "):
            await self._send_error(
                send, 401, "MISSING_TOKEN", "Authorization header required"
            )
            return

        token = auth_header[7:]
        secret = settings.auth.secret_key.get_secret_value()
        algorithm = settings.auth.algorithm

        try:
            payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[algorithm])
        except jwt.ExpiredSignatureError:
            await self._send_error(send, 401, "TOKEN_EXPIRED", "Token has expired")
            return
        except jwt.InvalidTokenError:
            await self._send_error(send, 401, "INVALID_TOKEN", "Invalid token")
            return

        if payload.get("type") != "access":
            await self._send_error(send, 401, "INVALID_TOKEN", "Invalid token type")
            return

        jti = payload.get("jti", "")
        if redis_client is not None:
            is_blacklisted = await redis_client.get(f"{BLACKLIST_PREFIX}{jti}")
            if is_blacklisted is not None:
                await self._send_error(
                    send, 401, "TOKEN_BLACKLISTED", "Token has been revoked"
                )
                return

        scope.setdefault("state", {})
        scope["state"]["user_id"] = int(payload["sub"])
        scope["state"]["email"] = payload["email"]
        scope["state"]["role"] = payload["role"]
        scope["state"]["jti"] = jti
        scope["state"]["exp"] = payload["exp"]

        await self.app(scope, receive, send)

    @staticmethod
    async def _send_error(send: Send, status: int, code: str, message: str) -> None:
        """Send a JSON error response directly."""
        body = json.dumps({"status": status, "message": message, "code": code}).encode()

        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode()],
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
