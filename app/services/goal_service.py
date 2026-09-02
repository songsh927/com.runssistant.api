from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.goal import Goal
from app.repositories.goal_repo import GoalRepository
from app.schemas.goal import GoalCreate, GoalStatusUpdate, GoalUpdate
from app.services.plan_service import PlanService

_repo = GoalRepository()
_plan_svc = PlanService()


class GoalService:
    async def create(self, session: AsyncSession, user_id: str, data: GoalCreate) -> Goal:
        previous_active = await _repo.get_active(session, user_id)
        if previous_active is not None:
            previous_active.status = "abandoned"
            await session.flush()

        goal = await _repo.create(
            session,
            user_id=user_id,
            goal_type=data.goal_type,
            weekly_km_target=data.weekly_km_target,
            race_name=data.race_name,
            race_date=data.race_date,
            race_target_time=data.race_target_time,
            race_distance_km=data.race_distance_km,
        )
        await _plan_svc.drop_untouched_current(session, user_id)
        return goal

    async def list(
        self, session: AsyncSession, user_id: str, status: str | None = None
    ) -> list[Goal]:
        return await _repo.list_goals(session, user_id, status)

    async def get_active(self, session: AsyncSession, user_id: str) -> Goal:
        goal = await _repo.get_active(session, user_id)
        if goal is None:
            raise NotFound("활성 목표가 없습니다.")
        return goal

    async def get(self, session: AsyncSession, goal_id: str, user_id: str) -> Goal:
        goal = await _repo.get_by_id(session, goal_id, user_id)
        if goal is None:
            raise NotFound()
        return goal

    async def update(
        self, session: AsyncSession, goal_id: str, user_id: str, data: GoalUpdate
    ) -> Goal:
        goal = await self.get(session, goal_id, user_id)
        update_data = data.model_dump(exclude_unset=True)
        return await _repo.update(session, goal, update_data)

    async def update_status(
        self, session: AsyncSession, goal_id: str, user_id: str, data: GoalStatusUpdate
    ) -> Goal:
        goal = await self.get(session, goal_id, user_id)
        return await _repo.update(session, goal, {"status": data.status})
