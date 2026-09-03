# Running Coach — Server Design & Execution Plan

## 1. MVP scope

수동 입력 기반 AI 러닝 코칭. 디바이스 연동 없이 코칭 가치 먼저 검증한다.

### In scope

- 러닝 기록 CRUD (거리, 시간, 페이스, RPE, 메모)
- 주간 목표 / 대회 목표 설정
- AI 오늘의 루틴 추천 (이지런 / 인터벌 / 템포런 / 장거리 / 휴식)
- 주간 볼륨 추적 + 플랜 자동 조정
- 날씨 연동 (OpenWeatherMap)

### Out of scope (Phase 2+)

- Capacitor 네이티브 래핑 / Health Connect / HealthKit
- 가민 API / GPX 업로드
- 소셜 기능 / 멀티 유저 경쟁

---

## 2. Tech stack

| Layer       | Choice                        | Reason                                  |
|-------------|-------------------------------|-----------------------------------------|
| Framework   | FastAPI + uvicorn             | LangGraph과 같은 Python, async 네이티브  |
| AI engine   | LangGraph + LLM provider 추상화 | 로컬(Ollama) ↔ Bedrock ↔ OpenAI 교체 가능 |
| Database    | PostgreSQL (RDS free tier)    | JSONB로 유연한 스키마, 익숙한 스택        |
| Cache       | Redis (ElastiCache) or in-mem | 세션 캐시, rate limit                    |
| Weather     | OpenWeatherMap free tier      | 분당 60회, MVP 충분                      |
| Auth        | JWT (python-jose)             | 사이드 프로젝트 수준, 간단하게            |
| Migration   | Alembic                       | SQLAlchemy 기반 마이그레이션              |
| Deploy      | AWS Lambda + API Gateway      | 비용 최소화, 사이드 프로젝트 적합         |

---

## 3. Project structure

```
running-coach-api/
├── alembic/                    # DB migrations
│   ├── versions/
│   └── env.py
├── app/
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Settings (pydantic-settings)
│   ├── dependencies.py         # DI: DB session, current_user
│   │
│   ├── api/                    # Route layer
│   │   ├── __init__.py
│   │   ├── auth.py             # POST /auth/signup, /auth/login
│   │   ├── runs.py             # /runs CRUD
│   │   ├── goals.py            # /goals CRUD
│   │   ├── plans.py            # /plans (weekly plan)
│   │   └── coach.py            # /coach (AI coaching)
│   │
│   ├── schemas/                # Pydantic request/response models
│   │   ├── auth.py
│   │   ├── run.py
│   │   ├── goal.py
│   │   ├── plan.py
│   │   └── coach.py
│   │
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── run.py
│   │   ├── goal.py
│   │   ├── weekly_plan.py
│   │   └── coaching_session.py
│   │
│   ├── repositories/           # Data access layer
│   │   ├── run_repo.py
│   │   ├── goal_repo.py
│   │   ├── plan_repo.py
│   │   └── coaching_repo.py
│   │
│   ├── services/               # Business logic
│   │   ├── run_service.py
│   │   ├── goal_service.py
│   │   ├── plan_service.py
│   │   ├── weather_service.py
│   │   └── stats_service.py
│   │
│   ├── llm/                    # LLM provider abstraction
│   │   ├── __init__.py
│   │   ├── base.py             # LLMProvider ABC
│   │   ├── ollama.py           # Local dev (Ollama)
│   │   ├── bedrock.py          # AWS Bedrock (Nova, Claude)
│   │   ├── openai.py           # OpenAI (optional)
│   │   └── factory.py          # Provider factory by config
│   │
│   └── graph/                  # LangGraph coaching engine
│       ├── state.py            # CoachState TypedDict
│       ├── coach_graph.py      # Graph assembly
│       ├── prompts.py          # System prompts
│       └── nodes/
│           ├── context_assembler.py
│           ├── rule_engine.py
│           ├── llm_coach.py    # Uses LLMProvider, not Bedrock directly
│           ├── plan_updater.py
│           └── response_formatter.py
│
├── tests/
│   ├── conftest.py
│   ├── test_runs.py
│   ├── test_goals.py
│   ├── test_coach.py
│   └── test_rule_engine.py
│
├── alembic.ini
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml          # local dev (postgres + redis)
```

---

## 4. Database schema

### 4.1 users

```sql
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    password    VARCHAR(255) NOT NULL,      -- bcrypt hash
    name        VARCHAR(100) NOT NULL,
    location    VARCHAR(100),               -- 날씨 조회용 (e.g. "Seoul")
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);
```

### 4.2 runs

```sql
CREATE TABLE runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    run_date        DATE NOT NULL,
    distance_km     DECIMAL(5,2) NOT NULL,
    duration_sec    INTEGER NOT NULL,
    avg_pace_sec    INTEGER GENERATED ALWAYS AS (
                        CASE WHEN distance_km > 0
                        THEN (duration_sec / distance_km)::INTEGER
                        ELSE NULL END
                    ) STORED,
    run_type        VARCHAR(20) NOT NULL
                        CHECK (run_type IN ('easy','tempo','interval','long','race','other')),
    rpe             SMALLINT CHECK (rpe BETWEEN 1 AND 10),
    notes           TEXT,
    weather_snapshot JSONB,
    -- weather_snapshot example:
    -- {"temp_c": 24, "humidity": 65, "condition": "맑음", "wind_mps": 3.2}
    created_at      TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT unique_user_run_date UNIQUE (user_id, run_date, created_at)
);

CREATE INDEX idx_runs_user_date ON runs(user_id, run_date DESC);
```

### 4.3 goals

```sql
CREATE TABLE goals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    goal_type       VARCHAR(20) NOT NULL
                        CHECK (goal_type IN ('weekly_volume', 'race')),
    weekly_km_target DECIMAL(5,1),
    race_name       VARCHAR(200),
    race_date       DATE,
    race_target_time INTEGER,              -- 목표 시간 (초)
    race_distance_km DECIMAL(5,2),         -- 5, 10, 21.1, 42.195 등
    status          VARCHAR(20) DEFAULT 'active'
                        CHECK (status IN ('active','completed','abandoned')),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_goals_user_active ON goals(user_id) WHERE status = 'active';
```

### 4.4 weekly_plans

```sql
CREATE TABLE weekly_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    goal_id         UUID REFERENCES goals(id),
    week_start      DATE NOT NULL,          -- 항상 월요일
    planned_sessions JSONB NOT NULL DEFAULT '[]',
    -- planned_sessions example:
    -- [
    --   {"day":"mon","type":"easy","distance_km":5,
    --    "pace_range":{"min":"6:00/km","max":"6:30/km"},"status":"completed"},
    --   {"day":"wed","type":"interval","distance_km":6,
    --    "pace_range":{"min":"5:00/km","max":"5:30/km"},"status":"recommended"},
    --   {"day":"sat","type":"long_run","distance_km":12,
    --    "pace_range":null,"status":"pending"}
    -- ]
    -- pace_range는 §5.5 API 응답 / §7.3 LLM 출력 계약과 동일한 {min, max} 형태로 통일한다.
    --   (Plan Updater가 LLM 응답을 변환 없이 그대로 기록하기 위함)
    --   Sprint 2의 규칙 기반 생성은 페이스 모델이 없어 항상 null을 넣는다.
    -- type은 runs.run_type 어휘를 따른다 (long → long_run).
    total_planned_km DECIMAL(5,1),
    adjustments_log  JSONB DEFAULT '[]',
    -- adjustments_log example:
    -- [
    --   {"date":"2026-09-03","reason":"VOLUME_EXCEEDED","change":"wed interval → easy 4km"}
    -- ]
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT unique_user_week UNIQUE (user_id, week_start)
);
```

### 4.5 coaching_sessions

```sql
CREATE TABLE coaching_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    context_snapshot JSONB NOT NULL,        -- AI에 넘긴 context 전체
    constraints     JSONB,                  -- rule engine output
    recommendation  JSONB NOT NULL,         -- AI 응답
    user_feedback   SMALLINT,              -- 1-5 별점 (나중에)
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_coaching_user_date
    ON coaching_sessions(user_id, created_at DESC);
```

### 4.6 ER diagram

```
users  ──1:N──  runs
users  ──1:N──  goals
users  ──1:N──  weekly_plans
users  ──1:N──  coaching_sessions
goals  ──1:N──  weekly_plans
```

---

## 5. API endpoints

### 5.1 Auth

| Method | Path              | Description       | Request Body                              | Response          |
|--------|-------------------|--------------------|-------------------------------------------|-------------------|
| POST   | `/auth/signup`    | 회원가입           | `{email, password, name, location?}`      | `{access_token}`  |
| POST   | `/auth/login`     | 로그인             | `{email, password}`                       | `{access_token}`  |

### 5.2 Runs

| Method | Path              | Description              | Notes                              |
|--------|-------------------|--------------------------|------------------------------------|
| POST   | `/runs`           | 러닝 기록 생성           | weather_snapshot 자동 채움          |
| GET    | `/runs`           | 내 러닝 기록 목록         | `?from=&to=&limit=&offset=`       |
| GET    | `/runs/{id}`      | 러닝 기록 상세           |                                    |
| PUT    | `/runs/{id}`      | 러닝 기록 수정           |                                    |
| DELETE | `/runs/{id}`      | 러닝 기록 삭제           | soft delete                        |

**POST /runs request body:**

```json
{
  "run_date": "2026-09-02",
  "distance_km": 5.2,
  "duration_sec": 1872,
  "run_type": "easy",
  "rpe": 4,
  "notes": "한강 반포대교 코스. 바람 좀 불었지만 쾌적."
}
```

**POST /runs response:**

```json
{
  "id": "uuid",
  "run_date": "2026-09-02",
  "distance_km": 5.2,
  "duration_sec": 1872,
  "avg_pace_sec": 360,
  "avg_pace_display": "6:00/km",
  "run_type": "easy",
  "rpe": 4,
  "notes": "한강 반포대교 코스. 바람 좀 불었지만 쾌적.",
  "weather_snapshot": {
    "temp_c": 26,
    "humidity": 58,
    "condition": "구름 조금",
    "wind_mps": 4.1
  },
  "created_at": "2026-09-02T19:30:00+09:00"
}
```

### 5.3 Goals

| Method | Path              | Description              | Notes                              |
|--------|-------------------|--------------------------|------------------------------------|
| POST   | `/goals`          | 목표 생성                | 기존 active 목표는 자동 abandoned   |
| GET    | `/goals`          | 목표 목록                | `?status=active`                   |
| GET    | `/goals/active`   | 현재 활성 목표            |                                    |
| PUT    | `/goals/{id}`     | 목표 수정                |                                    |
| PATCH  | `/goals/{id}/status` | 목표 상태 변경         | completed / abandoned              |

**POST /goals — weekly_volume type:**

```json
{
  "goal_type": "weekly_volume",
  "weekly_km_target": 30
}
```

**POST /goals — race type:**

```json
{
  "goal_type": "race",
  "race_name": "서울마라톤 2027",
  "race_date": "2027-03-16",
  "race_distance_km": 42.195,
  "race_target_time": 14400,
  "weekly_km_target": 40
}
```

### 5.4 Plans (weekly plan)

| Method | Path                    | Description                | Notes                     |
|--------|-------------------------|----------------------------|---------------------------|
| GET    | `/plans/current`        | 이번 주 플랜               | 없으면 자동 생성           |
| GET    | `/plans/{week_start}`   | 특정 주 플랜               | week_start = 월요일 날짜   |
| GET    | `/plans/history`        | 주간 플랜 히스토리          | `?weeks=8`                |

Plans는 직접 생성/수정하지 않는다. AI 코칭 시 자동으로 생성·갱신된다.

### 5.5 Coach (core)

| Method | Path                    | Description                    | Notes                           |
|--------|-------------------------|--------------------------------|---------------------------------|
| POST   | `/coach/recommend`      | 오늘의 러닝 추천 요청           | 핵심 엔드포인트                  |
| POST   | `/coach/feedback`       | 추천에 대한 피드백              | coaching_session_id + rating    |
| GET    | `/coach/history`        | 코칭 히스토리                   | `?limit=10`                     |

**POST /coach/recommend request:**

```json
{
  "rpe": 6,
  "notes": "어제 다리가 좀 무거웠는데 오늘은 괜찮음"
}
```

**POST /coach/recommend response:**

```json
{
  "session_id": "uuid",
  "recommendation": {
    "run_type": "tempo",
    "distance_km": 6.0,
    "pace_range": {
      "min": "5:20/km",
      "max": "5:40/km"
    },
    "warmup": "1km 이지런 (6:30~7:00 페이스) + 동적 스트레칭 5분",
    "main_session": "4km 템포런 (5:20~5:40 페이스). 2km 지점에서 페이스 확인 후 유지.",
    "cooldown": "1km 조깅 + 정적 스트레칭 5분",
    "reasoning": "이번 주 20km 중 12km 완료. 남은 3일에 8km 배분 필요. 어제 이지런 완료했고 RPE 6으로 컨디션 양호하므로 중강도 템포런 적합. 기온 25°C, 습도 55%로 러닝 최적 조건.",
    "motivation": "템포런은 레이스 페이스 감각을 만드는 투자입니다. 4km만 집중!"
  },
  "weekly_context": {
    "completed_km": 12.0,
    "target_km": 20.0,
    "progress_pct": 60,
    "remaining_days": 3,
    "sessions_done": 3,
    "plan_adjustment": null
  },
  "weather": {
    "temp_c": 25,
    "humidity": 55,
    "condition": "맑음"
  }
}
```

### 5.6 Stats (dashboard)

| Method | Path                     | Description                  | Notes                     |
|--------|--------------------------|------------------------------|---------------------------|
| GET    | `/stats/weekly`          | 이번 주 요약                  | 볼륨, 세션수, 평균 페이스  |
| GET    | `/stats/trend`           | 주간 트렌드                   | `?weeks=12`               |
| GET    | `/stats/personal-bests`  | 개인 기록                     | 거리별 최고 페이스          |

**GET /stats/weekly response:**

```json
{
  "week_start": "2026-08-31",
  "total_km": 12.0,
  "target_km": 20.0,
  "progress_pct": 60,
  "session_count": 3,
  "avg_pace_sec": 372,
  "avg_pace_display": "6:12/km",
  "avg_rpe": 5.3,
  "run_type_breakdown": {
    "easy": 2,
    "tempo": 1
  }
}
```

---

## 6. LLM provider abstraction

로컬 개발 시 Ollama(무료, GPU 불필요한 경량 모델)로 빠르게 반복하고,
배포 시 Bedrock Nova / Claude로 교체하는 구조.

### 6.1 Provider interface

```python
# app/llm/base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: dict | None = None  # {"input_tokens": N, "output_tokens": N}


class LLMProvider(ABC):
    """LLM provider 공통 인터페이스.
    모든 provider는 이 인터페이스만 구현하면 된다.
    """

    @abstractmethod
    async def invoke(
        self,
        system: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse: ...

    @abstractmethod
    def get_model_name(self) -> str: ...
```

### 6.2 Ollama provider (로컬 개발용)

```python
# app/llm/ollama.py
import httpx
from app.llm.base import LLMProvider, LLMResponse


class OllamaProvider(LLMProvider):
    """로컬 Ollama 서버와 통신. GPU 없어도 CPU로 동작하는 모델 사용."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "gemma3:4b",  # 가볍고 한국어 괜찮은 모델
    ):
        self.base_url = base_url
        self.model = model

    async def invoke(
        self,
        system: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_message},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return LLMResponse(
            content=data["message"]["content"],
            model=self.model,
            usage={
                "input_tokens": data.get("prompt_eval_count"),
                "output_tokens": data.get("eval_count"),
            },
        )

    def get_model_name(self) -> str:
        return f"ollama/{self.model}"
```

### 6.3 Bedrock provider (프로덕션)

```python
# app/llm/bedrock.py
import json
import boto3
from app.llm.base import LLMProvider, LLMResponse


class BedrockProvider(LLMProvider):
    """AWS Bedrock — Nova, Claude 등 모델 ID만 바꿔서 사용."""

    def __init__(
        self,
        model_id: str = "amazon.nova-lite-v1:0",
        region: str = "us-east-1",
    ):
        self.model_id = model_id
        self.client = boto3.client("bedrock-runtime", region_name=region)

    async def invoke(
        self,
        system: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        # Bedrock Converse API — 모델 불문 동일한 인터페이스
        import asyncio

        response = await asyncio.to_thread(
            self.client.converse,
            modelId=self.model_id,
            system=[{"text": system}],
            messages=[
                {
                    "role": "user",
                    "content": [{"text": user_message}],
                }
            ],
            inferenceConfig={
                "temperature": temperature,
                "maxTokens": max_tokens,
            },
        )

        output_text = response["output"]["message"]["content"][0]["text"]
        usage = response.get("usage", {})

        return LLMResponse(
            content=output_text,
            model=self.model_id,
            usage={
                "input_tokens": usage.get("inputTokens"),
                "output_tokens": usage.get("outputTokens"),
            },
        )

    def get_model_name(self) -> str:
        return f"bedrock/{self.model_id}"
```

### 6.4 OpenAI provider (선택)

```python
# app/llm/openai.py
import httpx
from app.llm.base import LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    """OpenAI API. 필요 시 추가."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    async def invoke(
        self,
        system: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]["message"]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice["content"],
            model=self.model,
            usage={
                "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
            },
        )

    def get_model_name(self) -> str:
        return f"openai/{self.model}"
```

### 6.5 Factory — config 기반 자동 선택

```python
# app/llm/factory.py
from app.config import settings
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.llm.bedrock import BedrockProvider
from app.llm.openai import OpenAIProvider


def create_llm_provider() -> LLMProvider:
    """LLM_PROVIDER 환경변수로 provider 결정.

    .env examples:
      LLM_PROVIDER=ollama          # 로컬 개발
      LLM_PROVIDER=bedrock         # AWS 배포
      LLM_PROVIDER=openai          # OpenAI 사용 시
    """
    match settings.LLM_PROVIDER:
        case "ollama":
            return OllamaProvider(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL,
            )
        case "bedrock":
            return BedrockProvider(
                model_id=settings.BEDROCK_MODEL_ID,
                region=settings.BEDROCK_REGION,
            )
        case "openai":
            return OpenAIProvider(
                api_key=settings.OPENAI_API_KEY,
                model=settings.OPENAI_MODEL,
            )
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER}")
```

### 6.6 Config (.env)

```bash
# ===== 로컬 개발 (.env) =====
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:4b       # 또는 qwen3:4b, llama3.2:3b

# ===== 프로덕션 (.env.prod) =====
LLM_PROVIDER=bedrock
BEDROCK_MODEL_ID=amazon.nova-lite-v1:0    # 저렴 + 빠름
# BEDROCK_MODEL_ID=amazon.nova-pro-v1:0   # 고품질
# BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514  # 최고 품질
BEDROCK_REGION=us-east-1
```

### 6.7 Settings (pydantic-settings)

```python
# app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ... 기존 설정 ...

    # LLM provider
    LLM_PROVIDER: str = "ollama"

    # Ollama (local)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma3:4b"

    # Bedrock (prod)
    BEDROCK_MODEL_ID: str = "amazon.nova-lite-v1:0"
    BEDROCK_REGION: str = "us-east-1"

    # OpenAI (optional)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    class Config:
        env_file = ".env"
```

### 6.8 LLM Coach 노드 — provider 주입

```python
# app/graph/nodes/llm_coach.py
import json
from app.llm.base import LLMProvider
from app.graph.prompts import COACH_SYSTEM_PROMPT


async def call_coach(state: CoachState, llm: LLMProvider) -> CoachState:
    prompt = COACH_SYSTEM_PROMPT.format(constraints="\n".join(state["constraints"]) or "없음")

    response = await llm.invoke(
        system=prompt,
        user_message=json.dumps(state["context"], ensure_ascii=False),
        temperature=0.7,
    )

    state["recommendation"] = json.loads(response.content)
    state["model_used"] = llm.get_model_name()  # 로깅용
    return state
```

### 6.9 Graph에서 provider 바인딩

```python
# app/graph/coach_graph.py
from functools import partial
from langgraph.graph import StateGraph, END
from app.llm.factory import create_llm_provider


def build_coach_graph():
    llm = create_llm_provider()

    workflow = StateGraph(CoachState)

    workflow.add_node("assemble_context", assemble_context)
    workflow.add_node("apply_rules", apply_rules)
    workflow.add_node("call_coach", partial(call_coach, llm=llm))
    workflow.add_node("update_plan", update_plan)
    workflow.add_node("format_response", format_response)

    workflow.set_entry_point("assemble_context")
    workflow.add_edge("assemble_context", "apply_rules")
    workflow.add_edge("apply_rules", "call_coach")
    workflow.add_edge("call_coach", "update_plan")
    workflow.add_edge("update_plan", "format_response")
    workflow.add_edge("format_response", END)

    return workflow.compile()
```

### 6.10 로컬 개발 추천 모델

| Model            | Size | 한국어 | Speed (CPU) | 추천 용도                    |
|------------------|------|--------|-------------|------------------------------|
| gemma3:4b        | 3GB  | 양호   | 보통        | 기본 개발용, JSON 출력 안정적  |
| qwen3:4b         | 3GB  | 좋음   | 보통        | 한국어 품질 우선 시            |
| llama3.2:3b      | 2GB  | 보통   | 빠름        | 가볍게 테스트용               |

Ollama 설치 후 `ollama pull gemma3:4b` 한 줄로 준비 완료.

---

### 6.1 RunService

```python
class RunService:
    async def create_run(self, user_id, data: RunCreate) -> Run:
        # 1. weather snapshot 자동 채움
        weather = await weather_service.get_for_date_location(data.run_date, user.location)
        # 2. DB 저장
        run = await run_repo.create(user_id, data, weather)
        # 3. 주간 플랜 상태 업데이트 (recommended → completed)
        await plan_service.mark_session_completed(user_id, run)
        return run
```

### 6.2 StatsService

```python
class StatsService:
    async def get_weekly_stats(self, user_id, week_start=None) -> WeeklyStats:
        if not week_start:
            week_start = get_monday(date.today())
        week_end = week_start + timedelta(days=6)

        runs = await run_repo.get_range(user_id, week_start, week_end)
        goal = await goal_repo.get_active(user_id)

        return WeeklyStats(
            total_km=sum(r.distance_km for r in runs),
            target_km=goal.weekly_km_target if goal else None,
            session_count=len(runs),
            avg_pace_sec=avg([r.avg_pace_sec for r in runs]),
            avg_rpe=avg([r.rpe for r in runs if r.rpe]),
            run_type_breakdown=Counter(r.run_type for r in runs),
        )

    async def get_trend(self, user_id, weeks=12) -> list[WeeklyStats]:
        results = []
        for i in range(weeks):
            ws = get_monday(date.today()) - timedelta(weeks=i)
            results.append(await self.get_weekly_stats(user_id, ws))
        return results
```

### 6.3 WeatherService

```python
class WeatherService:
    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

    async def get_current(self, location: str) -> WeatherData:
        # Redis 캐시: 같은 location, 30분 이내 → 캐시 반환
        cached = await redis.get(f"weather:{location}")
        if cached:
            return WeatherData.parse_raw(cached)

        resp = await httpx.get(
            self.BASE_URL,
            params={
                "q": location,
                "appid": settings.OWM_API_KEY,
                "units": "metric",
                "lang": "kr",
            },
        )
        data = resp.json()
        weather = WeatherData(
            temp_c=data["main"]["temp"],
            humidity=data["main"]["humidity"],
            condition=data["weather"][0]["description"],
            wind_mps=data["wind"]["speed"],
        )
        await redis.setex(f"weather:{location}", 1800, weather.json())
        return weather
```

---

## 8. LangGraph coaching engine

(이전 대화에서 설계한 내용 정리)

### 7.1 Graph flow

```
User request
    │
    ▼
[1. Context Assembler]  ← DB (runs, goals, plans) + Weather API
    │
    ▼
[2. Rule Engine]        ← Hard rules (volume guard, recovery, taper, heat)
    │
    ▼
[3. LLM Coach]          ← Bedrock Claude Sonnet + system prompt + constraints
    │
    ▼
[4. Plan Updater]       ← weekly_plans update + coaching_sessions log
    │
    ▼
[5. Response Formatter] → Structured JSON
```

### 7.2 Rule engine rules

| Rule               | Condition                                    | Action                                |
|--------------------|----------------------------------------------|---------------------------------------|
| VOLUME_EXCEEDED    | 주간 km ≥ target × 1.2                       | easy or rest only                     |
| HARD_DAYS_LIMIT    | 최근 2일 연속 tempo/interval                   | easy 강제                             |
| REST_DAY_MINIMUM   | 이번 주 rest day = 0 && sessions ≥ 4          | rest 강력 권장                         |
| TAPER_7D           | 대회 D-7 이내                                 | 볼륨 60% 이하                          |
| TAPER_3D           | 대회 D-3 이내                                 | easy 3km 이하 or rest                  |
| HEAT_ALERT         | 기온 ≥ 33°C                                  | 페이스 10-15% 하향                     |
| COLD_ALERT         | 기온 ≤ -5°C                                  | 실내 대안 제시 또는 방한 주의           |
| INJURY_RISK        | RPE ≥ 9 이틀 연속                             | rest 강제 + 통증 확인 메시지            |
| BEGINNER_GUARD     | 총 러닝 기록 < 10회                           | 최대 거리 5km, 이지런 위주              |

### 7.3 System prompt (핵심)

```
당신은 경험 많은 러닝 코치입니다.

## 원칙
1. 부상 예방이 최우선. 의심되면 보수적으로 추천하라.
2. 주간 볼륨은 전주 대비 10% 이상 급증하지 않도록 관리하라.
3. 80/20 법칙: 전체 볼륨의 80%는 이지런, 20%는 고강도.
4. 사용자의 주관적 컨디션(RPE)을 최우선 시그널로 삼아라.
5. 날씨 조건을 반드시 반영하라 (폭염, 한파, 미세먼지).

## 출력 형식
반드시 아래 JSON 형식으로만 응답하라:
{
  "run_type": "easy|tempo|interval|long|rest",
  "distance_km": number,
  "pace_range": {"min": "m:ss/km", "max": "m:ss/km"},
  "warmup": string,
  "main_session": string,
  "cooldown": string,
  "reasoning": string,
  "motivation": string
}

## 제약 조건
{constraints}
```

---

## 9. Execution plan

### Sprint 0: Project bootstrap (2일)

- [ ] 프로젝트 초기화 (pyproject.toml, ruff, mypy 설정)
- [ ] docker-compose.yml (PostgreSQL + Redis)
- [ ] FastAPI boilerplate (main.py, config.py, dependencies.py)
- [ ] Alembic 초기 설정 + 첫 마이그레이션 (users 테이블)
- [ ] JWT auth 구현 (signup, login, middleware)
- [ ] 기본 health check endpoint

**완료 기준:** `POST /auth/signup` → `POST /auth/login` → JWT 발급 → 인증된 요청 성공

### Sprint 1: Run CRUD + Stats (3일)

- [ ] runs 테이블 마이그레이션
- [ ] RunCreate / RunResponse 스키마
- [ ] RunRepository (create, get, list, update, delete)
- [ ] RunService (weather snapshot 자동 채움 포함)
- [ ] runs API 5개 엔드포인트
- [ ] StatsService (weekly_stats, trend)
- [ ] stats API 엔드포인트
- [ ] WeatherService (OpenWeatherMap + Redis 캐시)
- [ ] 테스트: run CRUD + stats 계산 검증

**완료 기준:** Postman으로 러닝 기록 입력 → 주간 통계 조회 가능

### Sprint 2: Goals + Weekly Plans (2일)

- [ ] goals, weekly_plans 테이블 마이그레이션
- [ ] Goal CRUD API
- [ ] PlanService (주간 플랜 자동 생성, 세션 상태 관리)
- [ ] plans API (current, history)
- [ ] Run 생성 시 weekly_plan 자동 업데이트 연동
- [ ] 테스트: 목표 생성 → 러닝 기록 → 플랜 진행률 반영

**완료 기준:** 목표 30km/주 설정 → 5km 러닝 기록 → 플랜에 25km 잔여 반영

### Sprint 3: AI Coaching Engine (4일)

- [ ] coaching_sessions 테이블 마이그레이션
- [ ] LangGraph state 정의 (CoachState)
- [ ] Context Assembler 노드
- [ ] Rule Engine 노드 (9개 룰)
- [ ] LLM Coach 노드 (Bedrock 연동)
- [ ] Plan Updater 노드
- [ ] Response Formatter 노드
- [ ] Graph 조립 + compile
- [ ] `POST /coach/recommend` 엔드포인트
- [ ] `POST /coach/feedback`, `GET /coach/history`
- [ ] 테스트: 다양한 시나리오 (볼륨 초과, 테이퍼링, 폭염 등)

**완료 기준:** RPE 입력 → AI가 컨텍스트 기반 구체적 세션 추천 반환

### Sprint 4: Polish + Deploy (2일)

- [ ] 에러 핸들링 통일 (custom exception handler)
- [ ] Request validation 강화
- [ ] API rate limiting
- [ ] Logging (structlog)
- [ ] Dockerfile + Lambda 패키징 (Mangum adapter)
- [ ] AWS CDK or SAM template
- [ ] RDS + ElastiCache 프로비저닝
- [ ] CI: GitHub Actions (lint + test + deploy)

**완료 기준:** Lambda에서 전체 API 동작, 프론트에서 호출 가능

---

## 10. API error format

모든 에러 응답은 동일한 형식:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "distance_km must be positive",
    "details": {}
  }
}
```

| Code                | HTTP | Description              |
|---------------------|------|--------------------------|
| VALIDATION_ERROR    | 400  | 입력 검증 실패            |
| UNAUTHORIZED        | 401  | 인증 실패 / 토큰 만료     |
| NOT_FOUND           | 404  | 리소스 없음               |
| CONFLICT            | 409  | 중복 데이터 (같은 날 기록) |
| RATE_LIMITED         | 429  | 요청 제한 초과            |
| COACHING_UNAVAILABLE | 503 | Bedrock 호출 실패         |

---

## 11. Key design decisions

### 11.1 왜 avg_pace를 generated column으로?

클라이언트가 계산해서 보내면 distance/duration과 불일치 가능.
DB에서 항상 `duration_sec / distance_km`으로 계산하면 데이터 정합성 보장.

### 11.2 왜 Rule Engine이 LLM 앞에?

LLM은 가끔 "오늘 인터벌 가즈아!"처럼 무리한 추천을 한다.
Rule Engine이 constraints를 생성하면 LLM은 그 범위 내에서만 추천.
LLM의 창의성(세션 구성, 동기부여 멘트)은 살리면서 안전성은 하드코딩으로 보장.

### 11.3 왜 coaching_sessions에 context_snapshot을 통째로 저장?

디버깅: AI가 이상한 추천을 했을 때, 당시 context를 그대로 볼 수 있다.
분석: 나중에 어떤 context 조합에서 만족도가 높았는지 분석 가능.
재현: 같은 context로 다른 모델/프롬프트를 테스트할 수 있다.

### 11.4 왜 LLM provider를 추상화?

로컬 개발 시 Bedrock 호출은 느리고 돈이 든다. Ollama로 빠르게 반복하고
배포 시 .env 한 줄(`LLM_PROVIDER=bedrock`)만 바꾸면 끝.
coaching_sessions에 `model_used`를 저장하므로 모델별 추천 품질 비교도 가능.
나중에 모델 A/B 테스트나 fallback 체인(Bedrock 실패 → OpenAI)도 이 구조에서 확장.

### 11.5 weekly_plans의 planned_sessions를 왜 JSONB로?

요일별 세션 구조가 유동적이다 (주 3일 수도, 5일 수도 있다).
AI가 조정할 때 세션을 추가/삭제/변경하는데 정규화된 테이블이면 복잡해진다.
JSONB면 한번에 읽고 한번에 쓸 수 있어서 AI 연동에 적합하다.

---

## Appendix: Local dev quickstart

```bash
# 1. 환경 세팅
git clone <repo>
cd running-coach-api
cp .env.example .env  # LLM_PROVIDER=ollama 기본값

# 2. 인프라 실행
docker-compose up -d  # postgres:15 + redis:7

# 3. Ollama 설치 + 모델 다운로드
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma3:4b           # ~3GB, 한국어 양호
# 또는: ollama pull qwen3:4b    # 한국어 더 좋음

# 4. 의존성 설치
uv sync  # or: pip install -e ".[dev]"

# 5. DB 마이그레이션
alembic upgrade head

# 6. 개발 서버
uvicorn app.main:app --reload --port 8000
# → .env의 LLM_PROVIDER=ollama로 로컬 모델 자동 사용

# 7. 테스트
pytest -v

# 배포 시 .env만 변경:
# LLM_PROVIDER=bedrock
# BEDROCK_MODEL_ID=amazon.nova-lite-v1:0
```
