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

from app.core.exceptions import (
    AppException,
    AuthorizationError,
    MessageNotFoundError,
    SessionNotFoundError,
)
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
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

        async for event in self._agent.astream_events(
            {"messages": input_messages},
            config=config,
            version="v2",
        ):
            event_dict = dict(event)
            stream_event = self._process_stream_event(event_dict)
            if stream_event:
                yield stream_event

        state = await self._agent.aget_state(config)
        all_messages = state.values.get("messages", [])
        new_messages = self._convert_messages_to_dicts(
            all_messages[len(input_messages):]
        )
        records = await self._save_messages(session.id, request.message, new_messages)

        user_message_id, ai_message_id = self._extract_message_ids(records)

        yield StreamEvent(
            event="done",
            data=json.dumps(
                {
                    "conversation_id": conversation_id,
                    "session_id": session.id,
                    "is_new_session": is_new,
                    "user_message_id": user_message_id,
                    "ai_message_id": ai_message_id,
                }
            ),
        )

    async def stream_regenerate(
        self,
        conversation_id: str,
        message_id: int,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Regenerate an AI response by deleting it and re-invoking the agent.

        Yields:
            StreamEvent objects for each streaming event.
        """
        session, _message = await self._validate_message_ownership(
            conversation_id, message_id, expected_role="ai"
        )

        await self._chat_repo.delete_messages_from_id(session.id, message_id)

        history = await self._load_history(session.id)
        if not history:
            raise AppException(
                message="No messages to regenerate from",
                code="NO_MESSAGES",
                status_code=400,
            )

        last_human_message_id = await self._find_last_human_message_id(session.id)

        config: RunnableConfig = {
            "configurable": {"thread_id": conversation_id},
        }

        async for event in self._agent.astream_events(
            {"messages": history},
            config=config,
            version="v2",
        ):
            event_dict = dict(event)
            stream_event = self._process_stream_event(event_dict)
            if stream_event:
                yield stream_event

        state = await self._agent.aget_state(config)
        all_messages = state.values.get("messages", [])
        new_messages = self._convert_messages_to_dicts(
            all_messages[len(history):]
        )
        records = await self._save_ai_messages(session.id, new_messages)

        ai_message_id = self._extract_ai_message_id(records)

        yield StreamEvent(
            event="done",
            data=json.dumps(
                {
                    "conversation_id": conversation_id,
                    "session_id": session.id,
                    "user_message_id": last_human_message_id,
                    "ai_message_id": ai_message_id,
                }
            ),
        )

    async def stream_edit(
        self,
        conversation_id: str,
        message_id: int,
        new_content: str,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Edit a user message and re-invoke the agent from that point.

        Yields:
            StreamEvent objects for each streaming event.
        """
        session, _message = await self._validate_message_ownership(
            conversation_id, message_id, expected_role="human"
        )

        await self._chat_repo.delete_messages_from_id(session.id, message_id)

        history = await self._load_history(session.id)
        input_messages = history + [HumanMessage(content=new_content)]

        config: RunnableConfig = {
            "configurable": {"thread_id": conversation_id},
        }

        async for event in self._agent.astream_events(
            {"messages": input_messages},
            config=config,
            version="v2",
        ):
            event_dict = dict(event)
            stream_event = self._process_stream_event(event_dict)
            if stream_event:
                yield stream_event

        state = await self._agent.aget_state(config)
        all_messages = state.values.get("messages", [])
        new_messages = self._convert_messages_to_dicts(
            all_messages[len(input_messages):]
        )
        records = await self._save_messages(session.id, new_content, new_messages)

        user_message_id, ai_message_id = self._extract_message_ids(records)

        yield StreamEvent(
            event="done",
            data=json.dumps(
                {
                    "conversation_id": conversation_id,
                    "session_id": session.id,
                    "user_message_id": user_message_id,
                    "ai_message_id": ai_message_id,
                }
            ),
        )

    async def _validate_message_ownership(
        self,
        conversation_id: str,
        message_id: int,
        expected_role: str,
    ) -> tuple[ChatSession, ChatMessage]:
        """Validate that the message belongs to the user's session with expected role."""
        session = await self._chat_repo.find_session_by_conversation_id(conversation_id)
        if session is None:
            raise SessionNotFoundError()

        if session.user_id != self._user_id:
            raise AuthorizationError(
                message="Not authorized to access this conversation"
            )

        message = await self._chat_repo.find_message_by_id(message_id)
        if message is None:
            raise MessageNotFoundError()

        if message.session_id != session.id:
            raise AppException(
                message="Message does not belong to this conversation",
                code="MESSAGE_OWNERSHIP_ERROR",
                status_code=403,
            )

        if message.role != expected_role:
            raise AppException(
                message=f"Expected {expected_role} message, got {message.role}",
                code="INVALID_MESSAGE_ROLE",
                status_code=400,
            )

        return session, message

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
        messages = self._build_langchain_messages(db_messages)
        return self._sanitize_message_sequence(messages)

    async def _save_messages(
        self,
        session_id: int,
        user_message: str,
        new_messages: list[dict[str, Any]],
    ) -> list[ChatMessage]:
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
        return records

    async def _save_ai_messages(
        self,
        session_id: int,
        new_messages: list[dict[str, Any]],
    ) -> list[ChatMessage]:
        """Save only AI/tool messages to DB (no human message)."""
        records: list[ChatMessage] = []
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
        return records

    async def _find_last_human_message_id(self, session_id: int) -> int | None:
        """Find the ID of the last human message in a session."""
        db_messages = await self._chat_repo.find_messages_by_session_id(session_id)
        for msg in reversed(db_messages):
            if msg.role == "human":
                return msg.id
        return None

    @staticmethod
    def _extract_message_ids(
        records: list[ChatMessage],
    ) -> tuple[int | None, int | None]:
        """Extract user and AI message IDs from saved records."""
        user_id = None
        ai_id = None
        for record in records:
            if record.role == "human" and user_id is None:
                user_id = record.id
            if record.role == "ai":
                ai_id = record.id
        return user_id, ai_id

    @staticmethod
    def _extract_ai_message_id(records: list[ChatMessage]) -> int | None:
        """Extract the AI message ID from saved records."""
        for record in records:
            if record.role == "ai":
                return record.id
        return None

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
    def _sanitize_message_sequence(
        messages: list[BaseMessage],
    ) -> list[BaseMessage]:
        """Remove orphaned tool messages that lack a preceding AIMessage with tool_calls.

        Handles backward compatibility for conversations where intermediate
        AI messages with tool_calls were not saved to the database.
        """
        result: list[BaseMessage] = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                has_valid_predecessor = False
                for prev in reversed(result):
                    if isinstance(prev, ToolMessage):
                        continue
                    if isinstance(prev, AIMessage) and prev.tool_calls:
                        has_valid_predecessor = True
                    break
                if not has_valid_predecessor:
                    continue
            result.append(msg)
        return result

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
    def _convert_messages_to_dicts(
        messages: list[BaseMessage],
    ) -> list[dict[str, Any]]:
        """Convert LangChain message objects to dict format for DB persistence."""
        result: list[dict[str, Any]] = []
        for msg in messages:
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
