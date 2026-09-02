from datetime import date
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weekly_plan import WeeklyPlan


class PlanRepository:
    async def create(self, session: AsyncSession, **kwargs: Any) -> WeeklyPlan:
        plan = WeeklyPlan(**kwargs)
        session.add(plan)
        await session.flush()
        await session.refresh(plan)
        return plan

    async def get_by_week(
        self, session: AsyncSession, user_id: str, week_start: date
    ) -> WeeklyPlan | None:
        result = await session.execute(
            select(WeeklyPlan).where(
                and_(WeeklyPlan.user_id == user_id, WeeklyPlan.week_start == week_start)
            )
        )
        return result.scalar_one_or_none()

    async def list_recent(
        self, session: AsyncSession, user_id: str, weeks: int
    ) -> list[WeeklyPlan]:
        result = await session.execute(
            select(WeeklyPlan)
            .where(WeeklyPlan.user_id == user_id)
            .order_by(WeeklyPlan.week_start.desc())
            .limit(weeks)
        )
        plans = list(result.scalars().all())
        plans.reverse()
        return plans

    async def update(
        self, session: AsyncSession, plan: WeeklyPlan, data: dict[str, Any]
    ) -> WeeklyPlan:
        for key, value in data.items():
            setattr(plan, key, value)
        await session.flush()
        await session.refresh(plan)
        return plan

    async def delete(self, session: AsyncSession, plan: WeeklyPlan) -> None:
        await session.delete(plan)
        await session.flush()
