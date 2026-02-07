"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.chat_router import router as chat_router
from app.core.config import settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info(
        "Starting application",
        app_name=settings.app.name,
        environment=settings.app.env,
        llm_provider=settings.llm.provider,
    )
    yield
    # Shutdown
    logger.info("Shutting down application")


app = FastAPI(
    title=settings.app.name,
    description="LangChain 기반 채팅 서비스 - 웹검색, 파일 처리(RAG) 지원",
    version="0.1.0",
    lifespan=lifespan,
    debug=settings.app.debug,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "app": settings.app.name,
        "version": "0.1.0",
        "docs": "/docs",
    }


# Register routers
app.include_router(chat_router)
