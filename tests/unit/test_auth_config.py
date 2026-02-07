"""Tests for auth, database, and redis domain config classes."""

import pytest
from pydantic import SecretStr, ValidationError

from app.core.settings.auth_config import AuthConfig
from app.core.settings.database_config import DatabaseConfig
from app.core.settings.redis_config import RedisConfig


class TestAuthConfig:
    """Tests for AuthConfig frozen model."""

    def test_create_auth_config(self) -> None:
        config = AuthConfig(
            secret_key=SecretStr("secret"),
            algorithm="HS256",
            access_token_expire_minutes=30,
            refresh_token_expire_days=7,
            login_rate_limit="5/minute",
            register_rate_limit="3/minute",
        )
        assert config.algorithm == "HS256"
        assert config.access_token_expire_minutes == 30
        assert config.refresh_token_expire_days == 7
        assert config.secret_key.get_secret_value() == "secret"

    def test_auth_config_is_frozen(self) -> None:
        config = AuthConfig(
            secret_key=SecretStr("secret"),
            algorithm="HS256",
            access_token_expire_minutes=30,
            refresh_token_expire_days=7,
            login_rate_limit="5/minute",
            register_rate_limit="3/minute",
        )
        with pytest.raises(ValidationError):
            config.algorithm = "RS256"  # type: ignore[misc]


class TestDatabaseConfig:
    """Tests for DatabaseConfig."""

    def test_async_url_appends_charset(self) -> None:
        config = DatabaseConfig(
            url=SecretStr("mysql+aiomysql://root:pass@localhost:3306/db")
        )
        assert config.async_url.endswith("?charset=utf8mb4")

    def test_async_url_preserves_existing_query(self) -> None:
        config = DatabaseConfig(
            url=SecretStr("mysql+aiomysql://root:pass@localhost:3306/db?pool_size=5")
        )
        assert "?pool_size=5" in config.async_url
        assert "charset" not in config.async_url

    def test_database_config_is_frozen(self) -> None:
        config = DatabaseConfig(url=SecretStr("sqlite+aiosqlite:///:memory:"))
        with pytest.raises(ValidationError):
            config.url = SecretStr("other")  # type: ignore[misc]


class TestRedisConfig:
    """Tests for RedisConfig."""

    def test_create_redis_config(self) -> None:
        config = RedisConfig(url="redis://localhost:6379/0")
        assert config.url == "redis://localhost:6379/0"

    def test_redis_config_is_frozen(self) -> None:
        config = RedisConfig(url="redis://localhost:6379/0")
        with pytest.raises(ValidationError):
            config.url = "other"  # type: ignore[misc]


class TestSettingsAuthDomainProperties:
    """Test that Settings exposes auth/database/redis domain properties."""

    def test_settings_auth_property(self) -> None:
        from app.core.config import settings

        auth = settings.auth
        assert auth.algorithm == settings.jwt_algorithm
        assert (
            auth.access_token_expire_minutes == settings.jwt_access_token_expire_minutes
        )

    def test_settings_database_property(self) -> None:
        from app.core.config import settings

        db = settings.database
        assert db.url == settings.database_url

    def test_settings_redis_property(self) -> None:
        from app.core.config import settings

        redis_config = settings.redis
        assert redis_config.url == settings.redis_url
