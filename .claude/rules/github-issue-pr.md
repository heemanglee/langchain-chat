# GitHub Issue & PR 규칙

## Issue 생성

### 형식

```markdown
## Summary
한 줄로 변경 목적을 요약한다.

## Background
- 변경이 필요한 이유, 배경 설명
- 관련 시스템/의존성 정보

## Changes
### 카테고리별 변경 (예: API Endpoint Changes, Code Changes)
| 기존 | 신규 |
|------|------|
| ... | ... |

- 구체적인 코드/파일 변경 사항 bullet point

## Impact
- 변경이 다른 코드/시스템에 미치는 영향
- 호환성 관련 사항

## Checklist
- [ ] 주요 변경 항목 1
- [ ] 주요 변경 항목 2
- [ ] 로컬 테스트 완료
```

### 규칙
- 제목은 `type: 설명` 형식 (feat, fix, refactor, docs, test, chore, perf, ci)
- 본문은 한국어로 작성
- label은 변경 유형에 맞게 아래 목록에서 선택

### Label 목록

| Label | 색상 | 설명 |
|-------|------|------|
| `feat` | `#a2eeef` | 새로운 기능 |
| `fix` | `#d73a4a` | 버그 수정 |
| `refactor` | `#0075ca` | 코드 리팩토링 |
| `docs` | `#0075ca` | 문서 추가/수정 |
| `test` | `#bfd4f2` | 테스트 추가/수정 |
| `chore` | `#e4e669` | 설정, 의존성 등 기타 작업 |
| `perf` | `#f9d0c4` | 성능 개선 |
| `ci` | `#fbca04` | CI/CD 파이프라인 |
| `bug` | `#d73a4a` | 버그 리포트 (GitHub 기본) |
| `enhancement` | `#a2eeef` | 기능 개선 (GitHub 기본) |
| `documentation` | `#0075ca` | 문서 관련 (GitHub 기본) |

## PR 생성

### 형식

```markdown
## Summary
- 변경사항 요약 bullet point 1
- 변경사항 요약 bullet point 2

## Changes
### New Files (신규 파일이 있는 경우)
| File | Description |
|------|-------------|
| `path/to/file.py` | 파일 설명 |

### Modified Files
| File | Changes |
|------|---------|
| `path/to/file.py` | 변경 내용 설명 |

## Test Plan
- [x] 테스트 항목 1 (N개 통과)
- [x] 테스트 항목 2
- [x] 커버리지 XX%

## Security Considerations (해당 시 포함)
- [x] 입력 검증 완료
- [x] 민감 정보 노출 없음

Closes #이슈번호
```

### 규칙
- PR 제목은 70자 이내
- PR 본문 마지막에 반드시 `Closes #이슈번호` 포함 (merge 시 issue 자동 close)
- 한국어로 작성
- 커버리지 및 테스트 결과 명시

## 브랜치 네이밍

```
feat/{issue_number}-{짧은-설명}
fix/{issue_number}-{짧은-설명}
refactor/{issue_number}-{짧은-설명}
```

- issue 번호를 반드시 포함
- 설명은 kebab-case, 영문으로 작성
- 예: `feat/42-config-domain-split`, `fix/15-login-error`
