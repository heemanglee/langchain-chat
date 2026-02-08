# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LangChain 기반 채팅 서비스. LangGraph ReAct 에이전트를 사용하여 웹 검색 도구를 호출할 수 있는 대화형 API를 제공한다.

- **Runtime:** Python 3.11.9
- **Framework:** FastAPI + LangGraph
- **Package Manager:** uv (uv.lock 존재)
- **LLM Providers:** OpenAI (`ChatOpenAI`), Anthropic (`ChatAnthropic`) — `LLM_PROVIDER` 환경변수로 전환

## Commands

```bash
# 서버 실행 (개발)
uvicorn app.main:app --reload --port 8004

# 테스트 (커버리지 80% 미만 시 실패)
pytest

# 단일 테스트 파일/함수 실행
pytest tests/unit/test_chat_schema.py
pytest tests/unit/test_chat_schema.py::TestChatRequest::test_valid_request -v

# 린트 & 포맷
ruff check .
ruff format .

# 타입 체크
mypy app/

# pre-commit 수동 실행
pre-commit run --all-files

# Alembic 마이그레이션
alembic revision --autogenerate -m "message"
alembic upgrade head

# OpenAPI 스키마 생성 (FE 연동용)
python -m scripts.generate_openapi

# Chainlit 웹 UI
chainlit run chainlit_app.py -w
```

## Architecture

```
Router (api/) → Service (services/) → Repository (repositories/) → DB
     ↓               ↓                                               ↑
  Schema          Tools (tools/)                              Models (models/)
```

### Layered Structure

- **Router** (`api/v1/`, `api/common/`): HTTP 엔드포인트, Pydantic 검증, `Depends()`로 서비스 주입
- **Service**: `AgentService`(LangGraph ReAct agent), `AuthService`(회원가입/로그인), `TokenService`(JWT+Redis)
- **Repository**: `UserRepository` — 세션 주입받는 async repository 패턴
- **Tools**: `@tool` 데코레이터 LangChain 도구 (`web_search` via DuckDuckGo)
- **Dependencies** (`dependencies.py`): 3단계 DI — 싱글턴(`@lru_cache` LLM/임베딩), per-request(세션/레포지토리), composition(서비스)

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat` | 동기 채팅 → `ApiResponse[ChatResponse]` |
| POST | `/api/v1/chat/stream` | SSE 스트리밍 → `StreamEvent` |
| POST | `/api/auth/register` | 회원가입 |
| POST | `/api/auth/login` | 로그인 → JWT 토큰 발급 |
| POST | `/api/auth/logout` | 로그아웃 → 토큰 블랙리스트 |
| POST | `/api/auth/refresh` | 토큰 갱신 (동시성 락) |

### Streaming Event Types

`on_chat_model_stream` → `token`, `on_tool_start` → `tool_call`, `on_tool_end` → `tool_result`, 완료 시 `done`

## Configuration (Domain-Split Pattern)

`app/core/config.py`의 `Settings` 클래스가 `.env`에서 Pydantic BaseSettings V2로 로드. 환경변수는 **flat** (`LLM_PROVIDER`, `OPENAI_API_KEY` 등)이지만, `@cached_property`로 **도메인별 frozen config** 객체를 제공한다:

```python
settings.llm          # LLMConfig (provider, api_key, model, temperature)
settings.app          # AppConfig (name, version, env)
settings.auth         # AuthConfig (jwt_secret_key, algorithm, expire)
settings.database     # DatabaseConfig (async_url, pool_size)
settings.redis_config # RedisConfig (host, port, db)
settings.server       # ServerConfig (host, port, reload)
```

도메인 설정 클래스는 `app/core/settings/` 디렉토리에 개별 파일로 정의 (모두 `frozen=True`).

## Authentication Flow

1. **AuthMiddleware** (`core/middleware.py`): **Pure ASGI** 미들웨어 — SSE 스트리밍 호환. JWT 검증 후 `scope["state"]`에 user claims 주입. `PUBLIC_PATHS` 집합으로 인증 제외 경로 관리
2. **TokenService** (`services/token_service.py`): JWT 발급/검증, Redis 기반 토큰 블랙리스트(TTL=JWT exp), 로그인 시도 추적, refresh 동시성 락(`nx=True`)
3. **Depends RBAC** (`dependencies.py`): `get_current_user()` → middleware state에서 추출, `require_role("admin")` 팩토리 패턴

### Middleware 실행 순서

Request: CORS → SlowAPI → **AuthMiddleware** → endpoint
Response: endpoint → AuthMiddleware → SlowAPI → CORS

## Database

- **Production**: MySQL + `aiomysql` (async). `pool_recycle=3600`, `expire_on_commit=False`
- **Testing**: SQLite in-memory + `aiosqlite`
- **User PK**: `mapped_column(primary_key=True, autoincrement=True)` — `BigInteger + Identity()` 사용 금지 (SQLite 호환성)
- **Alembic**: `alembic/env.py`에서 `async_engine_from_config` 사용. DB URL은 `settings.database.async_url`에서 자동 주입

## Testing

- pytest + pytest-asyncio (`asyncio_mode="auto"`)
- 커버리지 80% 이상 필수 (`--cov-fail-under=80`)
- `tests/conftest.py` 공유 픽스처:
  - `setup_db`: SQLite in-memory 테이블 자동 생성/삭제 (autouse)
  - `fake_redis`: fakeredis 인스턴스 — `app.core.redis`와 `app.core.middleware` 양쪽 monkeypatch 필수
  - `async_client`: 인증 없는 테스트 클라이언트
  - `authed_client` / `admin_client`: JWT 포함 클라이언트
  - `make_auth_headers(fake_redis, user_id, email, role)`: 테스트용 JWT 생성 헬퍼
- DB 세션 오버라이드: `app.dependency_overrides[get_async_session]`

### API Response Format

모든 엔드포인트는 `ApiResponse[T]` 통합 포맷 사용:
- 성공: `{status: int, message: str, data: T}`
- 에러: `{status: int, message: str, code: str}`
- `success_response(data)` 헬퍼로 dict 반환 → FastAPI가 `ApiResponse`로 직렬화
