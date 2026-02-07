"""Database connection configuration."""

from pydantic import BaseModel, SecretStr


class DatabaseConfig(BaseModel, frozen=True):
    """Database connection settings."""

    url: SecretStr

    @property
    def async_url(self) -> str:
        """DB URL with charset for MySQL."""
        base = self.url.get_secret_value()
        if "?" not in base:
            return f"{base}?charset=utf8mb4"
        return base
