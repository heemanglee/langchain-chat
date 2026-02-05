# langchain-chat

LangChain 기반 채팅 서비스 - 웹검색, 파일 처리(RAG) 지원

## 기술 스택

- **Python**: 3.11+
- **Framework**: FastAPI, Pydantic V2
- **LLM**: OpenAI, Anthropic
- **Vector Store**: FAISS
- **Web UI**: Chainlit

## 요구사항

- Python 3.11 이상
- OpenAI API Key 또는 Anthropic API Key

## 설치

### 1. 저장소 클론

```bash
git clone https://github.com/your-repo/langchain-chat.git
cd langchain-chat
```

### 2. 가상환경 생성 및 활성화

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows
```

### 3. 의존성 설치

```bash
pip install -e ".[dev]"
```

### 4. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 편집하여 API 키 설정
```

## 환경변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `LLM_PROVIDER` | LLM 제공자 (openai, anthropic) | openai |
| `OPENAI_API_KEY` | OpenAI API 키 | - |
| `OPENAI_MODEL` | OpenAI 모델명 | gpt-4o-mini |
| `ANTHROPIC_API_KEY` | Anthropic API 키 | - |
| `ANTHROPIC_MODEL` | Anthropic 모델명 | claude-sonnet-4-20250514 |

## 실행

### FastAPI 서버

```bash
uvicorn app.main:app --reload --port 8004
```

API 문서: http://localhost:8004/docs

### Chainlit 웹 UI

```bash
chainlit run chainlit_app.py -w
```

## 프로젝트 구조

```
langchain-chat/
├── app/
│   ├── main.py              # FastAPI 진입점
│   ├── dependencies.py      # LLM, VectorStore 의존성
│   ├── api/v1/              # API 라우터
│   ├── services/            # 비즈니스 로직
│   ├── repositories/        # 데이터 접근 계층
│   ├── schemas/             # Pydantic 모델
│   ├── core/                # 설정, 예외
│   └── tools/               # LangChain 도구
├── chainlit_app.py          # Chainlit 웹 UI
├── tests/                   # 테스트
└── data/vector_store/       # 벡터 스토어 데이터
```

## 개발

### 테스트 실행

```bash
pytest
```

### 린트 & 포맷

```bash
ruff check .
ruff format .
```

### 타입 체크

```bash
mypy app/
```
