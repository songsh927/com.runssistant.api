"""에러 핸들러 통일 테스트."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_validation_error_envelope_on_invalid_run(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """distance_km <= 0 → 400 + VALIDATION_ERROR 봉투."""
    resp = await client.post(
        "/runs",
        json={
            "run_date": "2024-01-01",
            "distance_km": -5,
            "duration_sec": 3600,
            "run_type": "easy",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in body["error"]


@pytest.mark.asyncio
async def test_not_found_returns_envelope(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """존재하지 않는 run → 404 + NOT_FOUND 봉투."""
    resp = await client.get("/runs/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_unauthorized_no_token(client: AsyncClient) -> None:
    """인증 헤더 없이 보호된 엔드포인트 접근 → 401/403 + error 봉투."""
    resp = await client.get("/runs")
    assert resp.status_code in (401, 403)
    body = resp.json()
    assert "error" in body


@pytest.mark.asyncio
async def test_response_has_request_id_header(client: AsyncClient) -> None:
    """모든 응답에 X-Request-ID 헤더가 있어야 한다."""
    resp = await client.get("/health")
    assert "x-request-id" in resp.headers
    assert len(resp.headers["x-request-id"]) == 36  # UUID 길이
