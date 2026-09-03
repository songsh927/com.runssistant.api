# Running Coach API — Sprint 0 & Sprint 1 구현 요약

> 작성일: 2026-09-02
> 상태: Sprint 0 완료, Sprint 1 완료

---

## 프로젝트 개요

수동 입력 기반 AI 러닝 코칭 백엔드. 디바이스 연동 없이 코칭 가치를 먼저 검증하는 MVP.

- **스택**: FastAPI + asyncpg + SQLAlchemy 2.x + Alembic + Redis + PostgreSQL
- **아키텍처**: api → services → repositories → models (엄격한 레이어 분리)
- **테스트**: pytest-asyncio, 실 PostgreSQL 테스트 DB (`runcoach_test`)

---

## Sprint 0: 프로젝트 부트스트랩

### 구현 완료 항목

| 항목 | 파일 |
|------|------|
| 프로젝트 설정 (pyproject.toml, ruff, mypy) | `pyproject.toml` |
| 로컬 인프라 (PostgreSQL 15 + Redis 7) | `docker-compose.yml` |
| 테스트 DB 초기화 | `scripts/init-test-db.sql` |
| FastAPI 앱 진입점 + 에러 핸들러 | `app/main.py` |
| 환경 설정 (pydantic-settings) | `app/config.py` |
| DB 세션 (async_sessionmaker) | `app/db.py` |
| 의존성 주입 (get_db, get_current_user) | `app/dependencies.py` |
| ORM 베이스 + uuid_pk() 헬퍼 | `app/models/base.py` |
| User ORM 모델 | `app/models/user.py` |
| 예외 계층 (AppException 등 5종) | `app/core/exceptions.py` |
| JWT 인증 (python-jose, bcrypt) | `app/core/security.py` |
| Auth 스키마 | `app/schemas/auth.py` |
| Auth API (signup, login, me) | `app/api/auth.py` |
| Alembic 마이그레이션 — users 테이블 | `alembic/versions/7a0cb6ee1f48_create_users.py` |
| 테스트 픽스처 | `tests/conftest.py` |
| Auth 테스트 6개 | `tests/test_auth.py` |

### 주요 기술 결정

- **asyncpg 단독** (psycopg2 미사용) — async-only 스택 유지
- **bcrypt 직접 사용** — passlib + bcrypt 4.1 버전 충돌 회피
- **pytest-asyncio 이벤트 루프 스코프** — `asyncio_default_fixture_loop_scope = "session"` + `asyncio_default_test_loop_scope = "session"` 함께 설정해야 해결됨
- **`uuid.uuid4()` 고유 이메일** — 커밋 후 롤백 안 되는 테스트 격리 방식
- **`gen_random_uuid()` server_default** — DB가 UUID 생성, 클라이언트 신뢰 안 함
- **`ruff ignore = ["B008"]`** — FastAPI `Depends()` false positive 억제
- **`str(jwt.encode(...))` 캐스팅** — mypy strict `Any` 반환 처리

### 에러 응답 형식 (전 엔드포인트 통일)

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "리소스를 찾을 수 없습니다.",
    "details": {}
  }
}
```

### Sprint 0 테스트 결과

```
6 passed
  test_signup_success
  test_signup_duplicate_email
  test_login_success
  test_login_wrong_password
  test_me_success
  test_me_no_token
```

---

## Sprint 1: Run CRUD + Stats + Weather

### 구현 완료 항목

| 항목 | 파일 |
|------|------|
| Redis 클라이언트 | `app/core/redis.py` |
| 페이스 포맷 유틸 (format_pace, get_monday) | `app/core/pace.py` |
| Run ORM 모델 | `app/models/run.py` |
| Run 스키마 (RunCreate, RunUpdate, RunResponse) | `app/schemas/run.py` |
| Stats 스키마 (WeeklyStats, TrendPoint, PersonalBest) | `app/schemas/stats.py` |
| RunRepository (create, get_by_id, list_runs, update, soft_delete, get_range) | `app/repositories/run_repo.py` |
| WeatherService (OWM API + Redis 30분 캐시) | `app/services/weather_service.py` |
| RunService (날씨 자동 스냅샷, 소유권 검증) | `app/services/run_service.py` |
| StatsService (weekly_stats, trend, personal_bests) | `app/services/stats_service.py` |
| Runs API (5개 엔드포인트) | `app/api/runs.py` |
| Stats API (3개 엔드포인트) | `app/api/stats.py` |
| Alembic 마이그레이션 — runs 테이블 | `alembic/versions/f94c142bef11_create_runs.py` |
| 테스트 픽스처 업데이트 (FakeWeatherService, auth_headers) | `tests/conftest.py` |
| Run CRUD 테스트 8개 | `tests/test_runs.py` |
| Stats 테스트 7개 | `tests/test_stats.py` |

### runs 테이블 스키마

```sql
CREATE TABLE runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    run_date        DATE NOT NULL,
    distance_km     NUMERIC(5, 2) NOT NULL  CHECK (distance_km > 0),
    duration_sec    INTEGER NOT NULL        CHECK (duration_sec > 0),
    avg_pace_sec    INTEGER GENERATED ALWAYS AS
                        ((duration_sec / NULLIF(distance_km, 0))::integer) STORED,
    run_type        VARCHAR(20) NOT NULL
                        CHECK (run_type IN ('easy','tempo','interval','long_run','race','recovery')),
    rpe             INTEGER CHECK (rpe BETWEEN 1 AND 10),
    notes           TEXT,
    weather_snapshot JSONB,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_runs_user_date ON runs(user_id, run_date);
```

### API 엔드포인트 목록

#### Runs

| Method | Path | 설명 |
|--------|------|------|
| POST | `/runs` | 러닝 기록 생성 (날씨 자동 스냅샷) |
| GET | `/runs?from=&to=&limit=&offset=` | 목록 조회 (날짜 필터, 페이지네이션) |
| GET | `/runs/{id}` | 상세 조회 |
| PUT | `/runs/{id}` | 수정 |
| DELETE | `/runs/{id}` | 소프트 삭제 → 204 No Content |

#### Stats

| Method | Path | 설명 |
|--------|------|------|
| GET | `/stats/weekly?week_start=` | 주간 통계 (기본: 이번 주 월요일) |
| GET | `/stats/trend?weeks=12` | N주 추세 (오래된 순 정렬) |
| GET | `/stats/personal-bests` | 거리 버킷별 최고 페이스 (5k/10k/half/full) |

### POST /runs 응답 예시

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "...",
  "run_date": "2026-09-02",
  "distance_km": 5.0,
  "duration_sec": 1800,
  "avg_pace_sec": 360,
  "avg_pace_display": "6:00/km",
  "run_type": "easy",
  "rpe": 5,
  "notes": "Good run",
  "weather_snapshot": {
    "temp_c": 26.0,
    "feels_like_c": 25.0,
    "humidity": 65,
    "condition": "clear sky",
    "wind_speed_ms": 3.2
  },
  "created_at": "2026-09-02T10:30:00+00:00"
}
```

### 주요 기술 결정

| 결정 | 이유 |
|------|------|
| **Soft delete** (`deleted_at TIMESTAMPTZ`) | 모든 조회/통계 쿼리에 `deleted_at IS NULL` 필터 |
| **`avg_pace_sec` Computed 컬럼** | DB가 항상 `duration_sec / distance_km`으로 계산, 삽입 후 `session.refresh(run)`으로 값 회수 |
| **WeatherService graceful fallback** | OWM API 키 미설정 / 네트워크 실패 시 `weather_snapshot = null`, 기록 생성은 절대 차단하지 않음 |
| **소유권 위반 → 404** | 다른 유저의 run 접근 시 존재 여부 노출 방지 |
| **`get_weather_service` DI 팩토리** | 테스트에서 `FakeWeatherService`로 override, 실제 OWM 네트워크 미호출 |
| **메서드명 `list_runs`** (not `list`) | Python 3.13 클래스 바디에서 `list` 메서드 정의 후 이후 메서드의 `-> list[T]` 어노테이션 평가 시 builtin `list`가 클래스 멤버로 가려지는 버그 회피 |
| **`model_dump(exclude_unset=True)`** | PATCH 의미론: 전송하지 않은 필드는 변경하지 않음 |

### Sprint 1 테스트 결과

```
21 passed  (6 auth + 8 runs + 7 stats)

test_runs.py  :: test_create_run_success             ✅
test_runs.py  :: test_create_run_invalid_run_type    ✅
test_runs.py  :: test_list_runs                      ✅
test_runs.py  :: test_list_runs_date_filter          ✅
test_runs.py  :: test_get_run                        ✅
test_runs.py  :: test_get_run_not_found              ✅
test_runs.py  :: test_update_run                     ✅
test_runs.py  :: test_soft_delete_run                ✅
test_runs.py  :: test_other_user_cannot_access_run   ✅
test_stats.py :: test_weekly_stats_empty             ✅
test_stats.py :: test_weekly_stats_with_data         ✅
test_stats.py :: test_trend_length                   ✅
test_stats.py :: test_trend_chronological_order      ✅
test_stats.py :: test_personal_bests_empty           ✅
test_stats.py :: test_personal_bests_5k              ✅

ruff check  : 0 errors
ruff format : all formatted
mypy app    : Success (28 source files)
```

---

## 설계 대비 미차이 (Sprint 2 진입 전 보완 권장)

| 항목 | 설계 doc | 현재 구현 | 비고 |
|------|----------|-----------|------|
| `WeeklyStats.avg_rpe` | 포함 | **미구현** | runs 데이터만으로 계산 가능 — Sprint 2 초반 추가 권장 |
| `WeeklyStats.target_km`, `progress_pct` | 포함 | 미구현 | goals 테이블 필요 → Sprint 2에서 자동 해결 |
| `UNIQUE (user_id, run_date, created_at)` | 있음 | **마이그레이션 누락** | 기능 무결성 영향 없으나 Sprint 2 마이그레이션 시 추가 권장 |
| `run_type` 값 (`long`, `other`) | 설계 원안 | `long_run`, `recovery` | Sprint 1 계획 수립 시 명시적으로 변경·승인됨 |

---

## 현재 파일 구조

```
app/
├── main.py                  # FastAPI 앱, 에러 핸들러, 라우터 등록
├── config.py                # Settings (pydantic-settings)
├── db.py                    # async_sessionmaker
├── dependencies.py          # get_db, get_current_user, get_weather_service
├── api/
│   ├── auth.py              # POST /auth/signup|login, GET /auth/me
│   ├── runs.py              # POST|GET|PUT|DELETE /runs
│   └── stats.py             # GET /stats/weekly|trend|personal-bests
├── services/
│   ├── run_service.py       # RunService (CRUD + 소유권 검증)
│   ├── weather_service.py   # WeatherService (OWM + Redis 캐시)
│   └── stats_service.py     # StatsService (weekly, trend, personal bests)
├── repositories/
│   └── run_repo.py          # RunRepository (6개 메서드)
├── models/
│   ├── base.py              # Base, TimestampMixin, uuid_pk()
│   ├── user.py              # User ORM
│   └── run.py               # Run ORM (Computed avg_pace_sec, JSONB weather_snapshot)
├── schemas/
│   ├── auth.py              # SignupRequest, TokenResponse, UserResponse
│   ├── run.py               # RunCreate, RunUpdate, RunResponse
│   └── stats.py             # WeeklyStats, TrendPoint, PersonalBest
└── core/
    ├── exceptions.py        # AppException 계층 (NotFound, Conflict, Unauthorized 등)
    ├── security.py          # JWT create/decode, bcrypt hash/verify
    ├── pace.py              # format_pace(), get_monday()
    └── redis.py             # redis.asyncio 클라이언트

alembic/versions/
├── 7a0cb6ee1f48_create_users.py
└── f94c142bef11_create_runs.py

tests/
├── conftest.py              # setup_db, db_session, client, FakeWeatherService, auth_headers
├── test_auth.py             # 6 tests
├── test_runs.py             # 8 tests
└── test_stats.py            # 7 tests
```

---

## 다음 단계: Sprint 2 — Goals + Weekly Plans

**목표:**
- `goals`, `weekly_plans` 테이블 마이그레이션
- Goal CRUD API (`/goals`, `/goals/active`)
- PlanService (주간 플랜 자동 생성, 세션 상태 관리)
- Plans API (`/plans/current`, `/plans/history`)
- Run 생성 시 weekly_plan 자동 업데이트 연동 (RunService step 3)
- `WeeklyStats`에 `target_km`, `progress_pct`, `avg_rpe` 추가

**완료 기준:** 목표 30km/주 설정 → 5km 러닝 기록 → 플랜에 25km 잔여 반영
