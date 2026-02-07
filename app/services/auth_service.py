"""Authentication business logic."""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AccountLockedError,
    AuthenticationError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenBlacklistedError,
    UserAlreadyExistsError,
)
from app.core.security import DUMMY_HASH, hash_password, verify_password
from app.repositories.user_repo import UserRepository
from app.schemas.auth_schema import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenPayload,
    TokenResponse,
    UserResponse,
)
from app.services.token_service import MAX_LOGIN_ATTEMPTS, TokenService

logger = structlog.get_logger()


class AuthService:
    """Orchestrates registration, login, logout, and token refresh."""

    def __init__(
        self,
        user_repo: UserRepository,
        token_service: TokenService,
        session: AsyncSession,
    ) -> None:
        self._user_repo = user_repo
        self._token_service = token_service
        self._session = session

    async def register(self, request: RegisterRequest) -> RegisterResponse:
        """Register a new user and return tokens."""
        if await self._user_repo.exists_by_email(request.email):
            raise UserAlreadyExistsError

        hashed = await hash_password(request.password)
        user = await self._user_repo.create(
            email=request.email,
            hashed_password=hashed,
            username=request.username,
        )
        await self._session.commit()

        tokens = self._issue_tokens(user.id, user.email, user.role)
        logger.info("User registered", email=user.email, user_id=user.id)

        return RegisterResponse(
            user=UserResponse.model_validate(user),
            tokens=tokens,
        )

    async def login(self, request: LoginRequest) -> TokenResponse:
        """Authenticate a user and return tokens."""
        attempts = await self._token_service.get_login_attempts(request.email)
        if attempts >= MAX_LOGIN_ATTEMPTS:
            raise AccountLockedError

        user = await self._user_repo.find_by_email(request.email)

        if user is None:
            await verify_password(request.password, DUMMY_HASH)
            await self._token_service.record_failed_login(request.email)
            raise InvalidCredentialsError

        if not await verify_password(request.password, user.hashed_password):
            await self._token_service.record_failed_login(request.email)
            raise InvalidCredentialsError

        if not user.is_active:
            raise AuthenticationError(message="Account is disabled")

        await self._token_service.reset_login_attempts(request.email)
        logger.info("User logged in", email=user.email, user_id=user.id)

        return self._issue_tokens(user.id, user.email, user.role)

    async def logout(
        self, access_payload: TokenPayload, request: LogoutRequest
    ) -> MessageResponse:
        """Blacklist the access token and optionally the refresh token."""
        await self._token_service.blacklist_token(
            access_payload.jti, access_payload.exp
        )

        if request.refresh_token:
            try:
                refresh_payload = self._token_service.decode_token(
                    request.refresh_token
                )
                if refresh_payload.type != "refresh":
                    raise InvalidTokenError
                await self._token_service.blacklist_token(
                    refresh_payload.jti, refresh_payload.exp
                )
            except Exception:
                pass

        logger.info("User logged out", user_id=access_payload.sub)
        return MessageResponse(message="Successfully logged out")

    async def refresh(self, request: RefreshRequest) -> TokenResponse:
        """Issue new tokens using a valid refresh token."""
        payload = self._token_service.decode_token(request.refresh_token)

        if payload.type != "refresh":
            raise InvalidTokenError

        if await self._token_service.is_blacklisted(payload.jti):
            raise TokenBlacklistedError

        if not await self._token_service.acquire_refresh_lock(payload.jti):
            raise InvalidTokenError

        try:
            await self._token_service.blacklist_token(payload.jti, payload.exp)

            user = await self._user_repo.find_by_id(int(payload.sub))
            if user is None or not user.is_active:
                raise AuthenticationError(message="Account is disabled")

            return self._issue_tokens(user.id, user.email, user.role)
        finally:
            await self._token_service.release_refresh_lock(payload.jti)

    def _issue_tokens(self, user_id: int, email: str, role: str) -> TokenResponse:
        """Create an access/refresh token pair."""
        return TokenResponse(
            access_token=self._token_service.create_access_token(user_id, email, role),
            refresh_token=self._token_service.create_refresh_token(
                user_id, email, role
            ),
            expires_in=settings.auth.access_token_expire_minutes * 60,
        )
