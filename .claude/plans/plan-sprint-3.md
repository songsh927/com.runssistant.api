# Sprint 3 실행계획 — AI Coaching Engine (LangGraph)

## Context

Sprint 0~2가 완료된 상태다(56 tests passing). 지금까지는 전부 결정론적 CRUD였고,
**이 스프린트가 이 제품의 존재 이유**다 — 설계 §1이 말하는 "디바이스 연동 없이 코칭 가치를 먼저 검증"의
그 코칭이 여기서 처음 동작한다.

Sprint 2가 만들어 둔 `goals` / `weekly_plans`를 LangGraph 파이프라인이 읽고 쓴다.
Context Assembler가 runs·goals·plans·weather를 모아 컨텍스트를 만들고, Rule Engine이 안전 제약을
결정론적으로 계산한 뒤, LLM이 그 제약 **안에서만** 세션 내용을 채우고, Plan Updater가 결과를
`weekly_plans`에 반영하고 `coaching_sessions`에 스냅샷을 남긴다.

**완료 기준(설계 §9):** RPE 입력 → AI가 컨텍스트 기반 구체적 세션 추천 반환

---

## 확정된 설계 결정

| # | 결정 | 근거 |
|---|------|------|
| 1 | **LLM 실패 = 503 `COACHING_UNAVAILABLE`** | 설계 §10 그대로. 코칭이 이 앱의 핵심 가치라 조용히 열화된 추천을 주는 것보다 솔직히 실패하는 편이 낫다. 실패 시 `coaching_sessions` 기록도 남기지 않는다 |
| 2 | **JSON 강제 모드 + 관대한 추출 + 1회 재시도** | 로컬 기본 모델 gemma3:4b가 코드펜스·설명문을 붙이는 일이 잦다. provider 단에서 JSON을 강제하고, 깨지면 공통 추출 헬퍼로 구제하고, 그래도 안 되면 1회만 재호출 |
| 3 | **provider 3개 전부 구현** | 설계 §6 + §9의 "Bedrock 연동". Bedrock/OpenAI는 자격증명이 없어 **미검증 상태로 남는다는 점을 명시**하고 진행 |

### 설계 문서 자체의 공백 — 이번에 함께 고칠 것

| 위치 | 문제 | 조치 |
|------|------|------|
| §4.5 `coaching_sessions` SQL | `model_used` 컬럼이 없다. 그런데 §11.4와 `CLAUDE.md`는 "모델별 품질 비교를 위해 계속 기록하라"고 요구 | 컬럼 추가 + 설계 §4.5 SQL 수정 |
| §7.3 시스템 프롬프트 | `"run_type": "easy\|tempo\|interval\|long\|rest"` — `long`이 `runs.run_type` 어휘(`long_run`)와 불일치 | 프롬프트를 `long_run`으로 교정 + 포매터에 방어적 정규화(`long`→`long_run`) |
| `rest` 타입 | `runs.run_type` CHECK에 없음 | **정상이다.** `rest`는 `planned_sessions[].type`에만 존재하고 실제 run으로 기록되지 않는다. JSONB라 CHECK 제약이 없어 마이그레이션 불필요. Sprint 2 계획이 "Sprint 3에서 rest 도입"으로 이미 예고한 지점 |

### 파생 결정

- **Rule Engine 출력은 문자열이 아니라 구조체.** 설계 §6.8은 `"\n".join(constraints)`로 문자열을 암시하지만,
  §4.4의 `adjustments_log`가 `{"reason":"VOLUME_EXCEEDED", ...}`처럼 **룰 코드**를 요구한다.
  `{"code": "VOLUME_EXCEEDED", "message": "..."}` 형태로 만들어 프롬프트에는 `message`만 join하고,
  `adjustments_log`와 `coaching_sessions.constraints`에는 구조체 그대로 저장한다.
- **`LLMProvider.invoke` 시그니처는 §6.1 그대로 유지.** JSON 모드 플래그를 파라미터로 추가하지 않고,
  각 provider 구현 내부에서 항상 JSON을 강제한다(이 앱의 LLM 용도는 JSON 코칭 출력 하나뿐).
- **그래프는 DI로 주입한다.** `get_coach_graph()`를 `dependencies.py`에 두고 테스트에서
  `FakeLLMProvider`로 override — 기존 `get_weather_service` 선례와 동일한 패턴.
- **`CoachState`가 `AsyncSession`을 들고 다닌다.** Context Assembler와 Plan Updater가 DB를 직접 만져야 하는데
  설계 §7.1이 둘을 노드로 못박았기 때문이다. 노드는 repository/service를 호출한다.

---

## 아키텍처

```
POST /coach/recommend
  └─ app/api/coach.py
       └─ CoachService                      (app/services/coach_service.py)
            └─ compiled graph               (app/graph/coach_graph.py)
                 ├─ 1. Context Assembler    StatsService·PlanService·repos·WeatherService 재사용
                 ├─ 2. Rule Engine          순수 함수, 9개 룰 → constraints
                 ├─ 3. LLM Coach            LLMProvider 주입, 파싱·검증·1회 재시도
                 ├─ 4. Plan Updater         weekly_plans 갱신 + coaching_sessions insert
                 └─ 5. Response Formatter   설계 §5.5 페이로드 조립
```

### 재사용할 기존 코드 (새로 만들지 말 것)

| 필요한 것 | 이미 있는 것 |
|---|---|
| 주간 완료 km / target / progress / avg_rpe | `StatsService.get_weekly_stats` (`app/services/stats_service.py:38`) |
| 이번 주 플랜 + remaining_km | `PlanService.get_current` (`app/services/plan_service.py`) |
| 세션 JSONB 갱신 패턴(재할당) | `PlanService.mark_session_completed` — `apply_recommendation`도 같은 방식으로 |
| 활성 목표 | `GoalRepository.get_active` |
| 기간 내 러닝 | `RunRepository.get_range` |
| 날씨 (Redis 30분 캐시 + graceful None) | `WeatherService.get_current` |
| 페이스 구간 스키마 | **`PaceRange`** (`app/schemas/plan.py`) — LLM 출력 검증에 그대로 재사용 |
| 월요일 계산 / 페이스 포맷 | `get_monday`, `format_pace` (`app/core/pace.py`) |
| 에러 봉투 | `CoachingUnavailable` (`app/core/exceptions.py`) — 이미 정의만 되어 있고 미사용 |

---

## 데이터 모델

### `coaching_sessions` (설계 §4.5 + `model_used`)

`Run`과 동일하게 `TimestampMixin` 없이 `created_at`만 직접 선언(추천은 불변 기록).

```python
__table_args__ = (
    sa.CheckConstraint("user_feedback BETWEEN 1 AND 5", name="ck_coaching_sessions_feedback"),
    sa.Index("idx_coaching_user_date", "user_id", sa.text("created_at DESC")),
)

id: uuid_pk()
user_id: FK users.id, not null
context_snapshot: JSONB not null      # AI에 넘긴 context 전체 (§11.3 — 디버깅·분석·재현용, 보존할 것)
constraints: JSONB nullable           # rule engine 구조체 리스트
recommendation: JSONB not null        # LLM 응답
model_used: String(100) nullable      # "ollama/gemma3:4b" 등 (§11.4)
user_feedback: Integer nullable       # 1-5, runs.rpe 선례를 따라 SmallInteger 대신 Integer
created_at: TIMESTAMPTZ server_default now()
```

`runs.rpe`가 SMALLINT 설계에도 `Integer`로 구현된 선례를 따른다.

---

## 구현 단계

### 1. 의존성 + 설정

`pyproject.toml`에 `langgraph>=0.2.0`, `boto3>=1.34.0` 추가.
`config.py`는 LLM 설정이 **이미 전부 들어있다** — 수정 불필요.

> `uv run`이 dev extra를 제거하므로 `uv sync --extra dev` 후 `.venv/bin/*`를 직접 호출한다.

### 2. LLM provider 계층 (`app/llm/`)

- `base.py` — 설계 §6.1 그대로. `LLMResponse(content, model, usage)`, `LLMProvider` ABC의
  `invoke(system, user_message, temperature=0.7, max_tokens=2048)` / `get_model_name()`
- `parsing.py` — **순수 함수 `extract_json(text) -> dict`**. ```json 펜스 제거, 앞뒤 산문 제거,
  첫 `{`~짝이 맞는 `}` 추출. 가장 먼저 TDD로 짤 대상
- `ollama.py` — httpx `/api/chat`, `"format": "json"` 강제, `stream: False`
- `bedrock.py` — boto3 `converse`를 `asyncio.to_thread`로 감쌈. JSON 강제 플래그가 없으므로 프롬프트 + 추출에 의존
- `openai.py` — httpx, `response_format={"type":"json_object"}`
- `factory.py` — `create_llm_provider()`가 `settings.LLM_PROVIDER`로 분기 (설계 §6.5)

> **Bedrock/OpenAI는 자격증명이 없어 이번 스프린트에서 실행 검증되지 않는다.** 코드만 존재하는 상태이며,
> Sprint 4 배포 시 실제 호출로 검증해야 한다.

### 3. 마이그레이션

`app/models/coaching_session.py` 작성 → `app/models/__init__.py`에 re-export(**alembic autogenerate 필수 조건**)
→ `alembic revision --autogenerate -m "create_coaching_sessions"`.
`down_revision`이 `f98c4ca51889`인지, `created_at DESC` 인덱스가 제대로 나왔는지 검토.

### 4. Rule Engine (`app/graph/nodes/rule_engine.py`) — 이번 스프린트 최고 가치 TDD 대상

순수 함수 `evaluate_rules(context: dict) -> list[dict]`. LLM도 DB도 없이 전부 테스트 가능.
설계 §7.2의 9개 룰을 그대로:

| code | 조건 | context에서 읽는 값 |
|---|---|---|
| `VOLUME_EXCEEDED` | 주간 km ≥ target × 1.2 | `weekly.completed_km`, `weekly.target_km` |
| `HARD_DAYS_LIMIT` | 최근 2일 연속 tempo/interval | `recent_runs` |
| `REST_DAY_MINIMUM` | 이번 주 휴식일 0 && 세션 ≥ 4 | `weekly.session_count`, `recent_runs` |
| `TAPER_7D` | 대회 D-7 이내 | `goal.days_to_race` |
| `TAPER_3D` | 대회 D-3 이내 | `goal.days_to_race` |
| `HEAT_ALERT` | 기온 ≥ 33°C | `weather.temp_c` |
| `COLD_ALERT` | 기온 ≤ -5°C | `weather.temp_c` |
| `INJURY_RISK` | RPE ≥ 9 이틀 연속 | `recent_runs[].rpe` |
| `BEGINNER_GUARD` | 총 러닝 < 10회 | `total_run_count` |

`weather`가 `None`이거나 `goal`이 없을 때 조용히 건너뛰어야 한다(WeatherService는 실패 시 `None`을 준다).

### 5. 스키마 (`app/schemas/coach.py`)

```python
class CoachRecommendation(BaseModel):        # LLM 출력 검증 = 신뢰 경계
    run_type: Literal["easy","tempo","interval","long_run","recovery","rest"]
    distance_km: float = Field(ge=0)          # rest는 0
    pace_range: PaceRange | None = None       # app.schemas.plan에서 재사용
    warmup: str
    main_session: str
    cooldown: str
    reasoning: str
    motivation: str
```
그 외: `RecommendRequest(rpe?, notes?)`, `FeedbackRequest(coaching_session_id, rating 1-5)`,
`WeeklyContext`, `RecommendResponse`(§5.5 형태), `CoachingSessionResponse`.

`CoachingSessionResponse`에 `context_snapshot`은 **넣지 않는다** — 응답이 과도하게 커진다.
DB에는 보존하되 API로는 노출하지 않는다.

### 6. 나머지 노드 + 그래프

- `context_assembler.py` — 위 "재사용할 기존 코드" 표대로 조립. 결과가 곧 `context_snapshot`
- `llm_coach.py` — `prompts.COACH_SYSTEM_PROMPT.format(constraints=...)` → `invoke` →
  `extract_json` → `CoachRecommendation` 검증. 실패 시 1회 재시도, 최종 실패 시 `CoachingUnavailable`.
  `state["model_used"] = llm.get_model_name()`
- `plan_updater.py` — `PlanService.apply_recommendation(...)`(신규, `mark_session_completed`와 동일한
  JSONB 재할당 패턴)로 오늘 세션을 `status: "recommended"` + LLM `pace_range`로 갱신하고,
  룰이 발동했으면 `adjustments_log`에 `{date, reason: code, change}` append.
  그 뒤 `CoachingRepository.create(...)`로 스냅샷 저장
- `response_formatter.py` — §5.5 페이로드. `plan_adjustment`는 발동한 룰 요약 또는 `None`
- `state.py` — `CoachState` TypedDict (session, user_id, user_location, rpe, notes, context,
  constraints, recommendation, model_used, session_id, response)
- `coach_graph.py` — `build_coach_graph(llm)`이 `functools.partial`로 provider를 바인딩하고 선형 연결 후 compile

### 7. API + 배선

- `app/repositories/run_repo.py` — `count(session, user_id)` 추가 (BEGINNER_GUARD용;
  `get_range`로 전량 조회하는 방식은 낭비)
- `app/repositories/coaching_repo.py` — `create`, `get_by_id`, `list_recent`, `update`
- `app/api/coach.py` — `POST /coach/recommend`, `POST /coach/feedback`(200 + 갱신된 세션),
  `GET /coach/history?limit=10`
- `app/dependencies.py` — `get_coach_graph()` (지연 생성 + 캐시)
- `app/main.py` — `app.include_router(coach.router)`

---

## 구현 시 주의점

1. **LLM 출력은 신뢰 경계다.** `CoachRecommendation`을 통과하지 못한 응답은 절대 DB에 쓰지 않는다.
   Sprint 2 회고에서 짚은 대로, 잘못된 `pace_range`가 저장되면 이후 `GET /plans/current`가 500이 된다.
   **쓰기 전에 검증**하는 것이 그 예방책이다.
2. **JSONB in-place 변경은 저장되지 않는다** (Sprint 2와 동일). `apply_recommendation`도 반드시
   새 리스트를 만들어 재할당.
3. **실패 시 DB에 아무것도 남기지 않는다.** 결정 #1에 따라 `CoachingUnavailable`은
   `db.commit()` 전에 올라와야 한다. 노드에서 예외가 나면 라우터가 커밋하지 않고 빠져나가는지 확인.
4. **테스트는 절대 살아있는 LLM에 의존하지 않는다.** Ollama는 현재 미설치이며 CI에도 없다.
   전부 `FakeLLMProvider`로 돌린다.
5. **`mypy --strict`.** LangGraph의 타입 힌트가 느슨하다. 컴파일된 그래프 타입은 필요하면
   좁은 범위에 `# type: ignore[...]`를 붙이되 이유를 주석으로 남긴다.

---

## 테스트

기존 관례 유지: `@pytest.mark.asyncio`, 파일 로컬 `_signup(client)` 헬퍼, `resp` → `body` → `assert`.

**`tests/test_rule_engine.py`** (순수 단위 — LLM/DB 없음, 가장 촘촘하게)
- 9개 룰 각각의 발동 / 미발동 경계값
- `weather=None`, `goal=None`에서 조용히 통과
- 복수 룰 동시 발동 (예: `VOLUME_EXCEEDED` + `HEAT_ALERT`)

**`tests/test_llm_parsing.py`** (순수 단위)
- 순수 JSON / ```json 펜스 / 앞뒤 산문 동반 / 중첩 객체 / 파싱 불가 문자열

**`tests/test_coach.py`** (통합, `FakeLLMProvider` 주입)
- `test_recommend_returns_recommendation` — §5.5 응답 형태
- `test_recommend_persists_coaching_session` — `model_used`·`context_snapshot`·`constraints` 저장 확인
- `test_recommend_updates_weekly_plan` — 오늘 세션이 `status:"recommended"` + `pace_range` dict로 갱신
- `test_recommend_applies_rule_constraints` — 볼륨 초과 상황에서 constraints가 프롬프트에 전달됨
- `test_recommend_malformed_json_retries_then_503` — 계속 깨진 JSON → 503, **그리고 coaching_sessions 행이 없음**
- `test_recommend_llm_down_returns_503`
- `test_feedback_updates_rating` / `test_feedback_invalid_rating_rejected`(422) / 타인 세션 접근 404
- `test_history_returns_recent_sessions`

---

## 검증

```bash
uv sync --extra dev
.venv/bin/alembic upgrade head
.venv/bin/alembic downgrade -1 && .venv/bin/alembic upgrade head
.venv/bin/ruff format . && .venv/bin/ruff check .
.venv/bin/mypy app
.venv/bin/pytest -v            # 기존 56개 + 신규 전부
```

**완료 기준 수동 검증** — 실제 LLM으로 한 번은 돌려봐야 한다(현재 Ollama 미설치):

```bash
brew install ollama && ollama serve &
ollama pull gemma3:4b          # ~3GB
.venv/bin/uvicorn app.main:app --port 8000

# 목표 설정 → 러닝 몇 건 기록 → 추천 요청
curl -s localhost:8000/coach/recommend -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"rpe":6,"notes":"다리가 조금 무거움"}'
```

확인할 것: `recommendation.reasoning`이 실제 주간 볼륨·최근 러닝·날씨를 언급하는가(= 컨텍스트가
실제로 전달되었는가), `run_type`이 constraints를 위반하지 않는가, `weekly_context` 숫자가
`GET /stats/weekly`와 일치하는가.

---

## 위험 요소

| 위험 | 가능성 | 완화 |
|---|---|---|
| gemma3:4b가 스키마를 지키지 못함 | 높음 | JSON 강제 모드 + 추출 + 1회 재시도. 그래도 불안정하면 `qwen3:4b`로 교체(설계 §6.10) |
| 한국어 `reasoning` 품질이 낮음 | 중간 | 4B 모델의 한계. 프롬프트 튜닝으로 대응하되, 품질 판단은 Bedrock 전환 후에 |
| LangGraph 타입이 mypy strict와 충돌 | 중간 | 좁은 범위 `type: ignore` + 사유 주석 |
| `/coach/recommend`가 느리고 비용이 듦 (rate limit 없음) | 중간 | Sprint 4의 rate limiting 항목. 이번 스프린트 범위 밖임을 명시 |
| Bedrock/OpenAI 코드가 미검증 상태로 남음 | 확정 | 결정 #3에서 수용한 트레이드오프. Sprint 4 배포 시 최우선 검증 |

---

## 범위 밖 (Sprint 4)

- Rate limiting (`RATE_LIMITED` 429) — 설계 §10에 코드만 정의되어 있고 미구현
- Bedrock/OpenAI 실호출 검증
- structlog 로깅, Mangum/Lambda 패키징, CI
- 추천 품질의 정량 평가(모델 A/B) — `model_used`를 계속 기록해 두는 것으로 준비만 해 둠
