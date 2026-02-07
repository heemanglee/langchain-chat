"""Tests for TokenService."""

import time

import fakeredis.aioredis
import pytest

from app.core.exceptions import InvalidTokenError, TokenExpiredError
from app.services.token_service import TokenService


@pytest.fixture
def ts(fake_redis: fakeredis.aioredis.FakeRedis) -> TokenService:
    return TokenService(fake_redis)


class TestCreateTokens:
    """Tests for token creation."""

    def test_create_access_token(self, ts: TokenService) -> None:
        token = ts.create_access_token(user_id=1, email="a@b.com", role="user")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self, ts: TokenService) -> None:
        token = ts.create_refresh_token(user_id=1, email="a@b.com", role="admin")
        assert isinstance(token, str)

    def test_access_token_decodes_correctly(self, ts: TokenService) -> None:
        token = ts.create_access_token(user_id=42, email="test@test.com", role="user")
        payload = ts.decode_token(token)
        assert payload.sub == "42"
        assert payload.email == "test@test.com"
        assert payload.role == "user"
        assert payload.type == "access"
        assert payload.jti is not None

    def test_refresh_token_decodes_correctly(self, ts: TokenService) -> None:
        token = ts.create_refresh_token(user_id=10, email="r@r.com", role="admin")
        payload = ts.decode_token(token)
        assert payload.type == "refresh"
        assert payload.sub == "10"


class TestDecodeToken:
    """Tests for token decoding."""

    def test_invalid_token_raises(self, ts: TokenService) -> None:
        with pytest.raises(InvalidTokenError):
            ts.decode_token("not.a.valid.token")

    def test_expired_token_raises(self, ts: TokenService) -> None:
        import jwt as pyjwt

        from app.core.config import settings

        payload = {
            "sub": "1",
            "email": "a@b.com",
            "role": "user",
            "type": "access",
            "jti": "test-jti",
            "exp": int(time.time()) - 10,
        }
        expired_token = pyjwt.encode(
            payload,
            settings.auth.secret_key.get_secret_value(),
            algorithm=settings.auth.algorithm,
        )
        with pytest.raises(TokenExpiredError):
            ts.decode_token(expired_token)


class TestBlacklist:
    """Tests for token blacklisting."""

    async def test_blacklist_and_check(self, ts: TokenService) -> None:
        future_exp = int(time.time()) + 3600
        await ts.blacklist_token("jti-123", future_exp)
        assert await ts.is_blacklisted("jti-123") is True

    async def test_not_blacklisted(self, ts: TokenService) -> None:
        assert await ts.is_blacklisted("unknown-jti") is False


class TestLoginAttempts:
    """Tests for login attempt tracking."""

    async def test_record_and_get(self, ts: TokenService) -> None:
        count = await ts.record_failed_login("fail@test.com")
        assert count == 1
        assert await ts.get_login_attempts("fail@test.com") == 1

    async def test_increment(self, ts: TokenService) -> None:
        await ts.record_failed_login("inc@test.com")
        count = await ts.record_failed_login("inc@test.com")
        assert count == 2

    async def test_reset(self, ts: TokenService) -> None:
        await ts.record_failed_login("reset@test.com")
        await ts.reset_login_attempts("reset@test.com")
        assert await ts.get_login_attempts("reset@test.com") == 0

    async def test_zero_for_unknown(self, ts: TokenService) -> None:
        assert await ts.get_login_attempts("nobody@test.com") == 0
