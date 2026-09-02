from datetime import date

from pydantic import BaseModel


class WeeklyStats(BaseModel):
    week_start: date
    total_km: float
    target_km: float | None = None
    progress_pct: int | None = None
    session_count: int
    avg_pace_sec: int | None
    avg_pace_display: str | None
    avg_rpe: float | None = None
    run_type_breakdown: dict[str, int]


class TrendPoint(BaseModel):
    week_start: date
    total_km: float
    session_count: int
    avg_pace_sec: int | None
    avg_pace_display: str | None


class PersonalBest(BaseModel):
    distance_bucket: str
    best_pace_sec: int
    best_pace_display: str
    achieved_on: date
