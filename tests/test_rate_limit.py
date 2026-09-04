"""Rate limiting 테스트."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429(client: AsyncClient) -> None:
    """Redis 카운터가 한도 초과 시 429 + RATE_LIMITED 봉투 반환."""
    with patch("app.core.rate_limit.redis_client") as mock_redis:
        mock_redis.incr = AsyncMock(return_value=999)
        mock_redis.expire = AsyncMock(return_value=True)
        resp = await client.get("/health")

    assert resp.status_code == 429
    body = resp.json()
    assert body["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_rate_limit_redis_failure_fails_open(client: AsyncClient) -> None:
    """Redis 장애 시 요청이 통과(fail-open)돼야 한다."""
    with patch("app.core.rate_limit.redis_client") as mock_redis:
        mock_redis.incr = AsyncMock(side_effect=Exception("redis down"))
        resp = await client.get("/health")

    # 장애 시 요청 차단 없이 정상 통과
    assert resp.status_code == 200
