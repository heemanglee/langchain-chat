"""Background task for generating chat session titles."""

import structlog
from langchain_core.language_models import BaseChatModel

from app.core.database import async_session_factory
from app.repositories.chat_repo import ChatRepository
from app.services.title_service import TitleService

logger = structlog.get_logger()


async def generate_session_title(
    session_id: int,
    message: str,
    llm: BaseChatModel,
) -> None:
    """Generate and persist a session title in an independent DB session.

    Designed to run as a FastAPI BackgroundTask so that the chat response
    is not blocked by the LLM call.
    """
    try:
        title_service = TitleService(llm)
        title = await title_service.generate_title(message)

        async with async_session_factory() as session:
            repo = ChatRepository(session)
            await repo.update_session_title(session_id, title)
            await session.commit()

        logger.info(
            "Session title generated",
            session_id=session_id,
            title=title,
        )
    except Exception:
        logger.exception(
            "Failed to generate session title",
            session_id=session_id,
        )
