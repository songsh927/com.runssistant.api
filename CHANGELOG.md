# 변경 이력 (Changelog)

이 프로젝트의 주요 변경 사항을 기록합니다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르며,
버전은 [유의적 버전(SemVer)](https://semver.org/lang/ko/)을 준수합니다.

프로젝트는 [설계 문서](.claude/plans/running-coach-server-design.md) §9의
스프린트 단위로 개발됩니다 (Sprint 0 부트스트랩 → Sprint 4 배포).

---

## [Unreleased]

---

## [0.2.0] — 2026-09-04

Sprint 4 완료. 프로덕션 배포 가능 상태로 격상.
전체 API가 AWS Lambda(Mangum)에서 동작하며, 에러 봉투 통일·rate limiting·
structlog 로깅·GitHub Actions CI/CD를 갖춥니다.

### Sprint 4 — Polish + Deploy

**에러 핸들링 통일**
- `app/core/error_handlers.py` 신규: `RequestValidationError` → `VALIDATION_ERROR` 400,
  `HTTPException` → 코드 매핑, 미처리 `Exception` → `INTERNAL_ERROR` 500
  (스택트레이스는 로그에만, 응답에 미포함)
- `RateLimited` 예외 추가 (`code="RATE_LIMITED"`, HTTP 429)
- 모든 에러 응답이 `{"error": {"code", "message", "details"}}` 봉투로 통일

**앱 구조 개선**
- `create_app()` 팩토리 도입: CORS·미들웨어·에러 핸들러·라우터를 한 곳에서 조립
- `CORSMiddleware` 추가 (`CORS_ORIGINS` 환경 변수로 환경별 분리)
- lifespan 이벤트: 시작 시 Redis 연결 확인, 종료 시 클린업

**Request validation 강화**
- `GoalCreate.race_date`: 오늘 이후 날짜만 허용 (`@field_validator`)
- `RecommendRequest.notes`: `max_length=500` 제약 추가
- Pydantic 검증 실패가 자동으로 `VALIDATION_ERROR` 봉투로 직렬화됨

**Rate Limiting**
- `app/core/rate_limit.py`: Redis 고정 윈도우(1분) 미들웨어
  - 전역 기본: 분당 60회 (`RATE_LIMIT_DEFAULT`)
  - `/coach/recommend` 강화: 분당 5회 (`RATE_LIMIT_COACH`) — LLM 비용 방어
  - Redis 장애 시 fail-open (요청 통과 + 경고 로그)

**구조적 로깅 (structlog)**
- `app/core/logging.py`: `configure_logging()` — `ENV=prod` 이면 JSON, 로컬은 콘솔
- `X-Request-ID` 미들웨어: 모든 요청에 UUID 생성 → 응답 헤더 반영 + structlog 컨텍스트 바인딩

**Health / Readiness**
- `GET /readiness` 신규: DB(`SELECT 1`) + Redis(`PING`) 체크, 실패 시 503
- `GET /health` (liveness): 기존 유지, 빠른 응답

**Lambda 패키징**
- `app/lambda_handler.py`: `Mangum(create_app())` AWS Lambda 진입점
- `Dockerfile`: `public.ecr.aws/lambda/python:3.12` 베이스 컨테이너 이미지
- `.dockerignore`: tests·.venv·.env 제외

**인프라 (AWS SAM)**
- `template.yaml`: Lambda 함수 + API Gateway(HttpApi) 프록시 정의
  - 환경 변수는 SSM Parameter Store 참조 (하드코딩 금지)
  - Bedrock `InvokeModel` IAM 정책 포함
  - VPC 설정 (RDS/ElastiCache 접근) 주석으로 가이드
- `samconfig.toml`: `sam build`·`sam deploy` 기본 파라미터

**CI/CD (GitHub Actions)**
- `.github/workflows/ci.yml`: PR·브랜치 푸시마다
  `ruff format --check` → `ruff check` → `mypy` → `pytest --cov=app --cov-fail-under=80`
  (서비스 컨테이너: PostgreSQL 15 + Redis 7)
- `.github/workflows/deploy.yml`: `workflow_dispatch` 수동 트리거
  → `alembic upgrade head` → `sam build` → `sam deploy` (OIDC)

**의존성 추가**
- `structlog>=24.0.0` (구조적 로깅)
- `mangum>=0.17.0` (ASGI→Lambda 어댑터)
- `pytest-cov>=5.0.0` (커버리지 리포트)

**설정 확장 (`app/config.py`)**
- `ENV`, `LOG_LEVEL`, `CORS_ORIGINS`, `RATE_LIMIT_DEFAULT`, `RATE_LIMIT_COACH` 추가

**테스트**
- `tests/test_error_handlers.py`: 에러 봉투·`X-Request-ID` 헤더 검증
- `tests/test_health.py`: `/health`·`/readiness` 검증
- `tests/test_rate_limit.py`: 429 반환·Redis 장애 fail-open 검증
- 전체 105 테스트 통과, 커버리지 **85%** (기준 80%+)

---

## [0.1.0] — 2026-09-03

첫 개발 릴리스. Sprint 0~3 완료. 수동 입력 기반 AI 러닝 코칭 MVP의
핵심 흐름(러닝 기록 → 목표 설정 → AI 세션 추천)이 동작합니다.

### Sprint 3 — AI 코칭 엔진 (`63fb9bc`)

- **LangGraph 코칭 파이프라인** 추가: Context Assembler → Rule Engine →
  LLM Coach → Plan Updater → Response Formatter (`app/graph/`)
- **Rule Engine**를 LLM *이전*에 실행하여 안전 제약(볼륨 가드, 회복,
  테이퍼, 폭염/한파 경보, 부상 위험, 초보자 가드)을 코드로 결정론적 강제
- **LLM provider 추상화** (`app/llm/`): Ollama / Bedrock / OpenAI를
  `LLM_PROVIDER` 환경 변수 하나로 교체 (`factory.create_llm_provider()`)
- 코칭 API: `POST /coach/recommend`, `POST /coach/feedback`,
  `GET /coach/history`
- `coaching_sessions` 테이블 및 context snapshot(JSONB) 영속화

### Sprint 2 — 목표 + 주간 플랜

- 목표 API: `POST/GET/PUT /goals`, `GET /goals/active`,
  `PATCH /goals/{id}/status`
- 주간 플랜 API: `GET /plans/current`, `GET /plans/history`,
  `GET /plans/{week_start}` (플랜은 코칭/러닝의 부수 효과로만 생성·조정)
- `goals`, `weekly_plans` 테이블 (`planned_sessions` / `adjustments_log` JSONB)

### Sprint 1 — 러닝 기록 + 통계

- 러닝 CRUD API: `POST/GET/PUT/DELETE /runs`
- 통계 API: `GET /stats/weekly`, `GET /stats/trend`,
  `GET /stats/personal-bests`
- `runs.avg_pace_sec` 생성 컬럼(DB 계산) — 클라이언트 페이스 신뢰 안 함
- **날씨 자동 연동**: `RunService`가 OpenWeatherMap 호출 후
  `weather_snapshot` 스탬프 (Redis 30분 캐시)

### Sprint 0 — 부트스트랩

- 프로젝트 설정 (`pyproject.toml`, ruff, mypy)
- 로컬 인프라 `docker-compose.yml` (PostgreSQL 15 + Redis 7)
- FastAPI 앱 진입점 + 통일 에러 엔벨로프 핸들러
- JWT 인증 (python-jose + bcrypt): `POST /auth/signup`, `/auth/login`,
  `GET /auth/me`
- Alembic 마이그레이션 파이프라인, pytest-asyncio 테스트 기반
