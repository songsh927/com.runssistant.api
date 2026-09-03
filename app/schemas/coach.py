from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.plan import PaceRange

CoachRunType = Literal["easy", "tempo", "interval", "long_run", "recovery", "rest"]


class RecommendRequest(BaseModel):
    rpe: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = None


class CoachRecommendation(BaseModel):
    """LLM 출력 검증 = 신뢰 경계. 이 모델을 통과하지 못한 응답은 DB에 쓰지 않는다."""

    run_type: CoachRunType
    distance_km: float = Field(ge=0)
    pace_range: PaceRange | None = None
    warmup: str
    main_session: str
    cooldown: str
    reasoning: str
    motivation: str


class WeeklyContext(BaseModel):
    completed_km: float
    target_km: float | None
    progress_pct: int | None
    remaining_days: int
    sessions_done: int
    plan_adjustment: str | None


class WeatherContext(BaseModel):
    temp_c: float | None
    humidity: int | None
    condition: str | None


class RecommendResponse(BaseModel):
    session_id: str
    recommendation: CoachRecommendation
    weekly_context: WeeklyContext
    weather: WeatherContext | None


class FeedbackRequest(BaseModel):
    coaching_session_id: str
    rating: int = Field(ge=1, le=5)


class CoachingSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    constraints: list[dict[str, str]] | None
    recommendation: CoachRecommendation
    model_used: str | None
    user_feedback: int | None
    created_at: datetime
