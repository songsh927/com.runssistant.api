from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, get_weather_service
from app.models.user import User
from app.schemas.run import RunCreate, RunResponse, RunUpdate
from app.services.run_service import RunService
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/runs", tags=["runs"])
_svc = RunService()


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    body: RunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    weather_service: WeatherService = Depends(get_weather_service),
) -> RunResponse:
    run = await _svc.create_run(db, current_user.id, body, weather_service, current_user.location)
    await db.commit()
    return RunResponse.model_validate(run)


@router.get("", response_model=list[RunResponse])
async def list_runs(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RunResponse]:
    runs = await _svc.list(db, current_user.id, from_date, to_date, limit, offset)
    return [RunResponse.model_validate(r) for r in runs]


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RunResponse:
    run = await _svc.get(db, run_id, current_user.id)
    return RunResponse.model_validate(run)


@router.put("/{run_id}", response_model=RunResponse)
async def update_run(
    run_id: str,
    body: RunUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RunResponse:
    run = await _svc.update(db, run_id, current_user.id, body)
    await db.commit()
    return RunResponse.model_validate(run)


@router.delete("/{run_id}", status_code=204)
async def delete_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    await _svc.delete(db, run_id, current_user.id)
    await db.commit()
    return Response(status_code=204)
