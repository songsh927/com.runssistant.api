from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.runner_profile import (
    RunnerProfileCreate,
    RunnerProfileResponse,
    RunnerProfileUpdate,
)
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/users", tags=["profile"])
_svc = ProfileService()


@router.post("/profile", status_code=201, response_model=RunnerProfileResponse)
async def create_profile(
    body: RunnerProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RunnerProfileResponse:
    profile = await _svc.create_profile(db, current_user.id, body)
    await db.commit()
    return profile


@router.get("/profile", response_model=RunnerProfileResponse)
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RunnerProfileResponse:
    return await _svc.get_profile(db, current_user.id)


@router.patch("/profile", response_model=RunnerProfileResponse)
async def update_profile(
    body: RunnerProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RunnerProfileResponse:
    profile = await _svc.update_profile(db, current_user.id, body)
    await db.commit()
    return profile
