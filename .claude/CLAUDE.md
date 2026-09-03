# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status: greenfield

There is **no source code yet**. The authoritative specification is
[`.claude/plans/running-coach-server-design.md`](plans/running-coach-server-design.md) —
read it before implementing anything. Code is built sprint by sprint per Section 9
of that plan (Sprint 0 bootstrap → Sprint 1 runs+stats → Sprint 2 goals+plans →
Sprint 3 AI coaching → Sprint 4 polish+deploy). When the directory tree below does
not exist yet, create it following the design doc rather than inventing a new layout.

Design docs, prompts, and code comments are written in **Korean** — match that when
editing them.

## What this is

`running-coach-api`: a manual-input running-coaching backend. MVP validates coaching
value *without* device integration (no Garmin/HealthKit/GPX in scope). Core flow: a
user logs runs and goals, then `POST /coach/recommend` returns an AI-generated session
recommendation grounded in their weekly volume, recent runs, and current weather.

## Tech stack

FastAPI + uvicorn · PostgreSQL (SQLAlchemy + Alembic) · Redis (weather cache, rate
limit) · LangGraph for the coaching engine · JWT auth (python-jose) · uv for deps ·
ruff + mypy · deploy target AWS Lambda + API Gateway (via Mangum).

## Commands

```bash
docker-compose up -d                        # local postgres + redis
uv sync                                      # install deps (or: pip install -e ".[dev]")
alembic upgrade head                         # apply migrations
alembic revision --autogenerate -m "msg"     # create a migration
uvicorn app.main:app --reload --port 8000    # dev server
pytest -v                                    # all tests
pytest tests/test_coach.py                   # one file
pytest tests/test_coach.py::test_name        # one test
ruff format . && ruff check .                # format + lint
mypy app                                     # type check
```

Local LLM runs through Ollama, not a cloud key: `ollama pull gemma3:4b` then set
`LLM_PROVIDER=ollama` in `.env` (the default).

## Architecture

Strict layered flow — an HTTP request moves **api → services → repositories → models**,
and each layer only calls the one directly beneath it. Schemas (Pydantic) validate at
the api boundary; core holds config, security, exceptions.

```
app/
├── api/           # routes: auth, runs, goals, plans, coach, stats
├── services/      # business logic (run/goal/plan/weather/stats)
├── repositories/  # data access (SQLAlchemy)
├── models/        # ORM models
├── schemas/       # Pydantic request/response DTOs
├── core/          # config, security, exceptions, constants
├── llm/           # LLM provider abstraction (see below)
└── graph/         # LangGraph coaching engine (see below)
```

### The two pieces that need multiple files to understand

**1. LLM provider abstraction (`app/llm/`).** All LLM calls go through the
`LLMProvider` ABC (`base.py`) with a single `invoke(system, user_message, ...)` →
`LLMResponse` method. Concrete providers (`ollama.py`, `bedrock.py`, `openai.py`) are
selected at runtime by `factory.create_llm_provider()` reading `settings.LLM_PROVIDER`.
The point: iterate locally on free/fast Ollama, then switch to Bedrock in prod by
changing one env var — no code change. Nodes receive the provider by injection; never
call boto3/httpx for an LLM directly from a graph node.

**2. LangGraph coaching engine (`app/graph/`).** `coach_graph.build_coach_graph()`
binds a provider (via `functools.partial`) and wires a linear pipeline:

```
Context Assembler → Rule Engine → LLM Coach → Plan Updater → Response Formatter
```

- **Rule Engine runs *before* the LLM by design.** It produces hard `constraints`
  (volume guard, recovery, taper, heat/cold alerts, injury risk, beginner guard — full
  table in design §7.2). Safety is enforced deterministically in code; the LLM only
  fills in session detail and motivation *within* those constraints. Do not move safety
  logic into the prompt.
- The LLM must return the strict JSON shape defined in the system prompt (design §7.3);
  `Response Formatter` shapes the final API payload.
- `Plan Updater` persists the weekly plan change and logs a `coaching_sessions` row.

## Data model conventions (design §4)

- **`runs.avg_pace_sec` is a generated column** (`duration_sec / distance_km`) — never
  accept or trust a client-computed pace; the DB is the source of truth.
- **`weekly_plans.planned_sessions` / `adjustments_log` and
  `coaching_sessions.context_snapshot` are JSONB.** Weekly plans are read/written as a
  whole document because the AI adds/removes/edits day sessions freely. The full LLM
  context is snapshotted per coaching session for debugging, analysis, and replay —
  preserve it.
- **`coaching_sessions.model_used`** records which provider/model produced a
  recommendation; keep writing it so model quality can be compared.
- Weekly plans are **not** created/edited via the API directly — they are generated and
  adjusted as a side effect of coaching and run logging.

## Cross-cutting rules

- **Weather is auto-filled**, not client-supplied: `RunService.create_run` calls
  `WeatherService` (OpenWeatherMap, Redis-cached 30 min by location) and stamps
  `weather_snapshot` onto the run.
- **Uniform error envelope** for every error response (design §10):
  `{"error": {"code", "message", "details"}}` with a fixed code→HTTP mapping
  (e.g. `VALIDATION_ERROR` 400, `CONFLICT` 409, `COACHING_UNAVAILABLE` 503 when the LLM
  call fails). Add a custom exception handler rather than raising raw HTTPExceptions ad hoc.
- **KISS / YAGNI:** keep layer boundaries strict, but keep code *inside* each layer
  plain — no speculative factories, interfaces, or generalization beyond current needs.
  The `llm/` abstraction is the one deliberate exception (it earns its keep).
