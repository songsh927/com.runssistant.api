from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coaching_session import CoachingSession


class CoachingRepository:
    async def create(self, session: AsyncSession, **kwargs: Any) -> CoachingSession:
        coaching_session = CoachingSession(**kwargs)
        session.add(coaching_session)
        await session.flush()
        await session.refresh(coaching_session)
        return coaching_session

    async def get_by_id(
        self, session: AsyncSession, coaching_session_id: str, user_id: str
    ) -> CoachingSession | None:
        result = await session.execute(
            select(CoachingSession).where(
                and_(
                    CoachingSession.id == coaching_session_id,
                    CoachingSession.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_recent(
        self, session: AsyncSession, user_id: str, limit: int = 10
    ) -> list[CoachingSession]:
        result = await session.execute(
            select(CoachingSession)
            .where(CoachingSession.user_id == user_id)
            .order_by(CoachingSession.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(
        self, session: AsyncSession, coaching_session: CoachingSession, data: dict[str, Any]
    ) -> CoachingSession:
        for key, value in data.items():
            setattr(coaching_session, key, value)
        await session.flush()
        await session.refresh(coaching_session)
        return coaching_session
