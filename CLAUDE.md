# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LangChain 기반 채팅 서비스. LangGraph ReAct 에이전트를 사용하여 웹 검색 도구를 호출할 수 있는 대화형 API를 제공한다.

- **Runtime:** Python 3.11
- **Framework:** FastAPI + LangGraph
- **Package Manager:** uv (uv.lock 존재)
- **LLM Providers:** OpenAI (`ChatOpenAI`), Anthropic (`ChatAnthropic`) — `LLM_PROVIDER` 환경변수로 전환

## Commands

```bash
# 서버 실행 (개발)
uvicorn app.main:app --reload --port 8004

# 테스트 (커버리지 80% 미만 시 실패)
pytest

# 단일 테스트 파일 실행
pytest tests/unit/test_chat_schema.py

# 특정 테스트 함수 실행
pytest tests/unit/test_chat_schema.py::TestChatRequest::test_valid_request -v

# 린트 & 포맷
ruff check .
ruff format .

# 타입 체크
mypy app/

# pre-commit 수동 실행
pre-commit run --all-files

# Chainlit 웹 UI
chainlit run chainlit_app.py -w
```

## Architecture

```
Router (api/v1/) → Service (services/) → Tools (tools/)
                      ↓
                   Schema (schemas/)
```

- **Router**: HTTP 엔드포인트 정의, Pydantic 검증, `Depends()`로 서비스 주입
- **Service**: `AgentService`가 LangGraph `create_react_agent()`를 래핑. `MemorySaver`로 대화 스레드 관리
- **Tools**: `@tool` 데코레이터로 정의된 LangChain 도구 (`web_search`)
- **Dependencies** (`dependencies.py`): `get_llm()`, `get_agent_service()`, `get_embeddings()` — LLM/임베딩은 `@lru_cache`로 싱글턴

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat` | 동기 채팅 → `ChatResponse` |
| POST | `/api/v1/chat/stream` | SSE 스트리밍 → `StreamEvent` |

### Streaming Event Types

`on_chat_model_stream` → `token`, `on_tool_start` → `tool_call`, `on_tool_end` → `tool_result`, 완료 시 `done`

## Configuration

`app/core/config.py`의 `Settings` 클래스가 `.env` 파일에서 Pydantic BaseSettings V2로 로드한다. `settings` 싱글턴 인스턴스를 전역으로 사용.

## Testing

- pytest + pytest-asyncio (asyncio_mode="auto")
- `tests/conftest.py`에 공유 픽스처: `client`, `async_client`, `mock_llm`
- 단위 테스트: `tests/unit/`, 통합 테스트: `tests/integration/`
- 커버리지 80% 이상 필수 (`--cov-fail-under=80`)
