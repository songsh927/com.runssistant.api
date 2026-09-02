# Sprint 2 실행계획 — Goals + Weekly Plans

## Context

Sprint 0(auth)·Sprint 1(runs/stats/weather)이 완료된 상태다(21 tests passing).
설계 문서 §9의 Sprint 2는 **목표(goals)와 주간 플랜(weekly_plans)** 을 추가해,
"사용자가 주간 목표를 세우면 러닝 기록이 플랜 진행률에 자동 반영"되는 루프를 완성한다.

이 스프린트가 중요한 이유는 Sprint 3의 AI 코칭 엔진이 **읽고 조정할 대상**을 만들기 때문이다.
LangGraph의 Context Assembler는 goals/weekly_plans를 읽고, Plan Updater는 weekly_plans를 쓴다.
즉 Sprint 2는 AI가 붙기 전에 **결정론적 코드로 플랜의 뼈대와 갱신 규칙을 먼저 확정**하는 단계다.

**완료 기준(설계 §9):** 목표 30km/주 설정 → 5km 러닝 기록 → 플랜에 25km 잔여 반영

---

## 확정된 설계 결정

설계 문서가 명시하지 않아 이번에 확정한 사항:

| # | 결정 | 근거 |
|---|------|------|
| 1 | **플랜 자동 생성 = 규칙 기반 템플릿** | AI는 Sprint 3에 들어온다. `weekly_km_target`을 80/20 법칙으로 주 4세션에 배분. Sprint 3의 AI는 "생성"이 아니라 이 플랜의 "조정"을 맡게 되어 설계 §5.4("AI 코칭 시 자동 갱신")와 자연스럽게 이어짐 |
| 2 | **세션 매칭 = 요일 매칭 + 미계획은 추가** | `run_date`의 요일에 pending 세션이 있으면 completed 처리(같은 `run_type` 우선), 없으면 `unplanned: true` 세션으로 append. 실제 수행량이 항상 플랜에 남음 |
| 3 | **미차이 항목 전부 보완** | `WeeklyStats`의 `target_km`/`progress_pct`/`avg_rpe` + `runs`의 `UNIQUE (user_id, run_date, created_at)` |

**파생 결정:**

- **`completed_km`/`remaining_km`/`progress_pct`는 `runs`에서 집계**한다. `planned_sessions[].status`에서 합산하지 않는다.
  → run이 삭제·수정되어도 숫자는 항상 정확하고, 세션 status는 UI용 best-effort 상태로만 둔다.
- **목표 생성 시 이번 주 플랜에 completed 세션이 없으면 그 플랜을 삭제**한다. 다음 `/plans/current` 호출에서 새 목표 기준으로 재생성된다.
  → 플랜 생성 경로를 하나로 유지(재생성 로직 중복 없음)하고, "러닝 먼저 기록 → 목표 나중 설정" 순서에서도 플랜이 새 목표를 반영한다.
- **소유권 위반은 404**(`NotFound`). 기존 `test_other_user_cannot_access_run` 규약을 그대로 따르고 `Forbidden`/403은 만들지 않는다.
- **필드 검증 오류는 422**(Pydantic 기본), **비즈니스 규칙 위반은 400**(`ValidationError` → 통일 에러 봉투). 기존 `test_create_run_invalid_run_type`이 422를 기대하는 것과 일치.

---

## 데이터 모델

### `goals` (설계 §4.3)

`TimestampMixin` 사용(created_at + updated_at).

```python
__table_args__ = (
    sa.CheckConstraint("goal_type IN ('weekly_volume','race')", name="ck_goals_goal_type"),
    sa.CheckConstraint("status IN ('active','completed','abandoned')", name="ck_goals_status"),
    sa.CheckConstraint(
        "weekly_km_target IS NULL OR weekly_km_target > 0", name="ck_goals_weekly_km_positive"
    ),
    sa.Index(
        "idx_goals_user_active",
        "user_id",
        postgresql_where=sa.text("status = 'active'"),  # 부분 인덱스
    ),
)
```

컬럼: `id`(uuid_pk), `user_id`(FK), `goal_type` String(20), `weekly_km_target` Numeric(5,1) NULL,
`race_name` String(200) NULL, `race_date` Date NULL, `race_target_time` Integer NULL,
`race_distance_km` Numeric(5,2) NULL, `status` String(20) server_default `'active'`.

### `weekly_plans` (설계 §4.4)

`TimestampMixin` 사용.

```python
__table_args__ = (sa.UniqueConstraint("user_id", "week_start", name="unique_user_week"),)
```

컬럼: `id`, `user_id`(FK), `goal_id`(FK `goals.id`, nullable), `week_start` Date,
`planned_sessions` JSONB NOT NULL `server_default=text("'[]'::jsonb")`,
`total_planned_km` Numeric(5,1) NULL,
`adjustments_log` JSONB `server_default=text("'[]'::jsonb")`.

### `planned_sessions` JSONB 스키마 (이번에 확정)

```json
{
  "day": "tue",                  // mon|tue|wed|thu|fri|sat|sun  (date.weekday() 인덱스)
  "type": "easy",                // runs.run_type 어휘와 동일: easy|tempo|interval|long_run|race|recovery
  "distance_km": 6.0,
  "pace_range": null,            // Sprint 2는 페이스 모델 없음 → null, Sprint 3 AI가 채움
  "status": "pending",           // pending|recommended|completed  (recommended는 Sprint 3 AI가 사용)
  "actual_distance_km": null,    // completed 시 실제 거리
  "run_id": null,                // completed 시 해당 run의 id (Sprint 3 replay/디버깅용)
  "unplanned": false             // 계획에 없던 러닝으로 추가된 세션이면 true
}
```

### `runs` UNIQUE 제약 추가

`app/models/run.py`의 `__table_args__`에
`sa.UniqueConstraint("user_id", "run_date", "created_at", name="unique_user_run_date")` 추가.

---

## 구현 단계

### 1. 모델

- `app/models/goal.py` — `Goal(TimestampMixin, Base)`
- `app/models/weekly_plan.py` — `WeeklyPlan(TimestampMixin, Base)`
- `app/models/run.py` — `unique_user_run_date` 제약 추가
- `app/models/__init__.py` — `Goal`, `WeeklyPlan` re-export + `__all__` 추가
  **(필수: `alembic/env.py`가 `import app.models` 부수효과로만 모델을 인식한다)**

`app/models/run.py`의 기존 스타일 그대로 — `import sqlalchemy as sa`로 제약/인덱스, 컬럼 타입은 `sqlalchemy`에서 직접 import, `Mapped[...]` 어노테이션, `uuid_pk()`.

### 2. 마이그레이션

```bash
uv run alembic revision --autogenerate -m "create_goals_and_weekly_plans"
```

`down_revision`이 `'f94c142bef11'`인지 확인. **autogenerate 결과를 반드시 검토**할 것:

- 부분 인덱스(`postgresql_where`)가 `op.create_index(..., postgresql_where=...)`로 나왔는가
- JSONB `server_default '[]'::jsonb`가 누락되지 않았는가
- `runs`의 UNIQUE는 `op.create_unique_constraint('unique_user_run_date', 'runs', [...])`로 나오는가
- `downgrade()`가 역순으로 온전한가

> 테스트는 `Base.metadata.create_all`을 쓰므로 **마이그레이션 버그를 테스트가 잡아주지 않는다.**
> 반드시 `upgrade head` → `downgrade -1` → `upgrade head` 왕복을 수동 검증한다.

### 3. 스키마

- `app/schemas/goal.py` — `GoalType`/`GoalStatus` `Literal` 별칭, `GoalCreate`, `GoalUpdate`(전 필드 `X | None = None`), `GoalStatusUpdate`, `GoalResponse`(`ConfigDict(from_attributes=True)`)
  - `GoalCreate`에 `@model_validator(mode="after")`: `weekly_volume`이면 `weekly_km_target` 필수, `race`면 `race_name`/`race_date`/`race_distance_km` 필수 → 422
- `app/schemas/plan.py` — `PlannedSession`, `WeeklyPlanResponse`
- `app/schemas/stats.py` — `WeeklyStats`에 필드 추가. **기존 `get_trend` 호출이 깨지지 않도록 기본값 `None`을 준다:**
  ```python
  target_km: float | None = None
  progress_pct: int | None = None
  avg_rpe: float | None = None
  ```
  필드 순서는 설계 §5.6 응답 예시에 맞춘다(week_start, total_km, target_km, progress_pct, session_count, avg_pace_sec, avg_pace_display, avg_rpe, run_type_breakdown).

### 4. 리포지토리

`app/repositories/run_repo.py` 스타일 그대로 — **`__init__` 없음, `session`을 매 메서드 첫 인자로 전달, 커밋하지 않음, `flush()`+`refresh()`.**

- `app/repositories/goal_repo.py` — `create`, `get_by_id(session, goal_id, user_id)`, `list_goals(session, user_id, status=None)`, `get_active(session, user_id)`, `update(session, goal, data)`
- `app/repositories/plan_repo.py` — `create`, `get_by_week(session, user_id, week_start)`, `list_recent(session, user_id, weeks)`, `update(session, plan, data)`, `delete(session, plan)`

`get_active`는 `status == "active"` 필터 + `order_by(Goal.created_at.desc()).limit(1)`.

### 5. 서비스

**`app/services/plan_service.py`** — 이번 스프린트의 핵심.

모듈 레벨 순수 함수(테스트에서 직접 import하므로 언더스코어 없는 공개 이름):

```python
_DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")  # date.weekday() 인덱스

_TEMPLATE = (  # 80/20: 고강도(tempo) 20%, 이지/롱런 80%
    ("tue", "easy", 0.20),
    ("thu", "tempo", 0.20),
    ("sat", "long_run", 0.40),
    ("sun", "easy", 0.20),
)


def build_planned_sessions(weekly_km_target: float | None) -> list[dict[str, Any]]:
    """목표 주간 거리를 4세션으로 배분. 반올림 잔차는 마지막 세션에 흡수시켜
    distance_km 합이 weekly_km_target과 정확히 일치하게 만든다."""
```

`weekly_km_target`이 `None`이거나 `<= 0`이면 `[]` 반환.

`PlanService` 메서드:

| 메서드 | 반환 | 설명 |
|--------|------|------|
| `get_or_create(session, user_id, week_start)` | `WeeklyPlan` (ORM) | 없으면 active goal 기준으로 생성. 내부용 |
| `get_current(session, user_id)` | `WeeklyPlanResponse` | `get_monday(date.today())`로 `get_or_create` |
| `get_by_week(session, user_id, week_start)` | `WeeklyPlanResponse` | 없으면 `NotFound`. 월요일 아니면 `ValidationError` |
| `get_history(session, user_id, weeks=8)` | `list[WeeklyPlanResponse]` | 최근 N주, 오래된 순 |
| `mark_session_completed(session, user_id, run)` | `None` | 결정 #2 매칭 규칙 |
| `unmark_session(session, user_id, run)` | `None` | run 삭제 시 되돌리기 |
| `drop_untouched_current(session, user_id)` | `None` | completed 세션이 없으면 이번 주 플랜 삭제(결정: 목표 생성 시 호출) |

`WeeklyPlanResponse` 조립 시 `_run_repo.get_range(session, user_id, week_start, week_start + 6일)`로
`completed_km` 집계 → `remaining_km = max(0.0, total_planned_km - completed_km)`,
`progress_pct = int(round(completed_km / total_planned_km * 100))` (`total_planned_km` 없거나 0이면 둘 다 `None`).

**`app/services/goal_service.py`** — `create`(기존 active를 abandoned로 전환 후 생성 → `_plan_svc.drop_untouched_current` 호출), `list`, `get_active`, `get`(없으면 `NotFound`), `update`, `update_status`.

active 전환은 대상이 0~1건이므로 bulk `update()` 대신 **조회 후 `setattr` 루프**로 처리한다(`updated_at`의 `onupdate` 확실히 반영, 세션 동기화 이슈 없음).

**`app/services/stats_service.py` 수정** — `_compute_weekly(week_start, runs, target_km=None)`으로 시그니처 확장:

```python
rpes = [r.rpe for r in runs if r.rpe is not None]
avg_rpe = round(sum(rpes) / len(rpes), 1) if rpes else None
progress_pct = int(round(total_km / target_km * 100)) if target_km else None
```

`get_weekly_stats`만 `_goal_repo.get_active`를 조회해 `target_km`을 넘긴다.
`get_trend`는 **그대로 둔다**(주당 goal 조회 N회를 피하고, `TrendPoint`에는 target 필드가 없음).

**`app/services/run_service.py` 수정** — `create_run` 3단계(설계 §6.1) 및 `delete` 연동:

```python
_plan_svc = PlanService()   # WeatherService와 달리 외부 I/O가 없어 DI 불필요, _repo 싱글턴 관례를 따름

async def create_run(...):
    ...
    run = await _repo.create(session, ...)
    await _plan_svc.mark_session_completed(session, user_id, run)
    return run

async def delete(...):
    run = await self.get(session, run_id, user_id)
    await _plan_svc.unmark_session(session, user_id, run)
    await _repo.soft_delete(session, run)
```

### 6. API

- `app/api/goals.py` — `APIRouter(prefix="/goals", tags=["goals"])`, `_svc = GoalService()`
  설계 §5.3의 5개 엔드포인트만: `POST ""`(201), `GET ""`(`?status=`), `GET "/active"`, `PUT "/{goal_id}"`, `PATCH "/{goal_id}/status"`
- `app/api/plans.py` — `GET "/current"`, `GET "/history"`(`?weeks=8`), `GET "/{week_start}"`

  > **라우트 선언 순서 주의:** `/current`와 `/history`를 반드시 `/{week_start}` **앞에** 선언해야 한다.
  > 뒤에 두면 `/{week_start}`가 먼저 매칭된다.

  > **`GET /plans/current`는 생성 시 `await db.commit()`이 필요하다.** 읽기 라우트는 커밋하지 않는 기존 관례에서 벗어나므로 주석으로 이유를 남긴다.

- `app/main.py` — `app.include_router(goals.router)`, `app.include_router(plans.router)` 추가

기존 `app/api/runs.py` 관례 유지: `response_model` 명시, `Depends(get_db)`/`Depends(get_current_user)`,
mutation 후 `await db.commit()`, 응답은 `XResponse.model_validate(obj)`.

---

## 구현 시 주의점

1. **JSONB in-place 변경은 저장되지 않는다 — 이번 스프린트 최대 버그 위험.**
   SQLAlchemy는 `JSONB` 컬럼의 in-place 변경을 추적하지 않는다.
   ```python
   plan.planned_sessions.append(...)  # ❌ 저장 안 됨 (조용히 실패)
   sessions = [dict(s) for s in plan.planned_sessions]
   sessions.append(...)
   plan.planned_sessions = sessions  # ✅ 새 객체 재할당
   ```
   `MutableList.as_mutable(JSONB)` 대신 **재할당 방식**을 쓴다(추가 machinery 없이 명시적).

2. **`Numeric` → `Decimal` 변환.** `goal.weekly_km_target`, `plan.total_planned_km`, `run.distance_km`는 모두 `Decimal`이다. 산술 전에 `float(...)`로 변환한다.

3. **`unique_user_run_date` 제약의 실제 의미.** PostgreSQL `now()`는 트랜잭션 시작 시각이라 **같은 트랜잭션에서 같은 유저·같은 날짜로 run 2건을 insert하면 충돌**한다. API 호출마다 커밋하므로 실사용에서는 문제없다. 다만 `tests/test_runs.py::test_list_runs`가 같은 날짜로 run 3건을 만들므로, 제약 추가 후 이 테스트가 통과하는지 반드시 확인한다.

4. **`unique_user_week` 경합.** 동시 요청 2건이 같은 주 플랜을 생성하면 한쪽이 IntegrityError를 받는다. 단일 사용자 MVP에서는 수용하고 Sprint 4 polish로 미룬다.

5. **`mypy --strict` + `ruff`(line-length 100, `E,F,I,UP,B`).** JSONB를 다루는 코드는 `dict[str, Any]`/`list[dict[str, Any]]`로 명시 타이핑한다. 마이그레이션 파일은 ruff 대상에서 제외되어 있으므로 autogenerate 원형 그대로 두어도 된다.

---

## 테스트

기존 관례 유지: `@pytest.mark.asyncio` 명시, 파일 로컬 `_make_user()`/`_signup(client)` 헬퍼, `resp` → `body` → `assert` 구조.

**`tests/test_goals.py`** (신규)
- `test_create_weekly_volume_goal_success`
- `test_create_race_goal_success`
- `test_create_goal_abandons_previous_active`
- `test_create_weekly_volume_goal_without_target_rejected` (422)
- `test_list_goals_filter_by_status`
- `test_get_active_goal` / `test_get_active_goal_none`
- `test_update_goal` / `test_update_goal_status`
- `test_other_user_cannot_access_goal` (404)

**`tests/test_plans.py`** (신규)
- `test_build_planned_sessions_sums_to_target` — 순수 함수 단위 테스트, 여러 target 값 파라미터화
- `test_current_plan_auto_created_from_goal` — 30km → 4세션, 합 30.0
- `test_current_plan_without_goal_is_empty`
- `test_current_plan_is_idempotent` — 두 번 호출해도 같은 `id`
- `test_run_marks_planned_session_completed`
- `test_unplanned_run_appended_to_plan` — `unplanned: true`
- **`test_goal_30km_then_5km_run_leaves_25km_remaining`** — 설계 §9 완료 기준
- `test_delete_run_reverts_session_status`
- `test_new_goal_regenerates_untouched_plan`
- `test_get_plan_by_week_not_found` (404) / `test_get_plan_by_non_monday_rejected` (400)
- `test_plans_history`
- `test_other_user_cannot_access_plan` (404)

**`tests/test_stats.py`** (추가)
- `test_weekly_stats_includes_target_and_progress`
- `test_weekly_stats_avg_rpe`
- `test_weekly_stats_target_none_without_goal`

---

## 검증

```bash
docker compose up -d                      # postgres + redis (이미 기동 중)
uv run alembic upgrade head
uv run alembic downgrade -1 && uv run alembic upgrade head   # 마이그레이션 왕복
uv run ruff format . && uv run ruff check .
uv run mypy app
uv run pytest -v                          # 기존 21개 + 신규 전부 통과
```

**완료 기준 수동 검증** (`uvicorn app.main:app --reload --port 8000`):

```bash
TOKEN=$(curl -s localhost:8000/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"s2@example.com","password":"password123","name":"S2","location":"Seoul"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

# 1. 목표 30km/주
curl -s localhost:8000/goals -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"goal_type":"weekly_volume","weekly_km_target":30}'

# 2. 플랜 자동 생성 확인 → 4세션, total_planned_km=30.0, remaining_km=30.0
curl -s localhost:8000/plans/current -H "Authorization: Bearer $TOKEN"

# 3. 5km 러닝 기록 (이번 주 화요일)
curl -s localhost:8000/runs -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"run_date":"<이번주 화요일>","distance_km":"5.00","duration_sec":1800,"run_type":"easy","rpe":5}'

# 4. ✅ remaining_km == 25.0, tue 세션 status == "completed"
curl -s localhost:8000/plans/current -H "Authorization: Bearer $TOKEN"

# 5. ✅ target_km=30.0, progress_pct=17, avg_rpe=5.0
curl -s localhost:8000/stats/weekly -H "Authorization: Bearer $TOKEN"
```

---

## 범위 밖 (Sprint 3 이후)

- **run 수정 시 플랜 재동기화** — `run_date`가 다른 주로 바뀌는 경우의 이동 처리. `completed_km`는 runs에서 집계하므로 숫자는 항상 정확하고, `planned_sessions[].status`만 드리프트할 수 있다.
- **`pace_range` 산출** — Sprint 2에는 페이스 모델이 없어 `null`. Sprint 3 LLM Coach가 채운다.
- **`adjustments_log` 기록** — 컬럼과 기본값만 만들어 두고, 실제 append는 Sprint 3 Plan Updater가 담당한다.
- **`rest` 세션 타입** — 템플릿은 휴식일을 세션으로 만들지 않고 생략한다. Rule Engine이 rest를 강제하는 Sprint 3에서 도입.
- **`coaching_sessions` 테이블** — Sprint 3.
