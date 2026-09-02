from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.run import Run


class RunRepository:
    async def create(self, session: AsyncSession, **kwargs: Any) -> Run:
        run = Run(**kwargs)
        session.add(run)
        await session.flush()
        await session.refresh(run)
        return run

    async def get_by_id(self, session: AsyncSession, run_id: str, user_id: str) -> Run | None:
        result = await session.execute(
            select(Run).where(
                and_(Run.id == run_id, Run.user_id == user_id, Run.deleted_at.is_(None))
            )
        )
        return result.scalar_one_or_none()

    async def list_runs(
        self,
        session: AsyncSession,
        user_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Run]:
        conditions = [Run.user_id == user_id, Run.deleted_at.is_(None)]
        if from_date is not None:
            conditions.append(Run.run_date >= from_date)
        if to_date is not None:
            conditions.append(Run.run_date <= to_date)
        result = await session.execute(
            select(Run)
            .where(and_(*conditions))
            .order_by(Run.run_date.desc(), Run.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count(self, session: AsyncSession, user_id: str) -> int:
        result = await session.execute(
            select(func.count())
            .select_from(Run)
            .where(and_(Run.user_id == user_id, Run.deleted_at.is_(None)))
        )
        return result.scalar_one()

    async def update(self, session: AsyncSession, run: Run, data: dict[str, Any]) -> Run:
        for key, value in data.items():
            setattr(run, key, value)
        await session.flush()
        await session.refresh(run)
        return run

    async def soft_delete(self, session: AsyncSession, run: Run) -> None:
        run.deleted_at = datetime.now(UTC)
        await session.flush()

    async def get_range(
        self,
        session: AsyncSession,
        user_id: str,
        from_date: date,
        to_date: date,
    ) -> list[Run]:
        result = await session.execute(
            select(Run).where(
                and_(
                    Run.user_id == user_id,
                    Run.deleted_at.is_(None),
                    Run.run_date >= from_date,
                    Run.run_date <= to_date,
                )
            )
        )
        return list(result.scalars().all())
