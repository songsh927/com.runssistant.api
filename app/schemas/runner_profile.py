from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.run import RunType

DayOfWeek = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class ExperienceLevel(str, Enum):
    BEGINNER = "beginner"
    NOVICE = "novice"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


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
    MILD = "mild"
    CAUTION = "caution"
    SEVERE = "severe"


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


class ExperienceProfile(BaseModel):
    level: ExperienceLevel
    runs_per_week: int = Field(ge=0, le=7)
    longest_distance: LongestDistance


class TrainingProfile(BaseModel):
    preferred_types: list[RunType] = Field(min_length=1)
    available_days: list[DayOfWeek] = Field(min_length=1)
    time_per_session: TimePerSession


class InjuryProfile(BaseModel):
    status: dict[InjuryPart, InjuryStatus] = Field(
        default_factory=lambda: {part: InjuryStatus.NONE for part in InjuryPart}
    )
    history: str | None = Field(None, max_length=500)


class RunnerProfileCreate(BaseModel):
    experience: ExperienceProfile
    training: TrainingProfile
    cross_training: list[CrossTraining] = []
    injuries: InjuryProfile = Field(default_factory=InjuryProfile)


class RunnerProfileUpdate(BaseModel):
    experience: ExperienceProfile | None = None
    training: TrainingProfile | None = None
    cross_training: list[CrossTraining] | None = None
    injuries: InjuryProfile | None = None


class RunnerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    experience: ExperienceProfile
    training: TrainingProfile
    cross_training: list[CrossTraining]
    injuries: InjuryProfile
    onboarding_completed: bool
