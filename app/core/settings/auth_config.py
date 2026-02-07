"""JWT authentication configuration."""

from pydantic import BaseModel, SecretStr


class AuthConfig(BaseModel, frozen=True):
    """JWT authentication settings."""

    secret_key: SecretStr
    algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    login_rate_limit: str
    register_rate_limit: str
