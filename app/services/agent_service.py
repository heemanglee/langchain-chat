"""Agent service for LangGraph ReAct agent."""

import json
import re
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from app.models.chat_message import ChatMessage
from app.repositories.chat_repo import ChatRepository
from app.schemas.chat_schema import ChatRequest, ChatResponse, StreamEvent
from app.tools.web_search import web_search

SYSTEM_PROMPT_TEMPLATE = (
    "You are a helpful AI assistant.\n\n"
    "Current date and time: {system_time}\n"
    "When the user asks about 'today', 'now', 'yesterday', 'tomorrow', "
    "or any time-relative query, use this date to provide accurate information."
)


class AgentService:
    """Service for managing LangGraph ReAct agent interactions."""

    def __init__(
        self,
        llm: BaseChatModel,
        chat_repo: ChatRepository,
        user_id: int,
    ) -> None:
        self._llm = llm
        self._chat_repo = chat_repo
        self._user_id = user_id
        self._memory = MemorySaver()
        self._tools = [web_search]
        self._agent = create_react_agent(
            model=self._llm,
            tools=self._tools,
            checkpointer=self._memory,
            prompt=self._build_system_prompt,
        )

    async def chat(self, request: ChatRequest) -> tuple[ChatResponse, bool]:
        """Process a chat request with DB persistence.

        Returns:
            Tuple of (ChatResponse, is_new_session).
        """
        conversation_id = request.conversation_id or str(uuid.uuid4())

        session, is_new = await self._get_or_create_session(conversation_id)
        history = await self._load_history(session.id)

        config: RunnableConfig = {
            "configurable": {"thread_id": conversation_id},
        }

        input_messages = history + [HumanMessage(content=request.message)]

        response = await self._agent.ainvoke(
            {"messages": input_messages},
            config=config,
        )

        all_messages = response.get("messages", [])
        new_messages = self._extract_new_messages(all_messages, len(history))

        await self._save_messages(session.id, request.message, new_messages)

        ai_message = self._extract_last_ai_message(all_messages)
        sources = self._extract_sources(all_messages)

        chat_response = ChatResponse(
            message=ai_message,
            conversation_id=conversation_id,
            session_id=session.id,
            sources=sources,
            created_at=datetime.now(),
        )
        return chat_response, is_new

    async def stream_chat(
        self,
        request: ChatRequest,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream chat response as SSE with DB persistence.

        Yields:
            StreamEvent objects for each streaming event.
        """
        conversation_id = request.conversation_id or str(uuid.uuid4())

        session, is_new = await self._get_or_create_session(conversation_id)
        history = await self._load_history(session.id)

        config: RunnableConfig = {
            "configurable": {"thread_id": conversation_id},
        }

        input_messages = history + [HumanMessage(content=request.message)]

        collected_content: list[str] = []
        tool_messages: list[dict[str, Any]] = []

        async for event in self._agent.astream_events(
            {"messages": input_messages},
            config=config,
            version="v2",
        ):
            event_dict = dict(event)
            stream_event = self._process_stream_event(event_dict)
            if stream_event:
                yield stream_event

            self._collect_stream_data(event_dict, collected_content, tool_messages)

        ai_content = "".join(collected_content)
        new_messages = self._build_new_messages_from_stream(ai_content, tool_messages)
        await self._save_messages(session.id, request.message, new_messages)

        yield StreamEvent(
            event="done",
            data=json.dumps(
                {
                    "conversation_id": conversation_id,
                    "session_id": session.id,
                    "is_new_session": is_new,
                }
            ),
        )

    async def _get_or_create_session(self, conversation_id: str) -> tuple[Any, bool]:
        """Find existing session or create a new one."""
        session = await self._chat_repo.find_session_by_conversation_id(conversation_id)
        if session:
            return session, False
        session = await self._chat_repo.create_session(
            user_id=self._user_id,
            conversation_id=conversation_id,
        )
        return session, True

    async def _load_history(self, session_id: int) -> list[BaseMessage]:
        """Load previous messages from DB and convert to LangChain format."""
        db_messages = await self._chat_repo.find_messages_by_session_id(session_id)
        return self._build_langchain_messages(db_messages)

    async def _save_messages(
        self,
        session_id: int,
        user_message: str,
        new_messages: list[dict[str, Any]],
    ) -> None:
        """Save user message and agent response messages to DB."""
        records = [
            ChatMessage(
                session_id=session_id,
                role="human",
                content=user_message,
            )
        ]
        for msg in new_messages:
            records.append(
                ChatMessage(
                    session_id=session_id,
                    role=msg["role"],
                    content=msg.get("content", ""),
                    tool_calls_json=msg.get("tool_calls_json"),
                    tool_call_id=msg.get("tool_call_id"),
                    tool_name=msg.get("tool_name"),
                )
            )
        await self._chat_repo.create_messages_bulk(records)

    @staticmethod
    def _build_system_prompt(state: dict) -> list[BaseMessage]:
        """Build system prompt with current date/time (KST) prepended to state messages."""
        system_time = datetime.now(tz=ZoneInfo("Asia/Seoul")).strftime(
            "%Y-%m-%d %H:%M:%S KST"
        )
        return [
            SystemMessage(
                content=SYSTEM_PROMPT_TEMPLATE.format(system_time=system_time)
            ),
            *state["messages"],
        ]

    @staticmethod
    def _build_langchain_messages(
        db_messages: list[ChatMessage],
    ) -> list[BaseMessage]:
        """Convert DB ChatMessage records to LangChain message objects."""
        messages: list[BaseMessage] = []
        for msg in db_messages:
            if msg.role == "human":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "ai":
                kwargs: dict[str, Any] = {"content": msg.content}
                if msg.tool_calls_json:
                    kwargs["tool_calls"] = json.loads(msg.tool_calls_json)
                messages.append(AIMessage(**kwargs))
            elif msg.role == "system":
                messages.append(SystemMessage(content=msg.content))
            elif msg.role == "tool":
                messages.append(
                    ToolMessage(
                        content=msg.content,
                        tool_call_id=msg.tool_call_id or "",
                        name=msg.tool_name or "",
                    )
                )
        return messages

    @staticmethod
    def _extract_new_messages(
        all_messages: list[BaseMessage],
        history_len: int,
    ) -> list[dict[str, Any]]:
        """Extract new messages after history (skip first user message)."""
        new_msgs = all_messages[history_len + 1 :]
        result: list[dict[str, Any]] = []
        for msg in new_msgs:
            if isinstance(msg, AIMessage):
                entry: dict[str, Any] = {
                    "role": "ai",
                    "content": str(msg.content),
                }
                if msg.tool_calls:
                    entry["tool_calls_json"] = json.dumps(msg.tool_calls)
                result.append(entry)
            elif isinstance(msg, ToolMessage):
                result.append(
                    {
                        "role": "tool",
                        "content": str(msg.content),
                        "tool_call_id": msg.tool_call_id,
                        "tool_name": msg.name,
                    }
                )
            elif isinstance(msg, SystemMessage):
                result.append(
                    {
                        "role": "system",
                        "content": str(msg.content),
                    }
                )
        return result

    @staticmethod
    def _collect_stream_data(
        event: dict[str, Any],
        collected_content: list[str],
        tool_messages: list[dict[str, Any]],
    ) -> None:
        """Accumulate data from stream events for later DB persistence."""
        event_type = event.get("event", "")

        if event_type == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and isinstance(chunk, AIMessage) and chunk.content:
                collected_content.append(str(chunk.content))

        elif event_type == "on_tool_end":
            output = event.get("data", {}).get("output", "")
            tool_messages.append(
                {
                    "role": "tool",
                    "content": str(output),
                    "tool_call_id": event.get("run_id", ""),
                    "tool_name": event.get("name", ""),
                }
            )

    @staticmethod
    def _build_new_messages_from_stream(
        ai_content: str,
        tool_messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build the list of new messages from streamed data."""
        result: list[dict[str, Any]] = []
        for tool_msg in tool_messages:
            result.append(tool_msg)
        if ai_content:
            result.append({"role": "ai", "content": ai_content})
        return result

    def _process_stream_event(self, event: dict[str, Any]) -> StreamEvent | None:
        """Process a LangGraph stream event into a StreamEvent."""
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
        """Extract the last AI message content from messages."""
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                return str(message.content)
        return ""

    def _extract_sources(self, messages: list[BaseMessage]) -> list[str]:
        """Extract source URLs from tool messages."""
        sources: list[str] = []
        url_pattern = re.compile(r"https?://[^\s\]\)\"']+")

        for message in messages:
            if isinstance(message, ToolMessage):
                content = str(message.content)
                urls = url_pattern.findall(content)
                sources.extend(urls)

        return list(dict.fromkeys(sources))
