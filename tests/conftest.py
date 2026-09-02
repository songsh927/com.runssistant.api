import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.dependencies import get_db, get_weather_service
from app.main import app
from app.models.base import Base
from app.services.weather_service import WeatherService

test_engine = create_async_engine(settings.DATABASE_URL_TEST, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

_FAKE_WEATHER: dict[str, Any] = {
    "temp_c": 20.0,
    "feels_like_c": 19.0,
    "humidity": 60,
    "condition": "clear sky",
    "wind_speed_ms": 3.0,
}


class FakeWeatherService(WeatherService):
    async def get_current(self, location: str) -> dict[str, Any] | None:
        return _FAKE_WEATHER


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db() -> AsyncGenerator[None, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    def override_weather() -> WeatherService:
        return FakeWeatherService()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_weather_service] = override_weather
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    uid = str(uuid.uuid4())[:8]
    user = {
        "email": f"runner_{uid}@example.com",
        "password": "password123",
        "name": "Test Runner",
        "location": "Seoul",
    }
    resp = await client.post("/auth/signup", json=user)
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
