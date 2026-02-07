"""Server configuration."""

from pydantic import BaseModel


class ServerConfig(BaseModel, frozen=True):
    """Server settings."""

    host: str
    port: int
