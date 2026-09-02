from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pace import get_monday
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.stats import PersonalBest, TrendPoint, WeeklyStats
from app.services.stats_service import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])
_svc = StatsService()


@router.get("/weekly", response_model=WeeklyStats)
async def weekly_stats(
    week_start: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeeklyStats:
    start = week_start or get_monday(date.today())
    return await _svc.get_weekly_stats(db, current_user.id, start)


@router.get("/trend", response_model=list[TrendPoint])
async def trend(
    weeks: int = Query(default=12, ge=1, le=52),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TrendPoint]:
    return await _svc.get_trend(db, current_user.id, weeks)


@router.get("/personal-bests", response_model=list[PersonalBest])
async def personal_bests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PersonalBest]:
    return await _svc.get_personal_bests(db, current_user.id)
