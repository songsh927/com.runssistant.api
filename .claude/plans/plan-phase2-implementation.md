# 구현 계획: 러너 프로필 온보딩 (Phase 2)

**원본 설계**: `.claude/plans/plan-phase2.md`
**대상**: 회원가입 직후 4단계 온보딩 → 러너 프로필 수집 → AI 코칭 개인화
**복잡도**: Medium (신규 파일 + 코칭 엔진 연동)
**예상 소요**: ~2일 (설계 문서 §11 기준)

> ⚠️ 이 계획은 **실행하지 않음**. 설계 문서 `plan-phase2.md`를 실제 코드베이스에
> 맞춰 재조정한 실행 계획서다. 설계 문서의 예시 코드는 현재 코드베이스 규약과
> 여러 곳에서 어긋나므로, 아래 **§0 설계 문서와 실제 코드의 차이**를 먼저 확인할 것.

---

## 0. 설계 문서(plan-phase2.md)와 실제 코드의 차이 — 반드시 반영

설계 문서의 예시 코드를 **그대로 복붙하면 안 된다.** 실제 코드베이스 규약과 다음이 어긋난다:

| # | 설계 문서 예시 | 실제 코드베이스 규약 | 적용 방침 |
|---|----------------|----------------------|-----------|
| 1 | `constraints`에 **문자열** append (`apply_profile_rules`) | `constraints`는 `list[dict[str,str]]`, `{"code","message"}` 형태 (`rule_engine.py`, `llm_coach.py:28`에서 `c['code']`, `c['message']` 사용) | 프로필 룰도 **`{"code","message"}` dict** 반환 |
| 2 | `ProfileService.__init__(user_repo)` + `Depends()` DI | 서비스는 모듈 레벨 무상태 싱글턴 (`_svc = GoalService()`), 메서드 첫 인자로 `session: AsyncSession` 전달 (`goal_service.py:14`) | `ProfileService`도 동일 패턴, `Depends()` 대신 라우트에서 `_svc` 사용 |
| 3 | `user_repo.get/update` 존재 가정 | **`UserRepository`가 없음** — auth/dependencies는 `User`를 직접 `select`로 조회 | `app/repositories/user_repo.py` **신규 생성** (레이어 규약 준수: api→services→repositories→models) |
| 4 | `raise HTTPException(409, ...)` | 커스텀 `AppException` + `error_handlers` 사용, 라우트에서 raw HTTPException 금지 (CLAUDE.md, `exceptions.py`) | 신규 `AppException` 서브클래스 추가 (Task 5) |
| 5 | 라우트에서 commit 없음 | 라우트가 서비스 호출 후 `await db.commit()` 수행 (`goals.py:20`) | 동일하게 라우트에서 commit |
| 6 | signup 응답에 `onboarding_completed` 추가 | signup은 `TokenResponse`(토큰만) 반환. 유저 정보는 `GET /auth/me`의 `UserResponse` | `onboarding_completed`는 **`UserResponse`(/auth/me)** 에 추가 권장 (§6 결정 필요) |
| 7 | Enum 위주 스키마 | 기존 스키마는 `Literal` 사용 (`goal.py`, `run.py:9`) | injuries dict 키 등 **Enum이 필요한 곳만 Enum**, 나머지는 `Literal` 허용. `preferred_types`는 기존 `RunType`(`app/schemas/run.py:9`) 재사용 |
| 8 | 신규 `BEGINNER_GUARD` 문자열 | `rule_engine.py:131`에 이미 `BEGINNER_GUARD`(총 러닝 <10회) 존재 | **코드 중복 주의** — 프로필 경험레벨 룰은 별도 code(`PROFILE_BEGINNER_GUARD` 등)로 구분 |

---

## 1. 요약

회원가입 유저가 4단계 온보딩(경험/훈련습관/병행운동/부상)으로 `runner_profile`(JSONB)을
제출하면, 코칭 엔진의 Context Assembler가 이를 주입하고 Rule Engine이 프로필 기반 하드
제약(경험레벨·시간·요일·병행운동·부상)을 결정론적으로 추가한다. LLM은 제약 안에서만
세션을 채운다. 온보딩 미완료 유저는 `/coach/recommend` 호출 시 403(`ONBOARDING_REQUIRED`).

---

## 2. 미러링할 기존 패턴

| 범주 | 소스 | 패턴 |
|------|------|------|
| 모델(JSONB) | `app/models/coaching_session.py:21`, `app/models/run.py:38` | `mapped_column(JSONB, nullable=True)`, PG dialect import |
| 모델(Boolean 기본값) | `app/models/weekly_plan.py:22` | `server_default=sa.text(...)` 로 기본값 |
| 마이그레이션 | `alembic/versions/7a0cb6ee1f48_create_users.py` | 수동 리비전, `down_revision` 체이닝 |
| 스키마 | `app/schemas/goal.py` | `BaseModel`, `Field(...)` 제약, `model_validator`, `ConfigDict(from_attributes=True)` |
| 리포지토리 | `app/repositories/goal_repo.py` | 무상태 클래스, `session` 첫 인자, `flush`+`refresh` |
| 서비스 | `app/services/goal_service.py:9` | 모듈 레벨 `_repo = ...()`, `_svc` 싱글턴, 메서드에 `session` 전달 |
| 라우트 | `app/api/goals.py` | `APIRouter(prefix=...)`, `_svc` 싱글턴, `get_current_user`, 라우트 내 `db.commit()`, `response_model` |
| 예외 | `app/core/exceptions.py` | `AppException` 서브클래스 (code/message/http_status) |
| 라우터 등록 | `app/main.py:9,57-63` | `from app.api import ...`, `app.include_router(...)` |
| 코칭 컨텍스트 | `app/graph/nodes/context_assembler.py:60-83` | partial dict 반환, 리포지토리 조회 |
| 룰 엔진 | `app/graph/nodes/rule_engine.py:140` | 순수 함수 `_check_*` → `{"code","message"}` dict 리스트 |
| 룰 노드 | `app/graph/nodes/rule_engine_node.py` | `evaluate_rules(state["context"])` → `{"constraints": ...}` |
| 프롬프트 | `app/graph/prompts.py` | `COACH_SYSTEM_PROMPT` 문자열, `{constraints}` 포맷 (`{{ }}` 이스케이프) |
| 테스트 | `tests/conftest.py`, `tests/test_goals.py` | `client`+`auth_headers` fixture, ASGI AsyncClient, dependency override |

---

## 3. 변경 파일 목록

### 신규 파일
| 파일 | 목적 |
|------|------|
| `app/schemas/runner_profile.py` | Enum + Pydantic 스키마 (Create/Update/Response) |
| `app/repositories/user_repo.py` | `UserRepository.get/update` (신규 — §0-3) |
| `app/services/profile_service.py` | 프로필 비즈니스 로직 |
| `app/api/profile.py` | `/users/profile` CRUD 라우트 |
| `app/graph/nodes/profile_rules.py` | 프로필 기반 룰 (`{"code","message"}` 반환) |
| `app/graph/nodes/profile_rules_node.py` | `apply_profile_rules` 노드 (별도 파일 권장) |
| `alembic/versions/xxxx_add_runner_profile.py` | 마이그레이션 |
| `tests/test_profile.py` | 온보딩/조회/수정 + 403 플로우 테스트 |
| `tests/test_profile_rules.py` | 프로필 룰 단위 테스트 |

### 수정 파일
| 파일 | 변경 |
|------|------|
| `app/models/user.py` | `runner_profile` JSONB, `onboarding_completed` Boolean 컬럼 추가 |
| `app/core/exceptions.py` | `ProfileAlreadyExists`(409), `ProfileNotFound`(404), `OnboardingRequired`(403) 추가 |
| `app/dependencies.py` | `require_onboarding` 의존성 추가 |
| `app/main.py` | `profile` 라우터 등록 |
| `app/schemas/auth.py` | `UserResponse`에 `onboarding_completed` 추가 (§6 결정) |
| `app/graph/nodes/context_assembler.py` | `runner_profile` + `is_available_day` 컨텍스트 추가 |
| `app/graph/coach_graph.py` | `apply_profile_rules` 노드 삽입 |
| `app/graph/prompts.py` | 시스템 프롬프트에 러너 프로필 섹션 추가 |
| `app/api/coach.py` | `/recommend`에 `require_onboarding` 적용 |

> `app/graph/state.py`는 프로필이 `context`(dict) 안에 들어가므로 **변경 불필요**.

---

## 4. 작업 순서 (Task 단위)

### Task 1 — DB 모델 + 마이그레이션
- **작업**:
  - `app/models/user.py`에 컬럼 2개 추가:
    ```python
    runner_profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )
    ```
  - 수동 Alembic 리비전 (`alembic history`로 현재 head 확인 후 `down_revision` 체인).
- **미러**: `coaching_session.py:21`(JSONB), `weekly_plan.py:22`(server_default)
- **검증**: `alembic upgrade head` 성공, `alembic downgrade -1` 롤백 성공

### Task 2 — Enum + Pydantic 스키마 (`app/schemas/runner_profile.py`)
- **작업**: 설계 §2.3/§3의 Enum·스키마 정의. 단:
  - `preferred_types: list[RunType]` — `from app.schemas.run import RunType` 재사용 (신규 정의 금지).
  - `available_days` — `Literal["mon",...,"sun"]` 리스트 권장(설계는 `list[str]`).
  - `injuries.status` 기본값: 모든 부위 `NONE` (설계 §3 `default_factory`).
  - JSONB 직렬화를 위해 서비스에서 `model_dump(mode="json")` 사용 → Enum이 문자열로 저장되게.
- **미러**: `app/schemas/goal.py` (Field 제약, model_validator, ConfigDict)
- **검증**: `mypy app/schemas/runner_profile.py`, import 성공

### Task 3 — UserRepository (`app/repositories/user_repo.py`)
- **작업**: `get(session, user_id) -> User | None`, `update(session, user, data: dict) -> User`.
- **미러**: `app/repositories/goal_repo.py:43` (`update`가 `setattr`+`flush`+`refresh`)
- **검증**: `mypy app`

### Task 4 — ProfileService (`app/services/profile_service.py`)
- **작업**: 모듈 레벨 `_repo = UserRepository()`. 메서드: `create_profile`, `update_profile`, `get_profile` — 모두 첫 인자 `session`.
  - `create_profile`: `onboarding_completed`가 이미 True면 `raise ProfileAlreadyExists()`.
  - `update_profile`: 기존 `runner_profile` 위에 `model_dump(exclude_none=True)` **섹션 단위 머지**(설계 §5). 프로필 없으면 `ProfileNotFound`.
  - `get_profile`: 라우트 규약에 맞춰 `None` 반환 후 라우트 404 또는 `ProfileNotFound`로 통일.
- **주의**: 설계의 `Depends()` DI/`user_repo` 주입 대신 §0-2 패턴 사용.
- **미러**: `app/services/goal_service.py`
- **검증**: `mypy app`

### Task 5 — 예외 추가 (`app/core/exceptions.py`)
- **작업**:
  ```python
  class ProfileAlreadyExists(AppException):
      def __init__(...): super().__init__("PROFILE_ALREADY_EXISTS", ..., 409)
  class ProfileNotFound(AppException):
      def __init__(...): super().__init__("PROFILE_NOT_FOUND", ..., 404)
  class OnboardingRequired(AppException):
      def __init__(...): super().__init__("ONBOARDING_REQUIRED", ..., 403)
  ```
- **미러**: `Conflict`, `NotFound` (`exceptions.py:18,13`)
- **검증**: `error_handlers`가 `AppException`을 자동 매핑하는지 (`tests/test_error_handlers.py`)

### Task 6 — 라우트 (`app/api/profile.py`) + 등록
- **작업**: `APIRouter(prefix="/users", tags=["profile"])`, `_svc = ProfileService()`.
  - `POST /profile` (201), `GET /profile`, `PATCH /profile`.
  - 각 라우트: `get_current_user` 의존, 쓰기 후 `await db.commit()`.
  - `app/main.py`에 `from app.api import ... profile` + `include_router`.
- **미러**: `app/api/goals.py`
- **검증**: `uvicorn` 기동 후 `/docs`에 엔드포인트 노출

### Task 7 — 온보딩 게이트 (`app/dependencies.py` + `coach.py`)
- **작업**: `require_onboarding(user = Depends(get_current_user))` → 미완료 시 `raise OnboardingRequired()`. `app/api/coach.py`의 `/recommend`에서 `get_current_user` 대신 `require_onboarding` 사용.
- **주의**: 설계의 raw `HTTPException` 대신 `OnboardingRequired` (§0-4).
- **미러**: `app/dependencies.py:26` (`get_current_user`)
- **검증**: 온보딩 미완료 토큰으로 `/coach/recommend` → 403

### Task 8 — Context Assembler에 프로필 주입
- **작업**: `context_assembler.py`에서 `UserRepository.get`으로 유저 조회 → `context["runner_profile"]`(설계 §7.1 매핑) + `context["is_available_day"]` 추가. `_is_today_available(available_days)` 헬퍼 추가.
  - **프로필 None 방어**: 온보딩 게이트가 있어 `/coach` 경로에선 항상 존재하지만 `.get(...)` 방어 코딩 유지.
- **미러**: `context_assembler.py:60-83`
- **검증**: 단위 테스트에서 context에 키 존재 확인

### Task 9 — 프로필 룰 (`app/graph/nodes/profile_rules.py`)
- **작업**: 설계 §7.2 룰을 **`{"code","message"}` dict 리스트**로 반환하는 순수 함수 `evaluate_profile_rules(context) -> list[dict[str,str]]`. 경험레벨/시간/요일/병행운동/부상(caution·severe 하드, mild 참고).
  - 기존 `BEGINNER_GUARD`(`rule_engine.py:131`)와 code 충돌 방지 → `PROFILE_BEGINNER_GUARD` 등 접두.
  - 노드(`apply_profile_rules`)는 `{"constraints": state["constraints"] + evaluate_profile_rules(state["context"])}` 반환.
- **미러**: `app/graph/nodes/rule_engine.py:140` (`evaluate_rules`), `rule_engine_node.py`
- **검증**: `tests/test_profile_rules.py` (초급+무릎 caution → 인터벌 제약 존재)

### Task 10 — Graph 노드 삽입 (`app/graph/coach_graph.py`)
- **작업**: `apply_profile_rules` 노드 추가, 엣지 `apply_rules → apply_profile_rules → call_coach` (설계 §7.3).
- **미러**: `coach_graph.py:18-29`
- **검증**: 그래프 컴파일 성공, 코칭 통합 테스트 통과

### Task 11 — 시스템 프롬프트 (`app/graph/prompts.py`)
- **작업**: 설계 §7.4 러너 프로필 섹션을 `COACH_SYSTEM_PROMPT`에 추가. 중괄호 이스케이프(`{{ }}`) 규칙 유지.
- **미러**: `app/graph/prompts.py`
- **검증**: `COACH_SYSTEM_PROMPT.format(constraints="...")` 예외 없이 동작

### Task 12 — auth 응답 (`app/schemas/auth.py`) — §6 결정 후
- **작업**: `UserResponse`에 `onboarding_completed: bool` 추가. (`GET /auth/me`로 프론트가 온보딩 여부 확인)
- **미러**: `app/schemas/auth.py:23`
- **검증**: `/auth/me` 응답에 필드 포함

### Task 13 — 테스트
- **작업**:
  - `tests/test_profile.py`: 온보딩 제출(201) → 재제출(409) → 조회(200) → PATCH 부분수정(200) → 미완료 유저 `/coach`(403).
  - `tests/test_profile_rules.py`: 경험/시간/요일/병행/부상 각 룰 단위 검증. 특히 설계 §11의 “초급+무릎주의 → 인터벌 안 나옴”, “비훈련일 → 선택 러닝만”.
  - `conftest.py`의 `auth_headers`는 온보딩 미완료 유저 생성 → 온보딩 완료 fixture(`onboarded_headers`) 추가 및 기존 `test_coach.py` 갱신 필요.
- **미러**: `tests/test_goals.py`, `tests/test_rule_engine.py`, `tests/conftest.py`
- **검증**: `pytest -v`, 커버리지 80%+

---

## 5. 검증 커맨드

```bash
alembic upgrade head                           # 마이그레이션 적용
alembic downgrade -1 && alembic upgrade head   # 롤백 왕복
ruff format . && ruff check .                  # 포맷/린트
mypy app                                        # 타입 체크
pytest -v                                       # 전체 테스트
pytest tests/test_profile.py tests/test_profile_rules.py -v
pytest --cov=app --cov-report=term-missing      # 커버리지 80%+
```

---

## 6. 열린 결정 사항 (구현 착수 전 확인)

1. **signup 응답 vs /auth/me**: 설계는 signup 응답에 `onboarding_completed` 추가를 명시하나,
   현재 signup은 `TokenResponse`(토큰만) 반환. 권장은 `UserResponse`(/auth/me)에 추가.
2. **프로필 룰 위치**: 별도 노드(`apply_profile_rules`, 설계 방식) vs `evaluate_rules` 통합.
   → 설계대로 별도 노드 권장(관심사 분리·테스트 용이).
3. **기존 `BEGINNER_GUARD` 중복**: 총 러닝<10회 룰과 경험레벨=beginner 룰 동시 발생 가능.
   → 두 code 분리 공존 vs 프로필 우선 통합 결정.
4. **get_profile 미존재 처리**: `None` 반환 후 라우트 404 vs 서비스 `ProfileNotFound` — 규약 통일.

---

## 7. 리스크

| 리스크 | 가능성 | 완화 |
|--------|--------|------|
| 설계 예시 코드 그대로 복붙 → 제약 포맷/DI 불일치로 런타임 오류 | 높음 | §0 표를 구현 전 필수 체크리스트로 사용 |
| `constraints` 문자열 vs dict 혼용 → `llm_coach.py:28` KeyError | 중간 | 프로필 룰 반드시 `{"code","message"}` 반환 |
| 마이그레이션 `down_revision` 체인 오류 | 중간 | `alembic history`로 현재 head 확인 후 작성 |
| 기존 유저(프로필 없음)가 `/coach` 호출 → context KeyError | 중간 | `require_onboarding` 게이트 + assembler 방어 `.get()` |
| `injuries.status` Enum 키 JSONB 직렬화 문제 | 낮음 | `model_dump(mode="json")`로 문자열 직렬화 |
| 테스트 `auth_headers`가 온보딩 미완료라 기존 coach 테스트 깨짐 | 중간 | 온보딩 완료 fixture 추가 및 기존 coach 테스트 갱신 |

---

## 8. 완료 기준 (Acceptance)

- [ ] `POST/GET/PATCH /users/profile` 동작, 에러코드(409/404) 정확
- [ ] 온보딩 미완료 유저 `/coach/recommend` → 403 `ONBOARDING_REQUIRED`
- [ ] 코칭 context에 `runner_profile`·`is_available_day` 포함
- [ ] 프로필 룰이 `{"code","message"}` 형태로 constraints에 병합됨
- [ ] 초급+무릎 caution 프로필 → 인터벌/장거리 제약 발생 검증
- [ ] 비훈련일 → 선택 러닝만 제안 제약 발생 검증
- [ ] `ruff`/`mypy`/`pytest` 모두 통과, 커버리지 80%+
- [ ] 설계 예시가 아닌 **실제 코드베이스 패턴**으로 구현됨 (§0 준수)
```
