from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.run import Run
from app.repositories.run_repo import RunRepository
from app.schemas.run import RunCreate, RunUpdate
from app.services.plan_service import PlanService
from app.services.weather_service import WeatherService

_repo = RunRepository()
_plan_svc = PlanService()


class RunService:
    async def create_run(
        self,
        session: AsyncSession,
        user_id: str,
        data: RunCreate,
        weather_service: WeatherService,
        user_location: str | None = None,
    ) -> Run:
        weather_snapshot = None
        if user_location:
            weather_snapshot = await weather_service.get_current(user_location)

        run = await _repo.create(
            session,
            user_id=user_id,
            run_date=data.run_date,
            distance_km=data.distance_km,
            duration_sec=data.duration_sec,
            run_type=data.run_type,
            rpe=data.rpe,
            notes=data.notes,
            weather_snapshot=weather_snapshot,
        )
        await _plan_svc.mark_session_completed(session, user_id, run)
        return run

    async def get(self, session: AsyncSession, run_id: str, user_id: str) -> Run:
        run = await _repo.get_by_id(session, run_id, user_id)
        if run is None:
            raise NotFound()
        return run

    async def list(
        self,
        session: AsyncSession,
        user_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Run]:
        return await _repo.list_runs(session, user_id, from_date, to_date, limit, offset)

    async def update(
        self,
        session: AsyncSession,
        run_id: str,
        user_id: str,
        data: RunUpdate,
    ) -> Run:
        run = await self.get(session, run_id, user_id)
        update_data = data.model_dump(exclude_unset=True)
        return await _repo.update(session, run, update_data)

    async def delete(self, session: AsyncSession, run_id: str, user_id: str) -> None:
        run = await self.get(session, run_id, user_id)
        await _plan_svc.unmark_session(session, user_id, run)
        await _repo.soft_delete(session, run)
