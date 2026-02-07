# Async Database 규칙

## 핵심 원칙

이 프로젝트에서는 **MySQL + aiomysql** 기반으로 **항상 비동기(async) 데이터베이스 접근**을 사용한다. 동기 DB 드라이버 및 세션은 사용 금지.

## 필수 의존성

```
sqlalchemy[asyncio]
aiomysql
```

## SQLAlchemy Async 설정

### 엔진 생성

```python
# WRONG: 동기 엔진
from sqlalchemy import create_engine
engine = create_engine("mysql+pymysql://user:pass@host:3306/db")

# CORRECT: 비동기 엔진
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine(
    "mysql+aiomysql://user:pass@host:3306/db",
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)
```

### 세션 팩토리

```python
# WRONG: 동기 세션
from sqlalchemy.orm import sessionmaker, Session
SessionLocal = sessionmaker(bind=engine)

# CORRECT: 비동기 세션
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

### 세션 의존성 (FastAPI)

```python
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

## DB 드라이버

| 용도 | 동기 드라이버 (사용 금지) | 비동기 드라이버 (필수) |
|------|--------------------------|----------------------|
| 애플리케이션 | `pymysql` | `aiomysql` |
| 테스트 | `pymysql` | `aiomysql` (SQLite 테스트 시 `aiosqlite`) |

## MySQL 연결 URL 형식

```python
# 환경변수에서 로드
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+aiomysql://user:password@localhost:3306/dbname"
)

# charset 명시 (한글 지원)
engine = create_async_engine(
    f"{DATABASE_URL}?charset=utf8mb4",
    pool_recycle=3600,  # MySQL wait_timeout 대응
)
```

## 쿼리 패턴

### CRUD 작업

```python
from sqlalchemy import select, update, delete

# 조회
async def find_by_id(session: AsyncSession, id: int) -> Model | None:
    result = await session.execute(select(Model).where(Model.id == id))
    return result.scalar_one_or_none()

# 목록 조회
async def find_all(session: AsyncSession) -> list[Model]:
    result = await session.execute(select(Model))
    return list(result.scalars().all())

# 생성
async def create(session: AsyncSession, data: dict) -> Model:
    instance = Model(**data)
    session.add(instance)
    await session.flush()
    return instance

# 수정
async def update_by_id(session: AsyncSession, id: int, data: dict) -> None:
    await session.execute(
        update(Model).where(Model.id == id).values(**data)
    )

# 삭제
async def delete_by_id(session: AsyncSession, id: int) -> None:
    await session.execute(
        delete(Model).where(Model.id == id)
    )
```

### Eager Loading (N+1 방지)

```python
from sqlalchemy.orm import selectinload

# WRONG: Lazy loading (async에서 동작하지 않음)
result = await session.execute(select(User))
user = result.scalar_one()
orders = user.orders  # LazyLoading 에러 발생

# CORRECT: selectinload 사용
result = await session.execute(
    select(User).options(selectinload(User.orders))
)
user = result.scalar_one()
orders = user.orders  # 이미 로드됨
```

## MySQL 특화 주의사항

### pool_recycle 필수 설정

MySQL은 기본 `wait_timeout`(8시간)이 있어 유휴 커넥션이 끊길 수 있다. 반드시 `pool_recycle`을 설정한다.

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_recycle=3600,  # 1시간마다 커넥션 재생성
)
```

### charset 설정

한글 및 이모지 지원을 위해 `utf8mb4` charset을 사용한다.

```python
# 연결 URL에 charset 명시
"mysql+aiomysql://user:pass@host:3306/db?charset=utf8mb4"
```

### Auto Increment PK

```python
from sqlalchemy import BigInteger, Identity
from sqlalchemy.orm import Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
```

## Repository 패턴 적용

```python
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

class AsyncRepository(ABC, Generic[T]):
    def __init__(self, session: AsyncSession):
        self.session = session

    @abstractmethod
    async def find_by_id(self, id: int) -> T | None:
        pass

    @abstractmethod
    async def find_all(self) -> list[T]:
        pass

    @abstractmethod
    async def create(self, data: dict) -> T:
        pass
```

## 금지 사항

- `create_engine()` 사용 금지 → `create_async_engine()` 사용
- `sessionmaker()` 단독 사용 금지 → `async_sessionmaker()` 사용
- `Session` 타입 힌트 금지 → `AsyncSession` 사용
- `session.query()` 레거시 패턴 금지 → `select()` 문 사용
- `pymysql` 드라이버 직접 사용 금지 → `aiomysql` 사용
- Lazy loading 관계 접근 금지 → `selectinload` / `joinedload` 사용

## 마이그레이션 (Alembic)

Alembic 사용 시에도 비동기 설정 적용:

```python
# alembic/env.py
from sqlalchemy.ext.asyncio import async_engine_from_config

async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
```
