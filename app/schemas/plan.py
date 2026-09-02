from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PlannedSession(BaseModel):
    day: str
    type: str
    distance_km: float
    pace_range: dict[str, str] | None = None
    status: str
    actual_distance_km: float | None = None
    run_id: str | None = None
    unplanned: bool = False


class WeeklyPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    goal_id: str | None
    week_start: date
    planned_sessions: list[PlannedSession]
    total_planned_km: float | None
    completed_km: float
    remaining_km: float | None
    progress_pct: int | None
    adjustments_log: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
