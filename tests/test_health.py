"""health / readiness 엔드포인트 테스트."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_returns_status(client: AsyncClient) -> None:
    """readiness는 DB·Redis 상태를 포함한 응답을 반환해야 한다."""
    resp = await client.get("/readiness")
    # 로컬 환경에서 DB·Redis 연결 여부에 따라 200 또는 503
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "status" in body
    assert "checks" in body
    assert "database" in body["checks"]
    assert "redis" in body["checks"]
