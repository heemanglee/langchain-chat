"""Agent service for LangGraph ReAct agent."""

import re
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from app.schemas.chat_schema import ChatRequest, ChatResponse, StreamEvent
from app.tools.web_search import web_search


class AgentService:
    """Service for managing LangGraph ReAct agent interactions."""

    def __init__(self, llm: BaseChatModel) -> None:
        """Initialize the agent service.

        Args:
            llm: The language model to use for the agent.
        """
        self._llm = llm
        self._memory = MemorySaver()
        self._tools = [web_search]
        self._agent = create_react_agent(
            model=self._llm,
            tools=self._tools,
            checkpointer=self._memory,
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Process a chat request and return a response.

        Args:
            request: The chat request containing the user message.

        Returns:
            ChatResponse with the agent's reply.
        """
        conversation_id = request.conversation_id or str(uuid.uuid4())

        config: RunnableConfig = {
            "configurable": {"thread_id": conversation_id},
        }

        response = await self._agent.ainvoke(
            {"messages": [("user", request.message)]},
            config=config,
        )

        messages = response.get("messages", [])
        ai_message = self._extract_last_ai_message(messages)
        sources = self._extract_sources(messages)

        return ChatResponse(
            message=ai_message,
            conversation_id=conversation_id,
            sources=sources,
            created_at=datetime.now(),
        )

    async def stream_chat(
        self,
        request: ChatRequest,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream chat response as Server-Sent Events.

        Args:
            request: The chat request containing the user message.

        Yields:
            StreamEvent objects for each streaming event.
        """
        conversation_id = request.conversation_id or str(uuid.uuid4())

        config: RunnableConfig = {
            "configurable": {"thread_id": conversation_id},
        }

        async for event in self._agent.astream_events(
            {"messages": [("user", request.message)]},
            config=config,
            version="v2",
        ):
            stream_event = self._process_stream_event(dict(event))
            if stream_event:
                yield stream_event

        yield StreamEvent(event="done", data=conversation_id)

    def _process_stream_event(self, event: dict[str, Any]) -> StreamEvent | None:
        """Process a LangGraph stream event into a StreamEvent.

        Args:
            event: The raw event from astream_events.

        Returns:
            StreamEvent or None if event should be skipped.
        """
        event_type = event.get("event", "")

        if event_type == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and isinstance(chunk, AIMessage) and chunk.content:
                return StreamEvent(event="token", data=str(chunk.content))

        elif event_type == "on_tool_start":
            tool_name = event.get("name", "unknown")
            tool_input = event.get("data", {}).get("input", {})
            return StreamEvent(
                event="tool_call",
                data=f"{tool_name}: {tool_input}",
            )

        elif event_type == "on_tool_end":
            output = event.get("data", {}).get("output", "")
            truncated = str(output)[:500]
            return StreamEvent(event="tool_result", data=truncated)

        return None

    def _extract_last_ai_message(self, messages: list[BaseMessage]) -> str:
        """Extract the last AI message content from messages.

        Args:
            messages: List of messages from the agent response.

        Returns:
            The content of the last AI message.
        """
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                return str(message.content)
        return ""

    def _extract_sources(self, messages: list[BaseMessage]) -> list[str]:
        """Extract source URLs from tool messages.

        Args:
            messages: List of messages from the agent response.

        Returns:
            List of extracted URLs.
        """
        sources: list[str] = []
        url_pattern = re.compile(r"https?://[^\s\]\)\"']+")

        for message in messages:
            if isinstance(message, ToolMessage):
                content = str(message.content)
                urls = url_pattern.findall(content)
                sources.extend(urls)

        return list(dict.fromkeys(sources))
