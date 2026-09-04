# Running Coach — Server 수정사항: Runner profile 및 온보딩

> 기존 설계(`running-coach-server-design.md`) 구현 완료 기준.
> 이 문서는 러너 프로필 온보딩 기능 추가에 따른 변경사항만 다룬다.

---

## 1. 기능 개요

회원가입 직후 4단계 온보딩으로 러너 프로필을 수집하고,
이를 AI 코칭 엔진에 주입하여 개인화된 추천을 제공한다.

### 수집 항목

| Step | 카테고리   | 수집 데이터                                       |
|------|-----------|--------------------------------------------------|
| 1    | 러닝 경험  | 경력 구간, 주간 러닝 횟수, 최장 러닝 거리           |
| 2    | 훈련 습관  | 선호 러닝 타입, 가용 요일, 1회 시간 여유            |
| 3    | 병행 운동  | 웨이트/수영/자전거/요가/복싱/등산 (복수 선택)        |
| 4    | 부상 현황  | 부위별 상태(4단계) + 과거 부상 이력(자유 텍스트)     |

### 코칭 영향

- 초급자에게 인터벌/장거리 추천 방지
- 가용 요일·시간에 맞는 세션 구성
- 병행 운동 부하 고려한 볼륨 조절
- 부상 부위를 보호하는 세션 타입 제한

---

## 2. DB 변경

### 2.1 users 테이블 수정

```sql
-- Alembic migration
ALTER TABLE users ADD COLUMN runner_profile JSONB;
ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT false;
```

### 2.2 runner_profile 스키마

```json
{
  "experience": {
    "level": "intermediate",
    "runs_per_week": 3,
    "longest_distance": "10_21km"
  },
  "training": {
    "preferred_types": ["easy", "interval"],
    "available_days": ["mon", "wed", "sat"],
    "time_per_session": "30_60min"
  },
  "cross_training": ["boxing", "weight"],
  "injuries": {
    "status": {
      "knee": "mild",
      "ankle": "none",
      "achilles": "none",
      "shin": "none",
      "hip_back": "none",
      "plantar_fascia": "none"
    },
    "history": "2024년 좌측 무릎 반월판 수술"
  }
}
```

### 2.3 Enum 정의

```python
# app/schemas/runner_profile.py

class ExperienceLevel(str, Enum):
    BEGINNER = "beginner"        # 0~3개월
    NOVICE = "novice"            # 3~12개월
    INTERMEDIATE = "intermediate" # 1~3년
    ADVANCED = "advanced"         # 3년+

class LongestDistance(str, Enum):
    UNDER_5KM = "under_5km"
    KM_5_10 = "5_10km"
    KM_10_21 = "10_21km"
    HALF_PLUS = "half_plus"

class TimePerSession(str, Enum):
    UNDER_30 = "under_30min"
    MIN_30_60 = "30_60min"
    MIN_60_90 = "60_90min"
    UNLIMITED = "unlimited"

class InjuryStatus(str, Enum):
    NONE = "none"
    MILD = "mild"          # 경미 — 모니터링만
    CAUTION = "caution"    # 주의 — 세션 타입 제한
    SEVERE = "severe"      # 심각 — 해당 부하 금지

class CrossTraining(str, Enum):
    WEIGHT = "weight"
    SWIMMING = "swimming"
    CYCLING = "cycling"
    YOGA = "yoga"
    BOXING = "boxing"
    HIKING = "hiking"

class InjuryPart(str, Enum):
    KNEE = "knee"
    ANKLE = "ankle"
    ACHILLES = "achilles"
    SHIN = "shin"
    HIP_BACK = "hip_back"
    PLANTAR_FASCIA = "plantar_fascia"
```

---

## 3. Pydantic 스키마

```python
# app/schemas/runner_profile.py

class ExperienceProfile(BaseModel):
    level: ExperienceLevel
    runs_per_week: int = Field(ge=0, le=7)
    longest_distance: LongestDistance

class TrainingProfile(BaseModel):
    preferred_types: list[RunType] = Field(min_length=1)
    available_days: list[str] = Field(min_length=1)  # mon~sun
    time_per_session: TimePerSession

class InjuryProfile(BaseModel):
    status: dict[InjuryPart, InjuryStatus] = Field(
        default_factory=lambda: {part: InjuryStatus.NONE for part in InjuryPart}
    )
    history: str | None = Field(None, max_length=500)

class RunnerProfileCreate(BaseModel):
    """온보딩 시 전체 프로필 제출"""
    experience: ExperienceProfile
    training: TrainingProfile
    cross_training: list[CrossTraining] = []
    injuries: InjuryProfile

class RunnerProfileUpdate(BaseModel):
    """설정에서 부분 수정"""
    experience: ExperienceProfile | None = None
    training: TrainingProfile | None = None
    cross_training: list[CrossTraining] | None = None
    injuries: InjuryProfile | None = None

class RunnerProfileResponse(BaseModel):
    experience: ExperienceProfile
    training: TrainingProfile
    cross_training: list[CrossTraining]
    injuries: InjuryProfile
    onboarding_completed: bool
```

---

## 4. API 엔드포인트

### 4.1 신규 엔드포인트

| Method | Path                  | Description             | Notes                             |
|--------|-----------------------|-------------------------|-----------------------------------|
| POST   | `/users/profile`      | 온보딩 프로필 제출       | 최초 1회, onboarding_completed 갱신 |
| GET    | `/users/profile`      | 현재 프로필 조회         |                                   |
| PATCH  | `/users/profile`      | 프로필 부분 수정         | 설정 페이지에서 사용               |

### 4.2 기존 엔드포인트 변경

| Method | Path              | 변경 내용                                              |
|--------|-------------------|---------------------------------------------------------|
| POST   | `/auth/signup`    | 응답에 `onboarding_completed: false` 추가               |
| POST   | `/coach/recommend`| context에 runner_profile 자동 포함                      |

### 4.3 POST /users/profile — request/response

```json
// Request
{
  "experience": {
    "level": "intermediate",
    "runs_per_week": 3,
    "longest_distance": "10_21km"
  },
  "training": {
    "preferred_types": ["easy", "interval"],
    "available_days": ["mon", "wed", "sat"],
    "time_per_session": "30_60min"
  },
  "cross_training": ["boxing", "weight"],
  "injuries": {
    "status": {
      "knee": "mild",
      "ankle": "none",
      "achilles": "none",
      "shin": "none",
      "hip_back": "none",
      "plantar_fascia": "none"
    },
    "history": "2024년 좌측 무릎 반월판 수술"
  }
}

// Response — 201 Created
{
  "experience": { ... },
  "training": { ... },
  "cross_training": ["boxing", "weight"],
  "injuries": { ... },
  "onboarding_completed": true
}
```

### 4.4 PATCH /users/profile — 부분 수정

```json
// Request — 변경할 섹션만 전송
{
  "injuries": {
    "status": {
      "knee": "none",
      "ankle": "none",
      "achilles": "mild",
      "shin": "none",
      "hip_back": "none",
      "plantar_fascia": "none"
    },
    "history": "2024년 좌측 무릎 반월판 수술 (완치)"
  }
}

// Response — 200 OK (전체 프로필 반환)
{
  "experience": { ... },
  "training": { ... },
  "cross_training": ["boxing", "weight"],
  "injuries": { ... },
  "onboarding_completed": true
}
```

---

## 5. Service layer

```python
# app/services/profile_service.py

class ProfileService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create_profile(
        self, user_id: str, data: RunnerProfileCreate
    ) -> RunnerProfileResponse:
        profile_dict = data.model_dump()
        await self.user_repo.update(user_id, {
            "runner_profile": profile_dict,
            "onboarding_completed": True,
        })
        return RunnerProfileResponse(
            **profile_dict,
            onboarding_completed=True,
        )

    async def update_profile(
        self, user_id: str, data: RunnerProfileUpdate
    ) -> RunnerProfileResponse:
        user = await self.user_repo.get(user_id)
        current = user.runner_profile or {}

        # 전달된 섹션만 머지
        update_dict = data.model_dump(exclude_none=True)
        merged = {**current, **update_dict}

        await self.user_repo.update(user_id, {"runner_profile": merged})
        return RunnerProfileResponse(
            **merged,
            onboarding_completed=user.onboarding_completed,
        )

    async def get_profile(self, user_id: str) -> RunnerProfileResponse | None:
        user = await self.user_repo.get(user_id)
        if not user.runner_profile:
            return None
        return RunnerProfileResponse(
            **user.runner_profile,
            onboarding_completed=user.onboarding_completed,
        )
```

---

## 6. API route

```python
# app/api/profile.py

router = APIRouter(prefix="/users", tags=["profile"])

@router.post("/profile", status_code=201, response_model=RunnerProfileResponse)
async def create_profile(
    data: RunnerProfileCreate,
    user: User = Depends(get_current_user),
    service: ProfileService = Depends(),
):
    if user.onboarding_completed:
        raise HTTPException(409, "Profile already exists. Use PATCH to update.")
    return await service.create_profile(user.id, data)

@router.get("/profile", response_model=RunnerProfileResponse)
async def get_profile(
    user: User = Depends(get_current_user),
    service: ProfileService = Depends(),
):
    profile = await service.get_profile(user.id)
    if not profile:
        raise HTTPException(404, "Profile not found. Complete onboarding first.")
    return profile

@router.patch("/profile", response_model=RunnerProfileResponse)
async def update_profile(
    data: RunnerProfileUpdate,
    user: User = Depends(get_current_user),
    service: ProfileService = Depends(),
):
    return await service.update_profile(user.id, data)
```

---

## 7. 코칭 엔진 변경

### 7.1 Context Assembler 수정

```python
# app/graph/nodes/context_assembler.py — 변경 부분만

async def assemble_context(state: CoachState) -> CoachState:
    user_id = state["user_id"]

    # 기존 조회 (runs, goals, weekly_stats, weather)
    # ...

    # 추가: runner profile 조회
    user = await user_repo.get(user_id)
    profile = user.runner_profile

    state["context"] = {
        # 기존 필드 유지
        "recent_runs": ...,
        "weekly_volume": ...,
        "goal": ...,
        "today_condition": ...,
        "weather": ...,
        "last_run_days_ago": ...,

        # 추가 필드
        "runner_profile": {
            "experience_level": profile["experience"]["level"],
            "runs_per_week": profile["experience"]["runs_per_week"],
            "longest_distance": profile["experience"]["longest_distance"],
            "preferred_types": profile["training"]["preferred_types"],
            "available_days": profile["training"]["available_days"],
            "time_per_session": profile["training"]["time_per_session"],
            "cross_training": profile.get("cross_training", []),
            "injuries": profile["injuries"]["status"],
            "injury_history": profile["injuries"].get("history"),
        },
        "is_available_day": _is_today_available(
            profile["training"]["available_days"]
        ),
    }
    return state


def _is_today_available(available_days: list[str]) -> bool:
    day_map = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
    today = day_map[date.today().weekday()]
    return today in available_days
```

### 7.2 Rule Engine 추가 룰

기존 룰(VOLUME_EXCEEDED, HARD_DAYS_LIMIT 등)에 프로필 기반 룰을 추가한다.

```python
# app/graph/nodes/rule_engine.py — 추가 룰

def apply_profile_rules(state: CoachState) -> CoachState:
    ctx = state["context"]
    profile = ctx.get("runner_profile", {})
    constraints = state.get("constraints", [])

    # ── 경험 레벨 기반 ──

    level = profile.get("experience_level")

    if level == "beginner":
        constraints.append(
            "BEGINNER_GUARD: 입문자 — 최대 5km, 이지런 위주, "
            "인터벌·템포런 금지. 용어를 쉽게 설명할 것."
        )
    elif level == "novice":
        constraints.append(
            "NOVICE_LIMIT: 초급자 — 최대 8km, 인터벌 주 1회 제한, "
            "페이스 가이드를 구체적으로 제공할 것."
        )

    # ── 시간 제약 ──

    time_budget = profile.get("time_per_session")

    if time_budget == "under_30min":
        constraints.append(
            "TIME_SHORT: 1회 30분 이하 — 장거리(10km+) 추천 금지, "
            "짧은 인터벌이나 4km 이하 템포런 추천."
        )
    elif time_budget == "30_60min":
        constraints.append(
            "TIME_MEDIUM: 1회 30~60분 — 최대 8~10km 세션 구성."
        )

    # ── 가용 요일 ──

    if not ctx.get("is_available_day", True):
        constraints.append(
            "NON_TRAINING_DAY: 오늘은 러닝 예정일이 아님 — "
            "완전 휴식 또는 가벼운 선택 러닝(3km 이지런 이하)만 제안. "
            "사용자가 원하면 뛸 수 있다고 안내."
        )

    # ── 병행 운동 ──

    cross = profile.get("cross_training", [])

    if "weight" in cross or "boxing" in cross:
        constraints.append(
            "CROSS_HIGH_LOAD: 근력/복싱 병행 중 — "
            "하체 고강도 훈련 다음날이면 이지런 권장. "
            "주간 총 운동 부하를 고려하여 러닝 볼륨 20-30% 감소."
        )
    if "cycling" in cross or "swimming" in cross:
        constraints.append(
            "CROSS_CARDIO: 자전거/수영 병행 중 — "
            "유산소 베이스 충분. 러닝은 스피드·주력 향상에 집중 가능."
        )
    if "yoga" in cross:
        constraints.append(
            "CROSS_FLEXIBILITY: 요가/필라테스 병행 중 — "
            "유연성·코어 보강됨. 러닝 쿨다운 스트레칭 간소화 가능."
        )
    if "hiking" in cross:
        constraints.append(
            "CROSS_HIKING: 등산 병행 중 — "
            "등산 다음날 장거리/고강도 회피. 주말 등산 시 러닝 볼륨 조절."
        )

    # ── 부상 ──

    injuries = profile.get("injuries", {})

    injury_rules = {
        "knee": {
            "caution": "INJURY_KNEE_CAUTION: 무릎 주의 — 내리막 인터벌 금지, "
                       "충격 최소화. 트레드밀이나 평지 우선.",
            "severe":  "INJURY_KNEE_SEVERE: 무릎 심각 — 러닝 중단 권고. "
                       "수영·자전거 등 비충격 유산소 추천. 전문의 상담 안내.",
        },
        "ankle": {
            "caution": "INJURY_ANKLE_CAUTION: 발목 주의 — 트레일/울퉁불퉁한 노면 회피. "
                       "평지 이지런 위주.",
            "severe":  "INJURY_ANKLE_SEVERE: 발목 심각 — 러닝 중단 권고.",
        },
        "achilles": {
            "caution": "INJURY_ACHILLES_CAUTION: 아킬레스건 주의 — "
                       "스피드워크 제한, 페이스 10-15% 하향. 힐드롭 스트레칭 포함.",
            "severe":  "INJURY_ACHILLES_SEVERE: 아킬레스건 심각 — 러닝 중단 권고.",
        },
        "shin": {
            "caution": "INJURY_SHIN_CAUTION: 정강이(신스플린트) 주의 — "
                       "볼륨 50% 감소, 이지런 only, 부드러운 노면 추천.",
            "severe":  "INJURY_SHIN_SEVERE: 정강이 심각 — 러닝 중단 권고.",
        },
        "hip_back": {
            "caution": "INJURY_HIP_CAUTION: 허리/고관절 주의 — "
                       "페이스워크 중심, 스트라이드 줄이기. 코어 강화 운동 제안.",
            "severe":  "INJURY_HIP_SEVERE: 허리/고관절 심각 — 러닝 중단 권고.",
        },
        "plantar_fascia": {
            "caution": "INJURY_PF_CAUTION: 족저근막 주의 — "
                       "스피드워크 제한, 쿠셔닝 좋은 신발 안내. 아침 첫 러닝 주의.",
            "severe":  "INJURY_PF_SEVERE: 족저근막 심각 — 러닝 중단 권고.",
        },
    }

    for part, status in injuries.items():
        if status in ("caution", "severe") and part in injury_rules:
            constraints.append(injury_rules[part][status])

    # mild 상태는 LLM에 참고 정보로만 전달 (하드 제약 없음)
    mild_parts = [p for p, s in injuries.items() if s == "mild"]
    if mild_parts:
        parts_kr = {
            "knee": "무릎", "ankle": "발목", "achilles": "아킬레스건",
            "shin": "정강이", "hip_back": "허리/고관절",
            "plantar_fascia": "족저근막",
        }
        names = ", ".join(parts_kr.get(p, p) for p in mild_parts)
        constraints.append(
            f"INJURY_MILD_NOTE: {names} 경미한 불편 — "
            "세션 중 통증 시 즉시 중단 안내. 워밍업에 해당 부위 동적 스트레칭 포함."
        )

    state["constraints"] = constraints
    return state
```

### 7.3 Graph 수정 — 프로필 룰 노드 삽입

```python
# app/graph/coach_graph.py — 변경

def build_coach_graph():
    llm = create_llm_provider()

    workflow = StateGraph(CoachState)

    workflow.add_node("assemble_context", assemble_context)
    workflow.add_node("apply_rules", apply_rules)
    workflow.add_node("apply_profile_rules", apply_profile_rules)  # 추가
    workflow.add_node("call_coach", partial(call_coach, llm=llm))
    workflow.add_node("update_plan", update_plan)
    workflow.add_node("format_response", format_response)

    workflow.set_entry_point("assemble_context")
    workflow.add_edge("assemble_context", "apply_rules")
    workflow.add_edge("apply_rules", "apply_profile_rules")        # 추가
    workflow.add_edge("apply_profile_rules", "call_coach")         # 변경
    workflow.add_edge("call_coach", "update_plan")
    workflow.add_edge("update_plan", "format_response")
    workflow.add_edge("format_response", END)

    return workflow.compile()
```

### 7.4 System prompt 추가 지시

기존 COACH_SYSTEM_PROMPT에 아래 섹션 추가:

```
## 러너 프로필
사용자의 context에 runner_profile이 포함되어 있다.
이를 반드시 참고하여 추천을 개인화하라.

- experience_level에 따라 용어 수준을 조절하라.
  beginner에게는 "인터벌"이 아닌 "빠르게-느리게 반복 달리기"처럼 풀어서 설명.
  advanced에게는 전문 용어와 구체적 페이스를 사용.
- available_days를 참고하되, 오늘이 비훈련일이어도 사용자가 코칭을 요청했다면
  가벼운 선택지를 제공하라. "쉬세요"만 하지 말 것.
- cross_training은 보완 효과와 부하 중복을 함께 고려하라.
- injuries에 caution/severe가 있으면 제약 조건을 반드시 준수하라.
  severe인 부위가 하나라도 있으면 전문의 상담을 권하는 문구를 포함하라.
- injury_history는 과거 이력이므로 현재 상태(injuries.status)를 우선하되,
  재발 위험을 고려한 보수적 추천을 하라.
```

---

## 8. 에러 코드 추가

| Code                   | HTTP | Description                    |
|------------------------|------|--------------------------------|
| PROFILE_ALREADY_EXISTS | 409  | 이미 온보딩 완료, PATCH 사용    |
| PROFILE_NOT_FOUND      | 404  | 온보딩 미완료                   |
| ONBOARDING_REQUIRED    | 403  | 프로필 없이 /coach 호출 시      |

---

## 9. Coach 미들웨어 — 온보딩 체크

```python
# app/dependencies.py — 추가

async def require_onboarding(user: User = Depends(get_current_user)) -> User:
    if not user.onboarding_completed:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "ONBOARDING_REQUIRED",
                    "message": "Complete onboarding first.",
                }
            },
        )
    return user
```

`/coach/recommend` 엔드포인트에 이 의존성을 추가하여,
온보딩 미완료 사용자가 코칭 요청 시 403을 반환한다.
프론트에서는 403 수신 시 온보딩 페이지로 리디렉트.

---

## 10. 파일 변경 요약

### 신규 파일

```
app/schemas/runner_profile.py    # Pydantic 스키마 + Enum
app/api/profile.py               # 프로필 CRUD 엔드포인트
app/services/profile_service.py  # 프로필 비즈니스 로직
alembic/versions/xxxx_add_runner_profile.py  # 마이그레이션
```

### 수정 파일

```
app/models/user.py               # runner_profile JSONB, onboarding_completed 컬럼 추가
app/dependencies.py              # require_onboarding 의존성 추가
app/main.py                      # profile router 등록
app/graph/nodes/context_assembler.py  # runner_profile context 포함
app/graph/nodes/rule_engine.py        # profile 기반 룰 추가 (apply_profile_rules)
app/graph/coach_graph.py              # apply_profile_rules 노드 삽입
app/graph/prompts.py                  # system prompt 러너 프로필 섹션 추가
app/api/coach.py                      # require_onboarding 의존성 적용
```

---

## 11. 실행 계획

### Step 1: DB + 스키마 (0.5일)

- [ ] Alembic 마이그레이션 (runner_profile, onboarding_completed)
- [ ] RunnerProfileCreate / Update / Response 스키마
- [ ] Enum 정의 (ExperienceLevel, InjuryStatus 등)

### Step 2: API + Service (0.5일)

- [ ] ProfileService 구현
- [ ] profile.py 라우터 (POST, GET, PATCH)
- [ ] require_onboarding 의존성
- [ ] main.py에 라우터 등록
- [ ] 테스트: 온보딩 → 프로필 조회 → 부분 수정 플로우

### Step 3: 코칭 엔진 연동 (1일)

- [ ] Context Assembler에 runner_profile 추가
- [ ] apply_profile_rules 노드 구현 (경험/시간/요일/병행/부상 룰)
- [ ] Graph에 노드 삽입
- [ ] System prompt 수정
- [ ] 테스트: 초급+무릎주의 프로필 → 인터벌 추천 안 나오는지 검증
- [ ] 테스트: 비훈련일 → 선택 러닝만 나오는지 검증

**총 소요: ~2일**