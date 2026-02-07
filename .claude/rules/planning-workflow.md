# Planning Mode 워크플로우

## 필수 실행 순서

Plan Mode에서 계획이 **승인(accept)** 되면, 반드시 아래 순서대로 실행한다. 코드 작성은 3단계 이후에만 시작한다.

### 1단계: GitHub Issue 생성

계획 내용을 바탕으로 GitHub Issue를 먼저 생성한다.

```bash
gh issue create --title "type: 설명" --label "label" --body "$(cat <<'EOF'
## Summary
...

## Background
...

## Changes
...

## Impact
...

## Checklist
...
EOF
)"
```

- Issue 형식은 `github-issue-pr.md`의 Issue 생성 규칙을 따른다
- 제목은 `type: 설명` 형식 (feat, fix, refactor, docs, test, chore, perf, ci)
- 본문은 한국어로 작성
- 생성된 Issue 번호를 반드시 기록한다

### 2단계: 브랜치 생성

Issue 번호를 포함한 브랜치를 생성하고 체크아웃한다.

```bash
git checkout -b {type}/{issue_number}-{짧은-설명}
```

- 브랜치 네이밍은 `github-issue-pr.md`의 브랜치 네이밍 규칙을 따른다
- 예: `feat/42-add-conversation-history`, `fix/15-login-error`

### 3단계: 구현 시작

브랜치 생성이 완료된 후에만 코드 작성을 시작한다.

- `git-workflow.md`의 기능 구현 워크플로우를 따른다
- TDD 접근법 적용 (테스트 먼저 작성)
- 논리적 단위로 커밋 분리 (Atomic Commits)

### 4단계: PR 생성

구현 완료 후 PR을 생성한다.

- PR 본문 마지막에 `Closes #이슈번호` 포함
- PR 형식은 `github-issue-pr.md`의 PR 생성 규칙을 따른다

## 흐름 요약

```
Plan 승인 → Issue 생성 → 브랜치 생성 → 구현 → 커밋 → PR 생성
                ↓              ↓                        ↓
          Issue #번호    {type}/{#}-{desc}      Closes #{번호}
```

## 금지 사항

- Issue 생성 없이 바로 코드 작성 시작 금지
- Issue 번호 없이 브랜치 생성 금지
- main 브랜치에서 직접 작업 금지

## 참고 문서

- [`github-issue-pr.md`](./github-issue-pr.md) — Issue 형식, PR 형식, Label 목록, 브랜치 네이밍 규칙
