"""Rate limiting 테스트 — AI(LLM) 엔드포인트만 한도를 받는다."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

# 미들웨어는 인증보다 먼저 돌므로 토큰 없이도 rate limit 동작을 검증할 수 있다.
_AI_PATH = "/coach/recommend"


@pytest.mark.asyncio
async def test_ai_endpoint_rate_limit_exceeded_returns_429(client: AsyncClient) -> None:
    """AI 엔드포인트에서 Redis 카운터가 한도 초과 시 429 + RATE_LIMITED 봉투 반환."""
    with patch("app.core.rate_limit.redis_client") as mock_redis:
        mock_redis.incr = AsyncMock(return_value=999)
        mock_redis.expire = AsyncMock(return_value=True)
        resp = await client.post(_AI_PATH, json={})

    assert resp.status_code == 429
    body = resp.json()
    assert body["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_non_ai_endpoint_is_not_rate_limited(client: AsyncClient) -> None:
    """AI를 쓰지 않는 경로는 카운터가 한도를 넘겨도 통과하고, Redis를 조회조차 하지 않는다."""
    with patch("app.core.rate_limit.redis_client") as mock_redis:
        mock_redis.incr = AsyncMock(return_value=999)
        mock_redis.expire = AsyncMock(return_value=True)
        resp = await client.get("/health")

    assert resp.status_code == 200
    mock_redis.incr.assert_not_awaited()


@pytest.mark.asyncio
async def test_rate_limit_redis_failure_fails_open(client: AsyncClient) -> None:
    """Redis 장애 시 AI 엔드포인트 요청도 차단되지 않고 통과(fail-open)돼야 한다."""
    with patch("app.core.rate_limit.redis_client") as mock_redis:
        mock_redis.incr = AsyncMock(side_effect=Exception("redis down"))
        resp = await client.post(_AI_PATH, json={})

    # 429로 막히지 않고 애플리케이션까지 도달 (토큰이 없으므로 인증 단계에서 거부됨)
    assert resp.status_code != 429
    assert resp.status_code in (401, 403)
