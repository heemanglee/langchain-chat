"""Global dependencies for the application."""

from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.core.config import settings


@lru_cache
def get_llm() -> BaseChatModel:
    """Get the LLM instance based on the configured provider.

    Returns:
        BaseChatModel: The configured LLM instance.

    Raises:
        ValueError: If an unsupported LLM provider is configured.
    """
    match settings.llm_provider:
        case "openai":
            return ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key.get_secret_value(),
                streaming=True,
            )
        case "anthropic":
            return ChatAnthropic(
                model=settings.anthropic_model,
                api_key=settings.anthropic_api_key.get_secret_value(),
                streaming=True,
            )
        case _:
            raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    """Get the embeddings model instance.

    Uses OpenAI embeddings regardless of the LLM provider
    for consistent vector representations.

    Returns:
        OpenAIEmbeddings: The configured embeddings model.
    """
    return OpenAIEmbeddings(
        api_key=settings.openai_api_key.get_secret_value(),
    )
