# DB Primary Key 전략: Int PK + UUID 외부 ID

## 배경

`chat_sessions` 테이블은 **Auto-increment Int PK** (`id`)를 내부 식별자로, **UUID String** (`conversation_id`)을 외부 노출용 식별자로 사용하는 하이브리드 방식을 채택한다.

## InnoDB Clustered Index와 순차 Int PK

InnoDB는 PK를 기준으로 Clustered Index를 구성한다. 데이터가 PK 순서대로 물리적으로 저장되므로:

- **순차 삽입 최적화**: Auto-increment Int는 항상 마지막 페이지에 삽입되어 B+Tree 페이지 분할(page split)이 발생하지 않는다.
- **UUID PK의 문제**: 랜덤 UUID를 PK로 사용하면 삽입 시 B+Tree 중간 위치에 데이터가 들어가 빈번한 페이지 분할과 단편화(fragmentation)가 발생한다.
- **벤치마크**: 대량 삽입 시 UUID PK는 순차 Int PK 대비 2~5배 느린 성능을 보인다.

## FK 조인 성능

`chat_messages.session_id`가 `chat_sessions.id`를 참조하는 Foreign Key이다:

| 비교 항목 | Int PK (4/8 bytes) | UUID String (36 bytes) |
|-----------|-------------------|----------------------|
| 인덱스 크기 | 작음 | 4~9배 큼 |
| 비교 연산 | 정수 비교 (CPU 1 cycle) | 문자열 비교 (byte-by-byte) |
| 캐시 효율 | 높음 (더 많은 키가 메모리에 적재) | 낮음 |
| JOIN 성능 | 빠름 | 느림 |

메시지 조회 시 `WHERE session_id = ?` 쿼리가 빈번하게 실행되므로, Int FK의 성능 이점이 크다.

## 보안 이점

- **Int PK 단독 노출의 위험**: `/api/sessions/1`, `/api/sessions/2`처럼 순차적 ID가 외부에 노출되면 ID 열거 공격(IDOR)에 취약하다.
- **UUID 외부 ID**: `conversation_id` (UUID v4)를 API 응답에 노출하여 추측 불가능한 식별자를 제공한다.
- **내부 Int PK**: DB 내부 조인과 인덱싱에만 사용되어 성능과 보안을 동시에 확보한다.

## 본 프로젝트 적용

```
chat_sessions
├── id (Int, PK, auto-increment)      ← 내부 FK 참조용
├── conversation_id (UUID, unique)     ← 외부 API 노출용
└── user_id (Int, FK → users.id)

chat_messages
├── id (Int, PK, auto-increment)
└── session_id (Int, FK → chat_sessions.id)  ← Int 조인
```

- API 응답에는 `conversation_id` (UUID)만 노출
- DB 내부 조인은 모두 Int PK/FK로 수행
- SQLite 테스트 호환을 위해 `autoincrement=True` 사용 (`BigInteger + Identity()` 미사용)
