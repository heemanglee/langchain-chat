"""Service for generating chat session titles via LLM."""

from langchain_core.language_models import BaseChatModel


class TitleService:
    """Generates concise session titles from user messages."""

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    async def generate_title(self, message: str) -> str:
        """Summarise a user message into a title of at most 10 characters."""
        prompt = (
            "다음 사용자 질문을 10자 이내의 한국어 제목으로 요약해. "
            "제목만 출력해:\n"
            f"{message}"
        )
        response = await self._llm.ainvoke(prompt)
        return str(response.content).strip()[:10]
