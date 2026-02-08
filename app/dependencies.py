"""Global dependencies for the application."""

from collections.abc import Callable
from functools import lru_cache

from fastapi import Depends, Request
from fastapi.security import HTTPBearer
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_async_session
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.redis import get_redis
from app.repositories.chat_repo import ChatRepository
from app.repositories.user_repo import UserRepository
from app.services.agent_service import AgentService
from app.services.auth_service import AuthService
from app.services.conversation_service import ConversationService
from app.services.token_service import TokenService

bearer_scheme = HTTPBearer(auto_error=False)


# --- Existing dependencies ---


@lru_cache
def get_llm() -> BaseChatModel:
    """Get the LLM instance based on the configured provider."""
    llm_config = settings.llm
    match llm_config.provider:
        case "openai":
            return ChatOpenAI(
                model=llm_config.openai_model,
                api_key=llm_config.openai_api_key,
                streaming=True,
            )
        case "anthropic":
            return ChatAnthropic(  # type: ignore[call-arg]
                model_name=llm_config.anthropic_model,
                api_key=llm_config.anthropic_api_key,
                streaming=True,
            )
        case _:
            raise ValueError(f"Unsupported LLM provider: {llm_config.provider}")


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    """Get the embeddings model instance."""
    return OpenAIEmbeddings(
        api_key=settings.llm.openai_api_key,
    )


# --- Auth dependencies ---


class CurrentUser(BaseModel):
    """Authenticated user extracted from request state."""

    model_config = ConfigDict(frozen=True)

    id: int
    email: str
    role: str


def get_token_service() -> TokenService:
    """Get TokenService backed by the active Redis client."""
    return TokenService(get_redis())


def get_user_repository(
    session: AsyncSession = Depends(get_async_session),
) -> UserRepository:
    """Get UserRepository bound to the current session."""
    return UserRepository(session)


def get_chat_repository(
    session: AsyncSession = Depends(get_async_session),
) -> ChatRepository:
    """Get ChatRepository bound to the current session."""
    return ChatRepository(session)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    token_service: TokenService = Depends(get_token_service),
    session: AsyncSession = Depends(get_async_session),
) -> AuthService:
    """Get AuthService with all dependencies."""
    return AuthService(
        user_repo=user_repo,
        token_service=token_service,
        session=session,
    )


def get_current_user(request: Request) -> CurrentUser:
    """Extract the authenticated user from middleware-populated state."""
    state = getattr(request, "state", None)
    user_id = getattr(state, "user_id", None) if state else None
    if user_id is None:
        raise AuthenticationError(message="Not authenticated")
    return CurrentUser(
        id=state.user_id,
        email=state.email,
        role=state.role,
    )


def require_role(*allowed_roles: str) -> Callable[..., CurrentUser]:
    """Dependency factory that enforces role-based access control."""

    def _check(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise AuthorizationError(
                message=f"Role '{current_user.role}' is not permitted"
            )
        return current_user

    return _check


def get_conversation_service(
    chat_repo: ChatRepository = Depends(get_chat_repository),
    current_user: CurrentUser = Depends(get_current_user),
) -> ConversationService:
    """Get ConversationService for the authenticated user."""
    return ConversationService(chat_repo=chat_repo, user_id=current_user.id)


def get_agent_service(
    chat_repo: ChatRepository = Depends(get_chat_repository),
    current_user: CurrentUser = Depends(get_current_user),
) -> AgentService:
    """Get AgentService with DB persistence and user context."""
    llm = get_llm()
    return AgentService(llm=llm, chat_repo=chat_repo, user_id=current_user.id)
