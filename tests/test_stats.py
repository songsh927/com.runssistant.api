import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.core.pace import get_monday


def _make_user() -> dict[str, str]:
    uid = str(uuid.uuid4())[:8]
    return {
        "email": f"runner_{uid}@example.com",
        "password": "password123",
        "name": "Test Runner",
        "location": "Seoul",
    }


async def _signup(client: AsyncClient) -> dict[str, str]:
    resp = await client.post("/auth/signup", json=_make_user())
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_run(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    run_date: date,
    distance_km: str = "5.00",
    duration_sec: int = 1800,
    run_type: str = "easy",
) -> dict[str, object]:
    resp = await client.post(
        "/runs",
        json={
            "run_date": str(run_date),
            "distance_km": distance_km,
            "duration_sec": duration_sec,
            "run_type": run_type,
        },
        headers=headers,
    )
    return resp.json()  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_weekly_stats_empty(client: AsyncClient) -> None:
    headers = await _signup(client)
    monday = get_monday(date.today())
    resp = await client.get(f"/stats/weekly?week_start={monday}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_km"] == 0.0
    assert body["session_count"] == 0
    assert body["avg_pace_sec"] is None
    assert body["run_type_breakdown"] == {}


@pytest.mark.asyncio
async def test_weekly_stats_with_data(client: AsyncClient) -> None:
    headers = await _signup(client)
    monday = get_monday(date.today())

    await _create_run(
        client, headers, run_date=monday, distance_km="10.00", duration_sec=3600, run_type="tempo"
    )
    await _create_run(
        client, headers, run_date=monday + timedelta(days=1), distance_km="5.00", duration_sec=1800
    )
    await _create_run(
        client, headers, run_date=monday + timedelta(days=2), distance_km="5.00", duration_sec=1800
    )

    resp = await client.get(f"/stats/weekly?week_start={monday}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_km"] == 20.0
    assert body["session_count"] == 3
    assert body["avg_pace_sec"] == 360  # 7200 sec / 20 km
    assert body["avg_pace_display"] == "6:00/km"
    assert body["run_type_breakdown"]["easy"] == 2
    assert body["run_type_breakdown"]["tempo"] == 1


@pytest.mark.asyncio
async def test_trend_length(client: AsyncClient) -> None:
    headers = await _signup(client)
    resp = await client.get("/stats/trend?weeks=4", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 4


@pytest.mark.asyncio
async def test_trend_chronological_order(client: AsyncClient) -> None:
    headers = await _signup(client)
    resp = await client.get("/stats/trend?weeks=3", headers=headers)
    points = resp.json()
    dates = [p["week_start"] for p in points]
    assert dates == sorted(dates)


@pytest.mark.asyncio
async def test_personal_bests_empty(client: AsyncClient) -> None:
    headers = await _signup(client)
    resp = await client.get("/stats/personal-bests", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_personal_bests_5k(client: AsyncClient) -> None:
    headers = await _signup(client)
    await _create_run(client, headers, run_date=date.today(), distance_km="5.00", duration_sec=1500)

    resp = await client.get("/stats/personal-bests", headers=headers)
    assert resp.status_code == 200
    bests = resp.json()
    five_k = next((b for b in bests if b["distance_bucket"] == "5k"), None)
    assert five_k is not None
    assert five_k["best_pace_sec"] == 300  # 1500 / 5 = 300 sec/km = 5:00/km
    assert five_k["best_pace_display"] == "5:00/km"


@pytest.mark.asyncio
async def test_weekly_stats_target_none_without_goal(client: AsyncClient) -> None:
    headers = await _signup(client)
    monday = get_monday(date.today())
    await _create_run(client, headers, run_date=monday, distance_km="5.00")

    resp = await client.get(f"/stats/weekly?week_start={monday}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_km"] is None
    assert body["progress_pct"] is None


@pytest.mark.asyncio
async def test_weekly_stats_includes_target_and_progress(client: AsyncClient) -> None:
    headers = await _signup(client)
    await client.post(
        "/goals", json={"goal_type": "weekly_volume", "weekly_km_target": 30}, headers=headers
    )
    monday = get_monday(date.today())
    await _create_run(client, headers, run_date=monday, distance_km="15.00")

    resp = await client.get(f"/stats/weekly?week_start={monday}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_km"] == 30.0
    assert body["progress_pct"] == 50


@pytest.mark.asyncio
async def test_weekly_stats_avg_rpe(client: AsyncClient) -> None:
    headers = await _signup(client)
    monday = get_monday(date.today())
    resp = await client.post(
        "/runs",
        json={
            "run_date": str(monday),
            "distance_km": "5.00",
            "duration_sec": 1800,
            "run_type": "easy",
            "rpe": 4,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    resp = await client.post(
        "/runs",
        json={
            "run_date": str(monday + timedelta(days=1)),
            "distance_km": "5.00",
            "duration_sec": 1800,
            "run_type": "easy",
            "rpe": 6,
        },
        headers=headers,
    )
    assert resp.status_code == 201

    resp = await client.get(f"/stats/weekly?week_start={monday}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["avg_rpe"] == 5.0
