# Project Structure

## 디렉토리 구조

```
app/
├── main.py              # 애플리케이션 진입점 및 의존성 주입 설정
├── api/                 # Router 레이어 (엔드포인트 정의)
│   └── v1/
│       └── rag_router.py
├── services/            # Service 레이어 (비즈니스 로직, LangChain 체인 제어)
│   └── rag_service.py
├── repositories/        # Repository 레이어 (DB 또는 Vector Store 접근)
│   └── vector_repo.py
├── schemas/             # Pydantic 모델 (Request/Response DTO)
│   └── rag_schema.py
├── core/                # 공통 설정 (config, security 등)
└── dependencies.py      # 전역적으로 사용되는 의존성 관리
```

## 레이어별 책임

### Router 레이어 (`api/`)
- HTTP 엔드포인트 정의
- Request/Response 변환
- 입력 유효성 검사
- Service 호출

### Service 레이어 (`services/`)
- 비즈니스 로직 처리
- LangChain 체인 제어
- 트랜잭션 관리
- 여러 Repository 조합

### Repository 레이어 (`repositories/`)
- 데이터 접근 추상화
- Vector Store 접근 (FAISS, Pinecone 등)
- DB 쿼리 실행

### Schema 레이어 (`schemas/`)
- Pydantic 모델 정의
- Request DTO
- Response DTO
- 데이터 검증

### Core (`core/`)
- 애플리케이션 설정 (`config.py`)
- 보안 설정 (`security.py`)
- 공통 예외 (`exceptions.py`)

## 파일 네이밍 규칙

| 레이어 | 패턴 | 예시 |
|--------|------|------|
| Router | `{domain}_router.py` | `rag_router.py` |
| Service | `{domain}_service.py` | `rag_service.py` |
| Repository | `{domain}_repo.py` | `vector_repo.py` |
| Schema | `{domain}_schema.py` | `rag_schema.py` |

## 의존성 흐름

```
Router → Service → Repository
           ↓
        Schema (DTO)
```

- Router는 Service만 의존
- Service는 Repository와 Schema 의존
- Repository는 외부 저장소(DB, Vector Store) 접근
- 순환 의존성 금지
