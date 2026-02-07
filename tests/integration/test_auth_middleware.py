"""Integration tests for AuthMiddleware."""

import fakeredis.aioredis
from httpx import AsyncClient

from tests.conftest import make_auth_headers


class TestPublicPaths:
    """Tests that public paths are accessible without auth."""

    async def test_health_check(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/health")
        assert resp.status_code == 200

    async def test_root(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/")
        assert resp.status_code == 200

    async def test_docs(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/docs")
        assert resp.status_code == 200

    async def test_register(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/api/auth/register",
            json={
                "email": "pub@example.com",
                "password": "Test1234!",
                "username": "pubuser",
            },
        )
        assert resp.status_code == 201


class TestProtectedPaths:
    """Tests that protected paths require auth."""

    async def test_chat_without_token(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/api/v1/chat",
            json={"message": "hello"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["status"] == 401
        assert data["code"] == "MISSING_TOKEN"

    async def test_chat_with_invalid_token(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/api/v1/chat",
            json={"message": "hello"},
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "INVALID_TOKEN"

    async def test_chat_with_valid_token(
        self,
        async_client: AsyncClient,
        fake_redis: fakeredis.aioredis.FakeRedis,
    ) -> None:
        headers = make_auth_headers(fake_redis)
        resp = await async_client.post(
            "/api/v1/chat",
            json={"message": "hello"},
            headers=headers,
        )
        # Should pass middleware (may fail at service level, but not 401)
        assert resp.status_code != 401

    async def test_chat_with_blacklisted_token(
        self,
        async_client: AsyncClient,
        fake_redis: fakeredis.aioredis.FakeRedis,
    ) -> None:
        from app.services.token_service import TokenService

        ts = TokenService(fake_redis)
        token = ts.create_access_token(user_id=1, email="bl@test.com", role="user")
        payload = ts.decode_token(token)
        await ts.blacklist_token(payload.jti, payload.exp)

        resp = await async_client.post(
            "/api/v1/chat",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "TOKEN_BLACKLISTED"

    async def test_refresh_token_cannot_access_protected(
        self,
        async_client: AsyncClient,
        fake_redis: fakeredis.aioredis.FakeRedis,
    ) -> None:
        from app.services.token_service import TokenService

        ts = TokenService(fake_redis)
        token = ts.create_refresh_token(user_id=1, email="rt@test.com", role="user")
        resp = await async_client.post(
            "/api/v1/chat",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "INVALID_TOKEN"
