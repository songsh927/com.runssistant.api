from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal import Goal


class GoalRepository:
    async def create(self, session: AsyncSession, **kwargs: Any) -> Goal:
        goal = Goal(**kwargs)
        session.add(goal)
        await session.flush()
        await session.refresh(goal)
        return goal

    async def get_by_id(self, session: AsyncSession, goal_id: str, user_id: str) -> Goal | None:
        result = await session.execute(
            select(Goal).where(and_(Goal.id == goal_id, Goal.user_id == user_id))
        )
        return result.scalar_one_or_none()

    async def list_goals(
        self, session: AsyncSession, user_id: str, status: str | None = None
    ) -> list[Goal]:
        conditions = [Goal.user_id == user_id]
        if status is not None:
            conditions.append(Goal.status == status)
        result = await session.execute(
            select(Goal).where(and_(*conditions)).order_by(Goal.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_active(self, session: AsyncSession, user_id: str) -> Goal | None:
        result = await session.execute(
            select(Goal)
            .where(and_(Goal.user_id == user_id, Goal.status == "active"))
            .order_by(Goal.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update(self, session: AsyncSession, goal: Goal, data: dict[str, Any]) -> Goal:
        for key, value in data.items():
            setattr(goal, key, value)
        await session.flush()
        await session.refresh(goal)
        return goal
