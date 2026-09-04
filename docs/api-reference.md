# Running Coach API — 프론트엔드 개발자용 레퍼런스

> **Base URL**: `http://localhost:8000` (로컬 개발)  
> **인증**: JWT Bearer Token — `Authorization: Bearer <access_token>`  
> **오류 응답 공통 형식**: `{"error": {"code": "...", "message": "..."}}`

---

## 목차

1. [인증 (Auth)](#1-인증-auth)
2. [러너 프로필 (Profile)](#2-러너-프로필-profile) ← **Sprint 3 신규**
3. [러닝 기록 (Runs)](#3-러닝-기록-runs)
4. [목표 (Goals)](#4-목표-goals)
5. [주간 플랜 (Plans)](#5-주간-플랜-plans)
6. [통계 (Stats)](#6-통계-stats)
7. [AI 코칭 (Coach)](#7-ai-코칭-coach)
8. [헬스체크 (Health)](#8-헬스체크-health)
9. [공통 타입 정의](#9-공통-타입-정의)
10. [오류 코드 일람](#10-오류-코드-일람)
11. [사용자 플로우 (온보딩)](#11-사용자-플로우-온보딩)

---

## 1. 인증 (Auth)

### POST `/auth/signup`

회원가입. 토큰만 반환 — 추가 사용자 정보는 `/auth/me` 참조.

**Request Body**

```json
{
  "email": "user@example.com",
  "password": "password123",
  "name": "홍길동",
  "location": "Seoul"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `email` | string | ✅ | 이메일 (중복 불가) |
| `password` | string | ✅ | 최소 8자 |
| `name` | string | ✅ | 1~100자 |
| `location` | string | ❌ | 날씨 조회용 도시명 (예: `"Seoul"`) |

**Response** `201 Created`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors**

| HTTP | code | 설명 |
|------|------|------|
| 409 | `CONFLICT` | 이미 사용 중인 이메일 |

---

### POST `/auth/login`

로그인.

**Request Body**

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response** `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors**

| HTTP | code | 설명 |
|------|------|------|
| 401 | `UNAUTHORIZED` | 이메일 또는 비밀번호 불일치 |

---

### GET `/auth/me`

현재 로그인 사용자 정보 조회. `onboarding_completed` 필드로 온보딩 완료 여부 확인.

**Headers**: `Authorization: Bearer <token>`

**Response** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": "홍길동",
  "location": "Seoul",
  "onboarding_completed": false,
  "created_at": "2026-09-04T10:00:00"
}
```

> **Note**: 회원가입 직후 `onboarding_completed: false`. `POST /users/profile` 완료 후 `true`로 바뀜.

---

## 2. 러너 프로필 (Profile)

> **Sprint 3 신규 추가.** AI 코칭(`POST /coach/recommend`)을 사용하려면 반드시 먼저 프로필을 등록해야 합니다.

### POST `/users/profile`

온보딩 — 러너 프로필 최초 등록. 한 번만 허용. 이후 수정은 `PATCH /users/profile`.

**Headers**: `Authorization: Bearer <token>`

**Request Body**

```json
{
  "experience": {
    "level": "intermediate",
    "runs_per_week": 4,
    "longest_distance": "10_21km"
  },
  "training": {
    "preferred_types": ["easy", "tempo"],
    "available_days": ["mon", "wed", "fri", "sat"],
    "time_per_session": "30_60min"
  },
  "cross_training": ["cycling", "yoga"],
  "injuries": {
    "status": {
      "knee": "none",
      "ankle": "none",
      "achilles": "none",
      "shin": "none",
      "hip_back": "none",
      "plantar_fascia": "none"
    },
    "history": null
  }
}
```

**experience.level** 값

| 값 | 설명 |
|---|---|
| `beginner` | 초보 (총 러닝 경험 3개월 미만) |
| `novice` | 초급 (3~12개월) |
| `intermediate` | 중급 (1~3년) |
| `advanced` | 고급 (3년 이상) |

**experience.longest_distance** 값

| 값 | 설명 |
|---|---|
| `under_5km` | 5km 미만 |
| `5_10km` | 5~10km |
| `10_21km` | 10~21km |
| `half_plus` | 하프마라톤 이상 |

**training.available_days** 값: `"mon"` `"tue"` `"wed"` `"thu"` `"fri"` `"sat"` `"sun"`

**training.time_per_session** 값

| 값 | 설명 |
|---|---|
| `under_30min` | 30분 미만 |
| `30_60min` | 30~60분 |
| `60_90min` | 60~90분 |
| `unlimited` | 제한 없음 |

**training.preferred_types** 값: `"easy"` `"tempo"` `"interval"` `"long_run"` `"race"` `"recovery"`

**cross_training** 값 (복수 선택, 빈 배열 허용):
`"weight"` `"swimming"` `"cycling"` `"yoga"` `"boxing"` `"hiking"`

**injuries.status** — 각 부위별 상태

| 부위 키 | 설명 |
|---------|------|
| `knee` | 무릎 |
| `ankle` | 발목 |
| `achilles` | 아킬레스건 |
| `shin` | 정강이 |
| `hip_back` | 허리/고관절 |
| `plantar_fascia` | 족저근막 |

| 상태 값 | 설명 |
|---------|------|
| `none` | 이상 없음 |
| `mild` | 경미한 불편 |
| `caution` | 주의 필요 |
| `severe` | 심각 (러닝 중단 권고 수준) |

**Response** `201 Created`

```json
{
  "experience": {
    "level": "intermediate",
    "runs_per_week": 4,
    "longest_distance": "10_21km"
  },
  "training": {
    "preferred_types": ["easy", "tempo"],
    "available_days": ["mon", "wed", "fri", "sat"],
    "time_per_session": "30_60min"
  },
  "cross_training": ["cycling", "yoga"],
  "injuries": {
    "status": {
      "knee": "none",
      "ankle": "none",
      "achilles": "none",
      "shin": "none",
      "hip_back": "none",
      "plantar_fascia": "none"
    },
    "history": null
  },
  "onboarding_completed": true
}
```

**Errors**

| HTTP | code | 설명 |
|------|------|------|
| 409 | `PROFILE_ALREADY_EXISTS` | 이미 온보딩 완료. `PATCH /users/profile` 사용 |
| 401 | `UNAUTHORIZED` | 미인증 |

---

### GET `/users/profile`

현재 사용자의 러너 프로필 조회.

**Headers**: `Authorization: Bearer <token>`

**Response** `200 OK` — POST 응답과 동일한 형식.

**Errors**

| HTTP | code | 설명 |
|------|------|------|
| 404 | `PROFILE_NOT_FOUND` | 아직 온보딩 미완료 |

---

### PATCH `/users/profile`

러너 프로필 부분 수정. 전달한 섹션만 업데이트.

**Headers**: `Authorization: Bearer <token>`

**Request Body** (모든 필드 선택)

```json
{
  "experience": {
    "level": "advanced",
    "runs_per_week": 5,
    "longest_distance": "half_plus"
  },
  "injuries": {
    "status": {
      "knee": "caution",
      "ankle": "none",
      "achilles": "none",
      "shin": "none",
      "hip_back": "none",
      "plantar_fascia": "none"
    },
    "history": "2026년 9월 무릎 IT밴드 부상"
  }
}
```

> **주의**: 섹션 단위 교체입니다. `injuries`를 보내면 기존 injuries 전체가 새 값으로 대체됩니다.

**Response** `200 OK` — 업데이트된 프로필.

**Errors**

| HTTP | code | 설명 |
|------|------|------|
| 404 | `PROFILE_NOT_FOUND` | 아직 온보딩 미완료 |

---

## 3. 러닝 기록 (Runs)

### POST `/runs`

러닝 기록 생성. 날씨 정보는 서버에서 자동 스탬핑.

**Headers**: `Authorization: Bearer <token>`

**Request Body**

```json
{
  "run_date": "2026-09-04",
  "distance_km": "10.5",
  "duration_sec": 3600,
  "run_type": "easy",
  "rpe": 6,
  "notes": "가볍게 달렸음"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `run_date` | date (YYYY-MM-DD) | ✅ | 러닝 날짜 |
| `distance_km` | number | ✅ | 거리 km (>0) |
| `duration_sec` | integer | ✅ | 소요 시간 초 (>0) |
| `run_type` | string | ✅ | 러닝 타입 (하단 타입 정의 참조) |
| `rpe` | integer 1~10 | ❌ | 주관적 운동 강도 |
| `notes` | string | ❌ | 메모 |

**Response** `201 Created`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "run_date": "2026-09-04",
  "distance_km": 10.5,
  "duration_sec": 3600,
  "avg_pace_sec": 343,
  "avg_pace_display": "5:43",
  "run_type": "easy",
  "rpe": 6,
  "notes": "가볍게 달렸음",
  "weather_snapshot": {
    "temp_c": 28.5,
    "humidity": 65,
    "condition": "Clear"
  },
  "created_at": "2026-09-04T10:00:00"
}
```

> **Note**: `avg_pace_sec`은 서버가 `duration_sec / distance_km`으로 계산 (DB generated column). 클라이언트 계산값은 무시.

---

### GET `/runs`

내 러닝 기록 목록.

**Headers**: `Authorization: Bearer <token>`

**Query Parameters**

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `from` | date | — | 시작 날짜 (포함) |
| `to` | date | — | 종료 날짜 (포함) |
| `limit` | integer 1~100 | 20 | 반환 개수 |
| `offset` | integer | 0 | 건너뛸 개수 |

**Response** `200 OK` — `RunResponse[]`

---

### GET `/runs/{run_id}`

특정 러닝 기록 조회.

**Response** `200 OK` — `RunResponse`

**Errors**: `404 NOT_FOUND` (본인 기록이 아닌 경우 포함)

---

### PUT `/runs/{run_id}`

러닝 기록 수정 (보낸 필드만 변경).

**Request Body**: `run_date`, `distance_km`, `duration_sec`, `run_type`, `rpe`, `notes` 중 원하는 필드

**Response** `200 OK` — 수정된 `RunResponse`

---

### DELETE `/runs/{run_id}`

러닝 기록 소프트 삭제.

**Response** `204 No Content`

---

## 4. 목표 (Goals)

### POST `/goals`

목표 생성. 기존 `active` 목표가 있으면 자동으로 `abandoned` 처리.

**Headers**: `Authorization: Bearer <token>`

**Request Body** — 주간 볼륨 목표

```json
{
  "goal_type": "weekly_volume",
  "weekly_km_target": 40
}
```

**Request Body** — 레이스 목표

```json
{
  "goal_type": "race",
  "race_name": "서울 하프마라톤 2027",
  "race_date": "2027-03-15",
  "race_distance_km": 21.0975,
  "race_target_time": 7200
}
```

| 필드 | 타입 | 필수 조건 | 설명 |
|------|------|----------|------|
| `goal_type` | string | ✅ | `"weekly_volume"` 또는 `"race"` |
| `weekly_km_target` | number | weekly_volume 시 필수 | 주간 목표 km |
| `race_name` | string | race 시 필수 | 대회명 (최대 200자) |
| `race_date` | date | race 시 필수 | 대회 날짜 (미래여야 함) |
| `race_distance_km` | number | race 시 필수 | 대회 거리 |
| `race_target_time` | integer | ❌ | 목표 기록 (초) |

**Response** `201 Created`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "goal_type": "race",
  "weekly_km_target": null,
  "race_name": "서울 하프마라톤 2027",
  "race_date": "2027-03-15",
  "race_target_time": 7200,
  "race_distance_km": 21.0975,
  "status": "active",
  "created_at": "2026-09-04T10:00:00",
  "updated_at": "2026-09-04T10:00:00"
}
```

---

### GET `/goals`

목표 목록 조회.

**Query Parameters**

| 파라미터 | 설명 |
|---------|------|
| `status` | `"active"` `"completed"` `"abandoned"` (미지정 시 전체) |

**Response** `200 OK` — `GoalResponse[]`

---

### GET `/goals/active`

현재 활성 목표 조회.

**Response** `200 OK` — `GoalResponse`

**Errors**: `404 NOT_FOUND` (활성 목표 없음)

---

### PUT `/goals/{goal_id}`

목표 내용 수정 (선택적 필드).

**Request Body**: `weekly_km_target`, `race_name`, `race_date`, `race_target_time`, `race_distance_km` 중 원하는 필드

**Response** `200 OK` — 수정된 `GoalResponse`

---

### PATCH `/goals/{goal_id}/status`

목표 상태 변경.

**Request Body**

```json
{
  "status": "completed"
}
```

`status` 값: `"completed"` 또는 `"abandoned"`

**Response** `200 OK` — 업데이트된 `GoalResponse`

---

## 5. 주간 플랜 (Plans)

> AI 코칭이 플랜을 자동 생성/수정합니다. 직접 생성 API는 없습니다.

### GET `/plans/current`

이번 주(월요일 기준) 플랜 조회. 없으면 자동 생성.

**Headers**: `Authorization: Bearer <token>`

**Response** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440003",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "goal_id": "550e8400-e29b-41d4-a716-446655440002",
  "week_start": "2026-09-01",
  "planned_sessions": [
    {
      "day": "mon",
      "type": "easy",
      "distance_km": 5.0,
      "pace_range": {"min": "5:30", "max": "6:00"},
      "status": "planned",
      "actual_distance_km": null,
      "run_id": null,
      "unplanned": false
    }
  ],
  "total_planned_km": 40.0,
  "completed_km": 10.5,
  "remaining_km": 29.5,
  "progress_pct": 26,
  "adjustments_log": [],
  "created_at": "2026-09-01T00:00:00",
  "updated_at": "2026-09-04T10:00:00"
}
```

**planned_sessions[].status** 값: `"planned"` `"completed"` `"skipped"`

---

### GET `/plans/history`

과거 플랜 이력.

**Query Parameters**

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `weeks` | 8 | 최근 N주 (1~52) |

**Response** `200 OK` — `WeeklyPlanResponse[]`

---

### GET `/plans/{week_start}`

특정 주 플랜 조회. `week_start`는 해당 주 월요일 날짜 (YYYY-MM-DD).

**Response** `200 OK` — `WeeklyPlanResponse`

---

## 6. 통계 (Stats)

### GET `/stats/weekly`

주간 통계 요약.

**Headers**: `Authorization: Bearer <token>`

**Query Parameters**

| 파라미터 | 설명 |
|---------|------|
| `week_start` | 기준 월요일 날짜 (미지정 시 이번 주) |

**Response** `200 OK`

```json
{
  "week_start": "2026-09-01",
  "total_km": 32.5,
  "target_km": 40.0,
  "progress_pct": 81,
  "session_count": 4,
  "avg_pace_sec": 330,
  "avg_pace_display": "5:30",
  "avg_rpe": 6.5,
  "run_type_breakdown": {
    "easy": 2,
    "tempo": 1,
    "long_run": 1
  }
}
```

---

### GET `/stats/trend`

주간 볼륨 트렌드 (차트용).

**Query Parameters**

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `weeks` | 12 | 최근 N주 (1~52) |

**Response** `200 OK`

```json
[
  {
    "week_start": "2026-08-25",
    "total_km": 35.0,
    "session_count": 5,
    "avg_pace_sec": 325,
    "avg_pace_display": "5:25"
  }
]
```

---

### GET `/stats/personal-bests`

거리 버킷별 개인 최고 기록.

**Response** `200 OK`

```json
[
  {
    "distance_bucket": "5km",
    "best_pace_sec": 280,
    "best_pace_display": "4:40",
    "achieved_on": "2026-08-15"
  }
]
```

---

## 7. AI 코칭 (Coach)

> **온보딩 필수**: `POST /users/profile` 완료 후에만 사용 가능.  
> 미완료 시 → `403 ONBOARDING_REQUIRED`

### POST `/coach/recommend`

오늘의 러닝 세션 AI 추천. LangGraph 파이프라인(컨텍스트 조합 → 안전 규칙 → 프로필 규칙 → LLM 생성)이 실행됩니다.

**Headers**: `Authorization: Bearer <token>`

**Request Body** (모두 선택)

```json
{
  "rpe": 7,
  "notes": "어제 장거리 달리고 다리가 좀 피로함"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `rpe` | integer 1~10 | 최근 피로도 |
| `notes` | string (최대 500자) | 코치에게 전달할 메모 |

**Response** `200 OK`

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440004",
  "recommendation": {
    "run_type": "easy",
    "distance_km": 5.0,
    "pace_range": {"min": "5:30", "max": "6:00"},
    "warmup": "5분 걷기 후 1km 아주 천천히",
    "main_session": "4km 이지런 — 대화가 가능한 페이스 유지",
    "cooldown": "5분 걷기 + 허벅지/종아리 스트레칭",
    "reasoning": "어제 장거리 후 RPE 7로 피로도가 있음. 회복 우선.",
    "motivation": "오늘은 쉬어가도 훈련입니다. 가볍게 흘려보내세요!"
  },
  "weekly_context": {
    "completed_km": 25.0,
    "target_km": 40.0,
    "progress_pct": 63,
    "remaining_days": 3,
    "sessions_done": 3,
    "plan_adjustment": "주간 목표 대비 순조롭게 진행 중"
  },
  "weather": {
    "temp_c": 28.5,
    "humidity": 65,
    "condition": "Clear"
  }
}
```

**recommendation.run_type** 값

| 값 | 설명 |
|---|---|
| `easy` | 이지런 |
| `tempo` | 템포런 |
| `interval` | 인터벌 |
| `long_run` | 장거리 |
| `recovery` | 회복런 |
| `rest` | 휴식 (AI가 러닝 대신 휴식을 권고하는 경우) |

**Errors**

| HTTP | code | 설명 |
|------|------|------|
| 403 | `ONBOARDING_REQUIRED` | 프로필 미등록 |
| 503 | `COACHING_UNAVAILABLE` | LLM 서버 다운 또는 응답 파싱 3회 실패 |
| 429 | `RATE_LIMITED` | 요청 한도 초과 |

---

### POST `/coach/feedback`

코칭 세션에 별점 피드백 제출.

**Headers**: `Authorization: Bearer <token>`

**Request Body**

```json
{
  "coaching_session_id": "550e8400-e29b-41d4-a716-446655440004",
  "rating": 4
}
```

| 필드 | 설명 |
|------|------|
| `coaching_session_id` | `POST /coach/recommend` 응답의 `session_id` |
| `rating` | 1~5 별점 |

**Response** `200 OK`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440004",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "constraints": [
    {"code": "HEAT_ALERT", "message": "기온 35°C. 페이스를 10-15% 하향 조정하세요."}
  ],
  "recommendation": {"...": "..."},
  "model_used": "gemma3:4b",
  "user_feedback": 4,
  "created_at": "2026-09-04T10:00:00"
}
```

---

### GET `/coach/history`

AI 코칭 세션 이력.

**Headers**: `Authorization: Bearer <token>`

**Query Parameters**

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `limit` | 10 | 최근 N개 (1~100) |

**Response** `200 OK` — `CoachingSessionResponse[]` (feedback 응답과 동일 형식)

---

## 8. 헬스체크 (Health)

### GET `/health`

Liveness probe. 인증 불필요.

**Response** `200 OK`

```json
{"status": "ok"}
```

---

### GET `/readiness`

Readiness probe. DB·Redis 연결 상태 확인.

**Response** `200 OK` (정상) / `503` (일부 의존성 실패)

```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "redis": "ok"
  }
}
```

---

## 9. 공통 타입 정의

### RunType

```
"easy" | "tempo" | "interval" | "long_run" | "race" | "recovery"
```

### DayOfWeek

```
"mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun"
```

### ExperienceLevel

```
"beginner" | "novice" | "intermediate" | "advanced"
```

### LongestDistance

```
"under_5km" | "5_10km" | "10_21km" | "half_plus"
```

### TimePerSession

```
"under_30min" | "30_60min" | "60_90min" | "unlimited"
```

### CrossTraining

```
"weight" | "swimming" | "cycling" | "yoga" | "boxing" | "hiking"
```

### InjuryPart

```
"knee" | "ankle" | "achilles" | "shin" | "hip_back" | "plantar_fascia"
```

### InjuryStatus

```
"none" | "mild" | "caution" | "severe"
```

### GoalType

```
"weekly_volume" | "race"
```

### GoalStatus

```
"active" | "completed" | "abandoned"
```

---

## 10. 오류 코드 일람

모든 오류 응답 형식:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "사람이 읽을 수 있는 메시지",
    "details": {}
  }
}
```

| HTTP | code | 발생 엔드포인트 | 설명 |
|------|------|----------------|------|
| 400 | `VALIDATION_ERROR` | 전체 | 요청 바디/파라미터 유효성 실패 |
| 401 | `UNAUTHORIZED` | 전체 인증 필요 엔드포인트 | 토큰 없음, 만료, 인증 실패 |
| 403 | `ONBOARDING_REQUIRED` | `POST /coach/recommend` | 러너 프로필 미등록 |
| 404 | `NOT_FOUND` | 단건 조회/수정/삭제 | 리소스 없음 (타인 리소스 접근 포함) |
| 404 | `PROFILE_NOT_FOUND` | `GET /users/profile`, `PATCH /users/profile` | 러너 프로필 미등록 |
| 409 | `CONFLICT` | `POST /auth/signup` | 이메일 중복 |
| 409 | `PROFILE_ALREADY_EXISTS` | `POST /users/profile` | 프로필 중복 등록 |
| 429 | `RATE_LIMITED` | 전체 | 요청 한도 초과 |
| 503 | `COACHING_UNAVAILABLE` | `POST /coach/recommend` | LLM 서버 다운 또는 응답 파싱 실패 |

---

## 11. 사용자 플로우 (온보딩)

AI 코칭 기능을 사용하기 위한 최소 플로우:

```
1. POST /auth/signup           → access_token 저장
2. POST /users/profile         → onboarding_completed: true
3. POST /coach/recommend       → AI 세션 추천 수령
4. (선택) POST /runs           → 실제 러닝 기록 입력
5. (선택) POST /coach/feedback → 별점 피드백 제출
```

**온보딩 상태 확인:**

```
GET /auth/me
→ { "onboarding_completed": false }  ← 프로필 등록 화면으로 이동
→ { "onboarding_completed": true }   ← 홈/코칭 화면으로 이동
```

**온보딩 없이 코칭 요청 시:**

```http
POST /coach/recommend
Authorization: Bearer <token>

→ HTTP 403
{
  "error": {
    "code": "ONBOARDING_REQUIRED",
    "message": "온보딩을 먼저 완료해야 합니다."
  }
}
```
