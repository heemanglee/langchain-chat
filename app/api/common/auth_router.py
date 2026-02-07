"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.dependencies import (
    CurrentUser,
    get_auth_service,
    get_current_user,
    get_token_service,
)
from app.schemas.auth_schema import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenPayload,
    TokenResponse,
)
from app.services.auth_service import AuthService
from app.services.token_service import TokenService

router = APIRouter(prefix="/api/auth", tags=["auth"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: RegisterRequest,
    auth_service: AuthServiceDep,
) -> RegisterResponse:
    """Register a new user."""
    return await auth_service.register(body)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """Authenticate and receive tokens."""
    return await auth_service.login(body)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    body: LogoutRequest,
    token_service: TokenServiceDep,
    auth_service: AuthServiceDep,
    current_user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Revoke the current access token."""
    access_payload = TokenPayload(
        sub=str(current_user.id),
        email=current_user.email,
        role=current_user.role,
        type="access",
        jti=request.state.jti,
        exp=request.state.exp,
    )
    return await auth_service.logout(access_payload, body)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """Refresh an access token."""
    return await auth_service.refresh(body)
