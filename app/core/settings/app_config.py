"""Application environment configuration."""

from typing import Literal

from pydantic import BaseModel


class AppConfig(BaseModel, frozen=True):
    """Application environment settings."""

    name: str
    env: Literal["development", "staging", "production"]
    debug: bool

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.env == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.env == "production"
