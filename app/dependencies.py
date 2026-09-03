from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Unauthorized
from app.core.security import decode_token
from app.db import AsyncSessionLocal
from app.graph.coach_graph import build_coach_graph
from app.llm.factory import create_llm_provider
from app.models.user import User
from app.services.weather_service import WeatherService

_bearer = HTTPBearer()
_coach_graph: Any = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_token(credentials.credentials)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise Unauthorized()
    return user


def get_weather_service() -> WeatherService:
    return WeatherService()


def get_coach_graph() -> Any:
    global _coach_graph
    if _coach_graph is None:
        _coach_graph = build_coach_graph(create_llm_provider())
    return _coach_graph
