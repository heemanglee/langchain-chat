# /dev - Backend Development Pipeline

백엔드 기능 개발의 전체 파이프라인을 실행한다.

**기능 설명:** $ARGUMENTS

---

## Pipeline Overview

아래 5단계를 순서대로 실행한다. 각 단계가 완료되어야 다음 단계로 진입한다.

```
Phase 1: PLAN → Phase 2: TDD → Phase 3: BUILD-FIX → Phase 4: CODE-REVIEW → Phase 5: VERIFY
```

---

## Phase 1: PLAN (PRD 인터뷰 + 계획 수립)

### 1-1. 사용자 인터뷰

`AskUserQuestion` 도구를 사용하여 아래 카테고리별로 질문한다. 한 번에 최대 4개 질문을 묶어서 보낸다.

**Round 1 — 기능 범위:**
- 이 기능의 핵심 목적은 무엇인가? (options: 새 기능 추가, 기존 기능 개선, 버그 수정, 리팩토링)
- 기능의 범위는? (options: 단일 엔드포인트, 여러 엔드포인트, 공통 서비스/유틸, 인프라/설정)

**Round 2 — API 및 보안:**
- 엔드포인트 유형은? (options: REST CRUD, SSE 스트리밍, 백그라운드 태스크, 내부 서비스 전용)
- 인증/인가 요구사항은? (options: 인증 필수 (Bearer JWT), 공개 엔드포인트, 관리자 전용 (require_role), RBAC 커스텀)

**Round 3 — 데이터 및 의존성:**
- DB 스키마 변경이 필요한가? (options: 새 모델 추가 → Alembic 마이그레이션 필요, 기존 모델 수정 → 마이그레이션 필요, DB 변경 없음)
- 외부 의존성은? (options: LangChain/LangGraph, Redis, 외부 API 연동, 없음)

**Round 4 — 우선순위:**
- 추가 고려사항이 있는가? (자유 입력)

### 1-2. PRD 생성

인터뷰 결과를 바탕으로 PRD 문서를 작성한다.

PRD에 포함할 내용:
- 기능 요약 및 목적
- API 엔드포인트 설계 (Method, Path, Request/Response 스키마)
- 레이어별 변경사항 (Router → Service → Repository → Schema → Model)
- DB 스키마 변경 (Alembic 마이그레이션 계획)
- 보안 요구사항 (인증/인가, 입력 검증)
- 테스트 계획

### 1-3. Plan Mode 진입

`EnterPlanMode`로 진입하여 구현 계획을 수립한다.

### 1-4. Issue & Branch 생성

계획이 승인되면 `planning-workflow.md` 규칙에 따라:
1. GitHub Issue 생성 (`gh issue create`)
2. 브랜치 생성 (`git checkout -b {type}/{issue_number}-{description}`)

---

## Phase 2: TDD (테스트 주도 개발)

`tdd-guide` 에이전트를 사용하여 TDD 워크플로우를 실행한다.

1. **RED** — 테스트 먼저 작성, `pytest` 실행으로 실패 확인
2. **GREEN** — 최소한의 코드로 테스트 통과
3. **REFACTOR** — 코드 품질 개선, 테스트 여전히 통과 확인
4. 커버리지 80%+ 검증 (`pytest --cov=app --cov-report=term-missing`)

### 완료 조건
- 모든 테스트 통과
- 커버리지 80% 이상
- 린트 에러 없음 (`ruff check .`)

---

## Phase 3: BUILD-FIX (빌드 검증 및 수정)

`/build-fix` 커맨드의 로직을 실행한다.

1. `ruff check .` + `ruff format --check .` + `mypy app/` + `pytest` 실행
2. 모든 검증 성공 → Phase 4로 진입
3. 검증 실패 → 에러 분석 → 자동 수정 → 재검증 (최대 3회)
4. 수정 후 `pytest`로 regression 확인

### 완료 조건
- 린트 + 포맷 + 타입 체크 + 테스트 모두 통과

---

## Phase 4: CODE-REVIEW (코드 리뷰)

`code-reviewer` 에이전트를 사용하여 코드 리뷰를 수행한다.

1. 변경된 파일에 대해 보안 + 품질 리뷰 실행
2. **CRITICAL** 이슈 → 즉시 수정, 재리뷰
3. **HIGH** 이슈 → 수정
4. **MEDIUM** 이슈 → 가능하면 수정

### 완료 조건
- CRITICAL 이슈 0개
- HIGH 이슈 0개
- 수정 후 전체 검증 재확인

---

## Phase 5: VERIFY (최종 검증)

`verification-agent`를 사용하여 최종 검증을 수행한다.

1. `ruff check .` — 린트 통과
2. `ruff format --check .` — 포맷 통과
3. `mypy app/` — 타입 에러 없음
4. `pytest --cov=app --cov-report=term-missing` — 테스트 통과 + 커버리지 80%+
5. 보안 체크 — 하드코딩된 시크릿 없음, `async-database.md` 규칙 준수

### 완료 조건
- 모든 검증 항목 PASS

---

## Phase 5+ : 커밋 및 PR

모든 단계 통과 후:

1. `git-workflow.md` 규칙에 따라 논리적 단위로 커밋 분리
2. `github-issue-pr.md` 규칙에 따라 PR 생성
3. PR 본문에 `Closes #이슈번호` 포함

---

## 중단 및 재개

- 어느 단계에서든 실패하면 해당 단계에서 문제를 해결한 후 재개
- 사용자가 중단을 요청하면 현재 진행 상태를 보고하고 중단
- 각 Phase 전환 시 사용자에게 진행 상황을 보고

---

## 참조 규칙

- `planning-workflow.md` — Issue/Branch 생성 순서
- `github-issue-pr.md` — Issue/PR 형식
- `project-structure.md` — 레이어 구조 (Router → Service → Repository)
- `async-database.md` — 비동기 DB 접근 규칙 (MySQL + aiomysql)
