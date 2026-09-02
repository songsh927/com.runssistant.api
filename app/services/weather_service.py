import json
import logging
from typing import Any

import httpx

from app.config import settings
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

_CACHE_TTL = 1800  # 30 minutes
_OWM_URL = "https://api.openweathermap.org/data/2.5/weather"


class WeatherService:
    async def get_current(self, location: str) -> dict[str, Any] | None:
        try:
            cached = await redis_client.get(f"weather:{location}")
            if cached:
                return json.loads(cached)  # type: ignore[no-any-return]

            if not settings.OWM_API_KEY:
                return None

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    _OWM_URL,
                    params={"q": location, "appid": settings.OWM_API_KEY, "units": "metric"},
                )
                resp.raise_for_status()
                data = resp.json()

            snapshot: dict[str, Any] = {
                "temp_c": data["main"]["temp"],
                "feels_like_c": data["main"]["feels_like"],
                "humidity": data["main"]["humidity"],
                "condition": data["weather"][0]["description"],
                "wind_speed_ms": data["wind"]["speed"],
            }
            await redis_client.setex(f"weather:{location}", _CACHE_TTL, json.dumps(snapshot))
            return snapshot
        except Exception:
            logger.exception("Weather fetch failed for location=%s", location)
            return None
