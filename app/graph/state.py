from typing import Any, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.weather_service import WeatherService


class CoachState(TypedDict):
    db_session: AsyncSession
    weather_service: WeatherService
    user_id: str
    user_location: str | None
    rpe: int | None
    notes: str | None
    context: dict[str, Any]
    constraints: list[dict[str, str]]
    recommendation: dict[str, Any]
    model_used: str
    coaching_session_id: str
    response: dict[str, Any]
