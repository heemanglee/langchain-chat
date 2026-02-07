"""Application configuration using Pydantic Settings V2."""

from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.settings import (
    AppConfig,
    AuthConfig,
    DatabaseConfig,
    FileUploadConfig,
    LLMConfig,
    RedisConfig,
    ServerConfig,
    VectorStoreConfig,
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Flat fields are loaded directly from environment variables.
    Domain properties provide grouped access (e.g. settings.llm.provider).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Provider
    llm_provider: Literal["openai", "anthropic"] = Field(
        default="openai",
        description="LLM provider to use",
    )

    # OpenAI
    openai_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="OpenAI API key",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model name",
    )

    # Anthropic
    anthropic_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Anthropic API key",
    )
    anthropic_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Anthropic model name",
    )

    # App
    app_name: str = Field(
        default="langchain-chat",
        description="Application name",
    )
    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application environment",
    )
    debug: bool = Field(
        default=True,
        description="Debug mode",
    )

    # Vector Store
    vector_store_path: Path = Field(
        default=Path("./data/vector_store"),
        description="Path to vector store directory",
    )
    chunk_size: int = Field(
        default=1000,
        ge=100,
        le=4000,
        description="Text chunk size for splitting",
    )
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        le=500,
        description="Overlap between chunks",
    )

    # File Upload
    max_file_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum file size in MB",
    )
    allowed_extensions: str = Field(
        default="pdf,txt,md",
        description="Comma-separated list of allowed file extensions",
    )

    # Server
    host: str = Field(
        default="0.0.0.0",
        description="Server host",
    )
    port: int = Field(
        default=8004,
        ge=1,
        le=65535,
        description="Server port",
    )

    # JWT Auth
    jwt_secret_key: SecretStr = Field(
        description="JWT secret key for token signing",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Access token expiration in minutes",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Refresh token expiration in days",
    )
    login_rate_limit: str = Field(
        default="5/minute",
        description="Login endpoint rate limit",
    )
    register_rate_limit: str = Field(
        default="3/minute",
        description="Register endpoint rate limit",
    )

    # Database
    database_url: SecretStr = Field(
        description="Async database URL (mysql+aiomysql://...)",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # --- Domain properties ---

    @cached_property
    def llm(self) -> LLMConfig:
        """LLM provider configuration."""
        return LLMConfig(
            provider=self.llm_provider,
            openai_api_key=self.openai_api_key,
            openai_model=self.openai_model,
            anthropic_api_key=self.anthropic_api_key,
            anthropic_model=self.anthropic_model,
        )

    @cached_property
    def app(self) -> AppConfig:
        """Application environment configuration."""
        return AppConfig(
            name=self.app_name,
            env=self.app_env,
            debug=self.debug,
        )

    @cached_property
    def vector_store(self) -> VectorStoreConfig:
        """Vector store configuration."""
        return VectorStoreConfig(
            path=self.vector_store_path,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

    @cached_property
    def file_upload(self) -> FileUploadConfig:
        """File upload configuration."""
        return FileUploadConfig(
            max_file_size_mb=self.max_file_size_mb,
            allowed_extensions=self.allowed_extensions,
        )

    @cached_property
    def server(self) -> ServerConfig:
        """Server configuration."""
        return ServerConfig(
            host=self.host,
            port=self.port,
        )

    @cached_property
    def auth(self) -> AuthConfig:
        """JWT authentication configuration."""
        return AuthConfig(
            secret_key=self.jwt_secret_key,
            algorithm=self.jwt_algorithm,
            access_token_expire_minutes=self.jwt_access_token_expire_minutes,
            refresh_token_expire_days=self.jwt_refresh_token_expire_days,
            login_rate_limit=self.login_rate_limit,
            register_rate_limit=self.register_rate_limit,
        )

    @cached_property
    def database(self) -> DatabaseConfig:
        """Database connection configuration."""
        return DatabaseConfig(url=self.database_url)

    @cached_property
    def redis(self) -> RedisConfig:
        """Redis connection configuration."""
        return RedisConfig(url=self.redis_url)

    # --- Convenience properties (delegate to domain configs) ---

    @property
    def allowed_extensions_list(self) -> list[str]:
        """Get allowed extensions as a list."""
        return self.file_upload.allowed_extensions_list

    @property
    def max_file_size_bytes(self) -> int:
        """Get maximum file size in bytes."""
        return self.file_upload.max_file_size_bytes

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app.is_development


# Global settings instance
settings = Settings()
