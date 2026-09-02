from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.pace import format_pace

RunType = Literal["easy", "tempo", "interval", "long_run", "race", "recovery"]


class RunCreate(BaseModel):
    run_date: date
    distance_km: Decimal = Field(gt=0)
    duration_sec: int = Field(gt=0)
    run_type: RunType
    rpe: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = None


class RunUpdate(BaseModel):
    run_date: date | None = None
    distance_km: Decimal | None = Field(default=None, gt=0)
    duration_sec: int | None = Field(default=None, gt=0)
    run_type: RunType | None = None
    rpe: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = None


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    run_date: date
    distance_km: float
    duration_sec: int
    avg_pace_sec: int | None
    run_type: str
    rpe: int | None
    notes: str | None
    weather_snapshot: dict[str, Any] | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def avg_pace_display(self) -> str | None:
        if self.avg_pace_sec is None:
            return None
        return format_pace(self.avg_pace_sec)
