"""Application configuration using Pydantic Settings V2."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

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

    @property
    def allowed_extensions_list(self) -> list[str]:
        """Get allowed extensions as a list."""
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        """Get maximum file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"


# Global settings instance
settings = Settings()
