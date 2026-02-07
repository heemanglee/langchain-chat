"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.common.auth_router import router as auth_router
from app.api.v1.chat_router import router as chat_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    validation_exception_handler,
)
from app.core.middleware import AuthMiddleware
from app.core.redis import close_redis, init_redis
from app.schemas.response_schema import ApiResponse, success_response

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    logger.info(
        "Starting application",
        app_name=settings.app.name,
        environment=settings.app.env,
        llm_provider=settings.llm.provider,
    )
    await init_redis()
    if settings.app.is_development:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await close_redis()
    await engine.dispose()
    logger.info("Shutting down application")


app = FastAPI(
    title=settings.app.name,
    description="LangChain 기반 채팅 서비스 - 웹검색, 파일 처리(RAG) 지원",
    version="0.1.0",
    lifespan=lifespan,
    debug=settings.app.debug,
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Custom handler for rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "status": 429,
            "message": "Rate limit exceeded",
            "code": "RATE_LIMIT_EXCEEDED",
        },
    )


# Exception handlers
app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]

# Middleware (registration order: inner→outer, execution order: outer→inner)
app.add_middleware(AuthMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=ApiResponse[dict])
async def health_check() -> dict:
    """Health check endpoint."""
    return success_response({"status": "healthy"})


@app.get("/", response_model=ApiResponse[dict])
async def root() -> dict:
    """Root endpoint."""
    return success_response(
        {
            "app": settings.app.name,
            "version": "0.1.0",
            "docs": "/docs",
        }
    )


# Register routers
app.include_router(auth_router)
app.include_router(chat_router)
