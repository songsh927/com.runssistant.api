from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.goal import GoalCreate, GoalResponse, GoalStatusUpdate, GoalUpdate
from app.services.goal_service import GoalService

router = APIRouter(prefix="/goals", tags=["goals"])
_svc = GoalService()


@router.post("", response_model=GoalResponse, status_code=201)
async def create_goal(
    body: GoalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalResponse:
    goal = await _svc.create(db, current_user.id, body)
    await db.commit()
    return GoalResponse.model_validate(goal)


@router.get("", response_model=list[GoalResponse])
async def list_goals(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[GoalResponse]:
    goals = await _svc.list(db, current_user.id, status)
    return [GoalResponse.model_validate(g) for g in goals]


@router.get("/active", response_model=GoalResponse)
async def get_active_goal(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalResponse:
    goal = await _svc.get_active(db, current_user.id)
    return GoalResponse.model_validate(goal)


@router.put("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: str,
    body: GoalUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalResponse:
    goal = await _svc.update(db, goal_id, current_user.id, body)
    await db.commit()
    return GoalResponse.model_validate(goal)


@router.patch("/{goal_id}/status", response_model=GoalResponse)
async def update_goal_status(
    goal_id: str,
    body: GoalStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalResponse:
    goal = await _svc.update_status(db, goal_id, current_user.id, body)
    await db.commit()
    return GoalResponse.model_validate(goal)
