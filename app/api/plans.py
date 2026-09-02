from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.plan import WeeklyPlanResponse
from app.services.plan_service import PlanService

router = APIRouter(prefix="/plans", tags=["plans"])
_svc = PlanService()


@router.get("/current", response_model=WeeklyPlanResponse)
async def get_current_plan(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeeklyPlanResponse:
    plan = await _svc.get_current(db, current_user.id)
    # get_current may create a new plan as a side effect, so it must be committed.
    await db.commit()
    return plan


@router.get("/history", response_model=list[WeeklyPlanResponse])
async def get_plan_history(
    weeks: int = Query(default=8, ge=1, le=52),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WeeklyPlanResponse]:
    return await _svc.get_history(db, current_user.id, weeks)


@router.get("/{week_start}", response_model=WeeklyPlanResponse)
async def get_plan_by_week(
    week_start: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeeklyPlanResponse:
    return await _svc.get_by_week(db, current_user.id, week_start)
