# 변경 이력 (Changelog)

이 프로젝트의 주요 변경 사항을 기록합니다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르며,
버전은 [유의적 버전(SemVer)](https://semver.org/lang/ko/)을 준수합니다.

프로젝트는 [설계 문서](.claude/plans/running-coach-server-design.md) §9의
스프린트 단위로 개발됩니다 (Sprint 0 부트스트랩 → Sprint 4 배포).

---

## [Unreleased]

### 예정 (Sprint 4 — polish + deploy)

- AWS Lambda + API Gateway 배포 (Mangum 어댑터)
- Rate limiting (Redis 기반) 전면 적용
- 관측성/로깅 정비 및 운영 하드닝

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
