"""Integration tests for auth endpoints."""

import fakeredis.aioredis
from httpx import AsyncClient


class TestRegisterEndpoint:
    """Tests for POST /api/auth/register."""

    async def test_register_success(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/api/auth/register",
            json={
                "email": "new@example.com",
                "password": "Test1234!",
                "username": "newuser",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user"]["email"] == "new@example.com"
        assert "access_token" in data["tokens"]

    async def test_register_duplicate(self, async_client: AsyncClient) -> None:
        payload = {
            "email": "dup@example.com",
            "password": "Test1234!",
            "username": "user",
        }
        await async_client.post("/api/auth/register", json=payload)
        resp = await async_client.post("/api/auth/register", json=payload)
        assert resp.status_code == 409

    async def test_register_invalid_email(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/api/auth/register",
            json={
                "email": "not-valid",
                "password": "Test1234!",
                "username": "user",
            },
        )
        assert resp.status_code == 422

    async def test_register_weak_password(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/api/auth/register",
            json={
                "email": "weak@example.com",
                "password": "weak",
                "username": "user",
            },
        )
        assert resp.status_code == 422


class TestLoginEndpoint:
    """Tests for POST /api/auth/login."""

    async def _register(self, client: AsyncClient) -> None:
        await client.post(
            "/api/auth/register",
            json={
                "email": "login@example.com",
                "password": "Test1234!",
                "username": "loginuser",
            },
        )

    async def test_login_success(self, async_client: AsyncClient) -> None:
        await self._register(async_client)
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": "login@example.com", "password": "Test1234!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, async_client: AsyncClient) -> None:
        await self._register(async_client)
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": "login@example.com", "password": "WrongPass1!"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": "ghost@example.com", "password": "Test1234!"},
        )
        assert resp.status_code == 401


class TestLogoutEndpoint:
    """Tests for POST /api/auth/logout."""

    async def test_logout_success(
        self,
        async_client: AsyncClient,
        fake_redis: fakeredis.aioredis.FakeRedis,
    ) -> None:
        await async_client.post(
            "/api/auth/register",
            json={
                "email": "logout@example.com",
                "password": "Test1234!",
                "username": "logoutuser",
            },
        )
        login_resp = await async_client.post(
            "/api/auth/login",
            json={"email": "logout@example.com", "password": "Test1234!"},
        )
        token = login_resp.json()["access_token"]
        resp = await async_client.post(
            "/api/auth/logout",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Successfully logged out"

    async def test_logout_without_auth(self, async_client: AsyncClient) -> None:
        resp = await async_client.post("/api/auth/logout", json={})
        assert resp.status_code == 401


class TestRefreshEndpoint:
    """Tests for POST /api/auth/refresh."""

    async def test_refresh_success(self, async_client: AsyncClient) -> None:
        await async_client.post(
            "/api/auth/register",
            json={
                "email": "refresh@example.com",
                "password": "Test1234!",
                "username": "refreshuser",
            },
        )
        login_resp = await async_client.post(
            "/api/auth/login",
            json={"email": "refresh@example.com", "password": "Test1234!"},
        )
        refresh_token = login_resp.json()["refresh_token"]
        resp = await async_client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_refresh_with_invalid_token(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert resp.status_code == 401
