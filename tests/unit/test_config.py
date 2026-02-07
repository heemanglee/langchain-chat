"""Tests for domain-specific configuration."""

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.core.settings import (
    AppConfig,
    FileUploadConfig,
    LLMConfig,
    ServerConfig,
    VectorStoreConfig,
)


class TestLLMConfig:
    """LLMConfig frozen immutability and field access tests."""

    def test_frozen_immutability(self) -> None:
        config = LLMConfig(
            provider="openai",
            openai_api_key=SecretStr("key"),
            openai_model="gpt-4o-mini",
            anthropic_api_key=SecretStr(""),
            anthropic_model="claude-sonnet-4-20250514",
        )
        with pytest.raises(ValidationError):
            config.provider = "anthropic"  # type: ignore[misc]

    def test_field_access(self) -> None:
        config = LLMConfig(
            provider="anthropic",
            openai_api_key=SecretStr("ok"),
            openai_model="gpt-4o",
            anthropic_api_key=SecretStr("ak"),
            anthropic_model="claude-sonnet-4-20250514",
        )
        assert config.provider == "anthropic"
        assert config.openai_model == "gpt-4o"
        assert config.anthropic_model == "claude-sonnet-4-20250514"


class TestAppConfig:
    """AppConfig frozen immutability and property tests."""

    def test_frozen_immutability(self) -> None:
        config = AppConfig(name="test", env="development", debug=True)
        with pytest.raises(ValidationError):
            config.name = "changed"  # type: ignore[misc]

    def test_is_development(self) -> None:
        config = AppConfig(name="app", env="development", debug=True)
        assert config.is_development is True
        assert config.is_production is False

    def test_is_production(self) -> None:
        config = AppConfig(name="app", env="production", debug=False)
        assert config.is_production is True
        assert config.is_development is False


class TestVectorStoreConfig:
    """VectorStoreConfig frozen immutability tests."""

    def test_frozen_immutability(self) -> None:
        config = VectorStoreConfig(
            path=Path("./data"), chunk_size=1000, chunk_overlap=200
        )
        with pytest.raises(ValidationError):
            config.chunk_size = 500  # type: ignore[misc]

    def test_field_access(self) -> None:
        config = VectorStoreConfig(
            path=Path("/tmp/store"), chunk_size=500, chunk_overlap=100
        )
        assert config.path == Path("/tmp/store")
        assert config.chunk_size == 500
        assert config.chunk_overlap == 100


class TestFileUploadConfig:
    """FileUploadConfig frozen immutability and property tests."""

    def test_frozen_immutability(self) -> None:
        config = FileUploadConfig(max_file_size_mb=10, allowed_extensions="pdf,txt")
        with pytest.raises(ValidationError):
            config.max_file_size_mb = 20  # type: ignore[misc]

    def test_allowed_extensions_list(self) -> None:
        config = FileUploadConfig(max_file_size_mb=10, allowed_extensions="pdf, txt, md")
        assert config.allowed_extensions_list == ["pdf", "txt", "md"]

    def test_max_file_size_bytes(self) -> None:
        config = FileUploadConfig(max_file_size_mb=5, allowed_extensions="pdf")
        assert config.max_file_size_bytes == 5 * 1024 * 1024


class TestServerConfig:
    """ServerConfig frozen immutability tests."""

    def test_frozen_immutability(self) -> None:
        config = ServerConfig(host="0.0.0.0", port=8000)
        with pytest.raises(ValidationError):
            config.port = 9000  # type: ignore[misc]

    def test_field_access(self) -> None:
        config = ServerConfig(host="127.0.0.1", port=3000)
        assert config.host == "127.0.0.1"
        assert config.port == 3000


class TestSettingsDomainProperties:
    """Settings domain property access tests."""

    def test_llm_property(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.llm.provider == "anthropic"
        assert s.llm.openai_api_key.get_secret_value() == "test-openai-key"
        assert s.llm.anthropic_api_key.get_secret_value() == "test-anthropic-key"

    def test_app_property(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_NAME", "my-app")
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("DEBUG", "false")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.app.name == "my-app"
        assert s.app.env == "production"
        assert s.app.debug is False
        assert s.app.is_production is True

    def test_vector_store_property(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.vector_store.chunk_size == 1000
        assert s.vector_store.chunk_overlap == 200

    def test_file_upload_property(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.file_upload.max_file_size_mb == 10
        assert s.file_upload.allowed_extensions_list == ["pdf", "txt", "md"]

    def test_server_property(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOST", "127.0.0.1")
        monkeypatch.setenv("PORT", "9000")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.server.host == "127.0.0.1"
        assert s.server.port == 9000

    def test_flat_access_still_works(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.llm_provider == "openai"
        assert s.app_name == "langchain-chat"
        assert s.chunk_size == 1000

    def test_convenience_properties_delegate(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.is_development is True
        assert s.allowed_extensions_list == ["pdf", "txt", "md"]
        assert s.max_file_size_bytes == 10 * 1024 * 1024

    def test_env_var_names_unchanged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify env var names match the original flat field names."""
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
        monkeypatch.setenv("APP_NAME", "custom-app")
        monkeypatch.setenv("CHUNK_SIZE", "500")
        monkeypatch.setenv("MAX_FILE_SIZE_MB", "20")
        monkeypatch.setenv("PORT", "3000")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.llm.provider == "openai"
        assert s.llm.openai_model == "gpt-4o"
        assert s.app.name == "custom-app"
        assert s.vector_store.chunk_size == 500
        assert s.file_upload.max_file_size_mb == 20
        assert s.server.port == 3000
