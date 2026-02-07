"""Tests for AuthService."""

import fakeredis.aioredis
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccountLockedError,
    AuthenticationError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenBlacklistedError,
    UserAlreadyExistsError,
)
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth_schema import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPayload,
)
from app.services.auth_service import AuthService
from app.services.token_service import TokenService


@pytest.fixture
def auth_service(
    db_session: AsyncSession,
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> AuthService:
    repo = UserRepository(db_session)
    ts = TokenService(fake_redis)
    return AuthService(user_repo=repo, token_service=ts, session=db_session)


@pytest.fixture
def ts(fake_redis: fakeredis.aioredis.FakeRedis) -> TokenService:
    return TokenService(fake_redis)


class TestRegister:
    """Tests for user registration."""

    async def test_register_success(self, auth_service: AuthService) -> None:
        result = await auth_service.register(
            RegisterRequest(
                email="reg@test.com",
                password="Test1234!",
                username="tester",
            )
        )
        assert result.user.email == "reg@test.com"
        assert result.tokens.access_token
        assert result.tokens.refresh_token

    async def test_register_duplicate_email(self, auth_service: AuthService) -> None:
        await auth_service.register(
            RegisterRequest(
                email="dup@test.com", password="Test1234!", username="user1"
            )
        )
        with pytest.raises(UserAlreadyExistsError):
            await auth_service.register(
                RegisterRequest(
                    email="dup@test.com", password="Test1234!", username="user2"
                )
            )


class TestLogin:
    """Tests for user login."""

    async def _create_user(
        self, db_session: AsyncSession, email: str = "login@test.com"
    ) -> User:
        hashed = await hash_password("Test1234!")
        user = User(
            email=email,
            hashed_password=hashed,
            username="testuser",
            role="user",
        )
        db_session.add(user)
        await db_session.flush()
        return user

    async def test_login_success(
        self, auth_service: AuthService, db_session: AsyncSession
    ) -> None:
        await self._create_user(db_session)
        await db_session.commit()
        result = await auth_service.login(
            LoginRequest(email="login@test.com", password="Test1234!")
        )
        assert result.access_token
        assert result.token_type == "bearer"

    async def test_login_wrong_password(
        self, auth_service: AuthService, db_session: AsyncSession
    ) -> None:
        await self._create_user(db_session)
        await db_session.commit()
        with pytest.raises(InvalidCredentialsError):
            await auth_service.login(
                LoginRequest(email="login@test.com", password="WrongPass1!")
            )

    async def test_login_nonexistent_user(self, auth_service: AuthService) -> None:
        with pytest.raises(InvalidCredentialsError):
            await auth_service.login(
                LoginRequest(email="nope@test.com", password="Test1234!")
            )

    async def test_login_inactive_user(
        self, auth_service: AuthService, db_session: AsyncSession
    ) -> None:
        user = await self._create_user(db_session)
        user.is_active = False
        await db_session.commit()
        with pytest.raises(AuthenticationError):
            await auth_service.login(
                LoginRequest(email="login@test.com", password="Test1234!")
            )

    async def test_login_account_locked(
        self,
        auth_service: AuthService,
        db_session: AsyncSession,
        fake_redis: fakeredis.aioredis.FakeRedis,
    ) -> None:
        await self._create_user(db_session)
        await db_session.commit()
        ts = TokenService(fake_redis)
        for _ in range(5):
            await ts.record_failed_login("login@test.com")
        with pytest.raises(AccountLockedError):
            await auth_service.login(
                LoginRequest(email="login@test.com", password="Test1234!")
            )


class TestLogout:
    """Tests for user logout."""

    async def test_logout_blacklists_token(
        self,
        auth_service: AuthService,
        ts: TokenService,
    ) -> None:
        payload = TokenPayload(
            sub="1",
            email="a@b.com",
            role="user",
            type="access",
            jti="test-jti",
            exp=9999999999,
        )
        result = await auth_service.logout(payload, LogoutRequest())
        assert result.message == "Successfully logged out"
        assert await ts.is_blacklisted("test-jti") is True


class TestRefresh:
    """Tests for token refresh."""

    async def test_refresh_success(
        self,
        auth_service: AuthService,
        db_session: AsyncSession,
        ts: TokenService,
    ) -> None:
        hashed = await hash_password("Test1234!")
        user = User(
            email="ref@test.com",
            hashed_password=hashed,
            username="refuser",
            role="user",
        )
        db_session.add(user)
        await db_session.commit()

        refresh_token = ts.create_refresh_token(
            user_id=user.id, email=user.email, role=user.role
        )
        result = await auth_service.refresh(RefreshRequest(refresh_token=refresh_token))
        assert result.access_token
        assert result.refresh_token

    async def test_refresh_with_access_token_raises(
        self, auth_service: AuthService, ts: TokenService
    ) -> None:
        access_token = ts.create_access_token(user_id=1, email="a@b.com", role="user")
        with pytest.raises(InvalidTokenError):
            await auth_service.refresh(RefreshRequest(refresh_token=access_token))

    async def test_refresh_blacklisted_token_raises(
        self,
        auth_service: AuthService,
        ts: TokenService,
        fake_redis: fakeredis.aioredis.FakeRedis,
    ) -> None:
        refresh_token = ts.create_refresh_token(user_id=1, email="a@b.com", role="user")
        payload = ts.decode_token(refresh_token)
        await ts.blacklist_token(payload.jti, payload.exp)

        with pytest.raises(TokenBlacklistedError):
            await auth_service.refresh(RefreshRequest(refresh_token=refresh_token))
