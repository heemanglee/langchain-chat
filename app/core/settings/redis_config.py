"""Redis connection configuration."""

from pydantic import BaseModel


class RedisConfig(BaseModel, frozen=True):
    """Redis connection settings."""

    url: str
