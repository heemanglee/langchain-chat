# /build-fix - Build Error Auto-Fix

린트, 포맷, 타입 체크, 테스트를 실행하고, 에러 발생 시 자동으로 분석 및 수정한다.

---

## 실행 절차

### Step 1: 전체 검증 실행

아래 순서대로 검증을 실행한다. 각 단계에서 에러가 발생하면 Step 2로 진입한다.

```bash
# 1. 린트
ruff check .

# 2. 포맷 검증
ruff format --check .

# 3. 타입 체크
mypy app/

# 4. 테스트
pytest
```

모든 검증 통과 시 → "빌드 성공" 보고 후 종료.

### Step 2: 에러 분석

실패한 검증의 에러 메시지를 분석하여 유형을 분류한다.

| 에러 유형 | 패턴 | 대응 |
|-----------|------|------|
| Ruff 린트 (자동 수정 가능) | `F401`(미사용 import), `I001`(import 정렬), `UP` 규칙 등 | `ruff check --fix .` 실행 |
| Ruff 린트 (수동 수정 필요) | `F811`(재정의), `E501`(라인 길이), `B` 규칙 등 | 코드 직접 수정 |
| Ruff 포맷 | 포맷 불일치 | `ruff format .` 실행 |
| mypy 타입 에러 | `error:`, `Incompatible types`, `has no attribute` | 타입 힌트/annotation 수정 |
| Import 에러 | `ModuleNotFoundError`, `ImportError` | import 경로 수정, `uv add` 의존성 추가 |
| Pydantic 에러 | `ValidationError`, `Field required`, `value_error` | 스키마 필드/타입 수정 |
| SQLAlchemy 에러 | `ArgumentError`, `MissingGreenlet`, async 관련 | 쿼리/모델 수정, `async-database.md` 규칙 참조 |
| pytest 실패 | `FAILED`, `AssertionError`, `fixture not found` | 구현 또는 테스트 수정 |

### Step 3: 자동 수정

에러 유형에 따라 수정을 적용한다.

**수정 우선순위:**
1. `ruff check --fix .` — 자동 수정 가능한 린트 에러 먼저 처리
2. `ruff format .` — 포맷 불일치 해소
3. mypy 타입 에러 — 타입 힌트/annotation 수동 수정
4. 테스트 실패 — 구현 코드 또는 테스트 코드 수정

**수정 원칙:**
- 한 번에 하나의 에러 유형만 수정
- 수정 후 관련 테스트가 깨지지 않는지 확인
- 기존 로직을 변경하지 않고 타입/import만 수정 (가능한 경우)

### Step 4: 재검증

```bash
ruff check . && ruff format --check . && mypy app/ && pytest
```

- 성공 → Step 5로 진입
- 실패 → Step 2로 돌아감 (최대 3회 반복)
- 3회 반복 후에도 실패 → 사용자에게 수동 개입 요청

### Step 5: Regression 확인

전체 검증 성공 후, 커버리지를 포함하여 최종 확인한다.

```bash
pytest --cov=app --cov-report=term-missing
```

- 커버리지 80%+ → "빌드 수정 완료" 보고
- 커버리지 미달 → 누락된 테스트 파악 후 보고

---

## 보고 형식

완료 시 아래 형식으로 보고한다:

```
## Build-Fix 결과

- 빌드 시도: N회
- 수정된 에러: N개
  - [에러 유형]: [파일:라인] — [수정 내용]
- 최종 상태: 성공/실패
- 테스트 상태: 통과/실패 (N/M)
- 커버리지: XX%
```

---

## 금지 사항

- `# type: ignore` 사용 금지 (정당한 사유 없이)
- `# noqa` 주석으로 린트 에러 회피 금지
- `Any` 타입으로 타입 에러 회피 금지
- 에러를 숨기기 위한 코드 삭제 금지
- 테스트를 `@pytest.mark.skip`으로 비활성화하여 통과시키기 금지
- `ruff check`의 `--unsafe-fixes` 플래그 사용 금지 (검토 없이)
