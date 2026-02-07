"""LLM provider configuration."""

from typing import Literal

from pydantic import BaseModel, SecretStr


class LLMConfig(BaseModel, frozen=True):
    """LLM provider settings."""

    provider: Literal["openai", "anthropic"]
    openai_api_key: SecretStr
    openai_model: str
    anthropic_api_key: SecretStr
    anthropic_model: str
