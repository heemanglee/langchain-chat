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
from app.schemas.response_schema import ApiResponse, success_response
from app.services.auth_service import AuthService
from app.services.token_service import TokenService

router = APIRouter(prefix="/api/auth", tags=["auth"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]


@router.post(
    "/register",
    response_model=ApiResponse[RegisterResponse],
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: RegisterRequest,
    auth_service: AuthServiceDep,
) -> dict:
    """Register a new user."""
    result = await auth_service.register(body)
    return success_response(result, status=201)


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(
    body: LoginRequest,
    auth_service: AuthServiceDep,
) -> dict:
    """Authenticate and receive tokens."""
    result = await auth_service.login(body)
    return success_response(result)


@router.post("/logout", response_model=ApiResponse[MessageResponse])
async def logout(
    request: Request,
    body: LogoutRequest,
    token_service: TokenServiceDep,
    auth_service: AuthServiceDep,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Revoke the current access token."""
    access_payload = TokenPayload(
        sub=str(current_user.id),
        email=current_user.email,
        role=current_user.role,
        type="access",
        jti=request.state.jti,
        exp=request.state.exp,
    )
    result = await auth_service.logout(access_payload, body)
    return success_response(result)


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh(
    body: RefreshRequest,
    auth_service: AuthServiceDep,
) -> dict:
    """Refresh an access token."""
    result = await auth_service.refresh(body)
    return success_response(result)
