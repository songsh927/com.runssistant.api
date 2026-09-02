from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

GoalType = Literal["weekly_volume", "race"]
GoalStatus = Literal["active", "completed", "abandoned"]


class GoalCreate(BaseModel):
    goal_type: GoalType
    weekly_km_target: Decimal | None = Field(default=None, gt=0)
    race_name: str | None = Field(default=None, max_length=200)
    race_date: date | None = None
    race_target_time: int | None = Field(default=None, gt=0)
    race_distance_km: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check_required_fields(self) -> "GoalCreate":
        if self.goal_type == "weekly_volume" and self.weekly_km_target is None:
            raise ValueError("weekly_volume 목표는 weekly_km_target이 필요합니다.")
        if self.goal_type == "race" and (
            self.race_name is None or self.race_date is None or self.race_distance_km is None
        ):
            raise ValueError("race 목표는 race_name, race_date, race_distance_km이 필요합니다.")
        return self


class GoalUpdate(BaseModel):
    weekly_km_target: Decimal | None = Field(default=None, gt=0)
    race_name: str | None = Field(default=None, max_length=200)
    race_date: date | None = None
    race_target_time: int | None = Field(default=None, gt=0)
    race_distance_km: Decimal | None = Field(default=None, gt=0)


class GoalStatusUpdate(BaseModel):
    status: Literal["completed", "abandoned"]


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    goal_type: str
    weekly_km_target: float | None
    race_name: str | None
    race_date: date | None
    race_target_time: int | None
    race_distance_km: float | None
    status: str
    created_at: datetime
    updated_at: datetime
