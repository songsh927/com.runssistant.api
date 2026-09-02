from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.graph.state import CoachState
from app.models.coaching_session import CoachingSession
from app.repositories.coaching_repo import CoachingRepository
from app.services.weather_service import WeatherService

_coaching_repo = CoachingRepository()


class CoachService:
    async def recommend(
        self,
        session: AsyncSession,
        graph: Any,
        weather_service: WeatherService,
        user_id: str,
        user_location: str | None,
        rpe: int | None,
        notes: str | None,
    ) -> dict[str, Any]:
        initial_state: CoachState = {
            "db_session": session,
            "weather_service": weather_service,
            "user_id": user_id,
            "user_location": user_location,
            "rpe": rpe,
            "notes": notes,
            "context": {},
            "constraints": [],
            "recommendation": {},
            "model_used": "",
            "coaching_session_id": "",
            "response": {},
        }
        final_state = await graph.ainvoke(initial_state)
        return final_state["response"]  # type: ignore[no-any-return]

    async def submit_feedback(
        self, session: AsyncSession, coaching_session_id: str, user_id: str, rating: int
    ) -> CoachingSession:
        coaching_session = await _coaching_repo.get_by_id(session, coaching_session_id, user_id)
        if coaching_session is None:
            raise NotFound()
        return await _coaching_repo.update(session, coaching_session, {"user_feedback": rating})

    async def get_history(
        self, session: AsyncSession, user_id: str, limit: int = 10
    ) -> list[CoachingSession]:
        return await _coaching_repo.list_recent(session, user_id, limit)
