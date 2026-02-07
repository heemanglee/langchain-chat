"""JWT token creation, validation, and blacklist management."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import redis.asyncio as redis

from app.core.config import settings
from app.core.exceptions import (
    InvalidTokenError,
    TokenExpiredError,
)
from app.schemas.auth_schema import TokenPayload

BLACKLIST_PREFIX = "token_blacklist:"
LOGIN_ATTEMPTS_PREFIX = "login_attempts:"
REFRESH_LOCK_PREFIX = "refresh_lock:"

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300


class TokenService:
    """Manage JWT tokens and Redis-backed blacklist."""

    def __init__(self, redis_client: redis.Redis) -> None:  # type: ignore[type-arg]
        self._redis = redis_client
        self._secret = settings.auth.secret_key.get_secret_value()
        self._algorithm = settings.auth.algorithm

    def create_access_token(self, user_id: int, email: str, role: str) -> str:
        """Create a signed JWT access token."""
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=settings.auth.access_token_expire_minutes)
        payload = {
            "sub": str(user_id),
            "email": email,
            "role": role,
            "type": "access",
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": expire,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def create_refresh_token(self, user_id: int, email: str, role: str) -> str:
        """Create a signed JWT refresh token."""
        now = datetime.now(UTC)
        expire = now + timedelta(days=settings.auth.refresh_token_expire_days)
        payload = {
            "sub": str(user_id),
            "email": email,
            "role": role,
            "type": "refresh",
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": expire,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_token(self, token: str) -> TokenPayload:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError from e
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError from e

        return TokenPayload(
            sub=payload["sub"],
            email=payload["email"],
            role=payload["role"],
            type=payload["type"],
            jti=payload["jti"],
            exp=payload["exp"],
        )

    # --- Blacklist ---

    async def blacklist_token(self, jti: str, exp: int) -> None:
        """Add a token to the blacklist until it expires."""
        ttl = exp - int(datetime.now(UTC).timestamp())
        if ttl > 0:
            await self._redis.setex(f"{BLACKLIST_PREFIX}{jti}", ttl, "1")

    async def is_blacklisted(self, jti: str) -> bool:
        """Check if a token is blacklisted."""
        result = await self._redis.get(f"{BLACKLIST_PREFIX}{jti}")
        return result is not None

    # --- Login attempts ---

    async def record_failed_login(self, email: str) -> int:
        """Record a failed login attempt, return total count."""
        key = f"{LOGIN_ATTEMPTS_PREFIX}{email}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, LOGIN_LOCKOUT_SECONDS)
        return int(count)

    async def reset_login_attempts(self, email: str) -> None:
        """Clear failed login attempts after successful login."""
        await self._redis.delete(f"{LOGIN_ATTEMPTS_PREFIX}{email}")

    async def get_login_attempts(self, email: str) -> int:
        """Get current failed login attempt count."""
        result = await self._redis.get(f"{LOGIN_ATTEMPTS_PREFIX}{email}")
        return int(result) if result else 0

    # --- Refresh lock (prevent concurrent refresh) ---

    async def acquire_refresh_lock(self, jti: str) -> bool:
        """Acquire a lock for refresh token to prevent concurrent use."""
        key = f"{REFRESH_LOCK_PREFIX}{jti}"
        return bool(await self._redis.set(key, "1", ex=10, nx=True))

    async def release_refresh_lock(self, jti: str) -> None:
        """Release the refresh lock."""
        await self._redis.delete(f"{REFRESH_LOCK_PREFIX}{jti}")
