import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient


def _make_user() -> dict[str, str]:
    uid = str(uuid.uuid4())[:8]
    return {
        "email": f"runner_{uid}@example.com",
        "password": "password123",
        "name": "Test Runner",
        "location": "Seoul",
    }


def _make_run(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "run_date": str(date.today()),
        "distance_km": "5.00",
        "duration_sec": 1800,
        "run_type": "easy",
        "rpe": 5,
        "notes": "Good run",
    }
    data.update(overrides)
    return data


async def _signup(client: AsyncClient) -> dict[str, str]:
    user = _make_user()
    resp = await client.post("/auth/signup", json=user)
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_run_success(client: AsyncClient) -> None:
    headers = await _signup(client)
    resp = await client.post("/runs", json=_make_run(), headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["run_type"] == "easy"
    assert body["avg_pace_sec"] == 360
    assert body["avg_pace_display"] == "6:00/km"
    assert body["weather_snapshot"] is not None
    assert body["weather_snapshot"]["condition"] == "clear sky"


@pytest.mark.asyncio
async def test_create_run_invalid_run_type(client: AsyncClient) -> None:
    headers = await _signup(client)
    resp = await client.post("/runs", json=_make_run(run_type="sprint"), headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_runs(client: AsyncClient) -> None:
    headers = await _signup(client)
    for _ in range(3):
        await client.post("/runs", json=_make_run(), headers=headers)
    resp = await client.get("/runs", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_list_runs_date_filter(client: AsyncClient) -> None:
    headers = await _signup(client)
    today = date.today()
    yesterday = today - timedelta(days=1)
    await client.post("/runs", json=_make_run(run_date=str(today)), headers=headers)
    await client.post("/runs", json=_make_run(run_date=str(yesterday)), headers=headers)

    resp = await client.get(f"/runs?from={today}&to={today}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["run_date"] == str(today)


@pytest.mark.asyncio
async def test_get_run(client: AsyncClient) -> None:
    headers = await _signup(client)
    created = (await client.post("/runs", json=_make_run(), headers=headers)).json()
    resp = await client.get(f"/runs/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_run_not_found(client: AsyncClient) -> None:
    headers = await _signup(client)
    resp = await client.get("/runs/00000000-0000-0000-0000-000000000000", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_run(client: AsyncClient) -> None:
    headers = await _signup(client)
    created = (await client.post("/runs", json=_make_run(), headers=headers)).json()
    resp = await client.put(
        f"/runs/{created['id']}",
        json={"notes": "Updated notes", "rpe": 7},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["notes"] == "Updated notes"
    assert body["rpe"] == 7


@pytest.mark.asyncio
async def test_soft_delete_run(client: AsyncClient) -> None:
    headers = await _signup(client)
    created = (await client.post("/runs", json=_make_run(), headers=headers)).json()
    run_id = created["id"]

    del_resp = await client.delete(f"/runs/{run_id}", headers=headers)
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/runs/{run_id}", headers=headers)
    assert get_resp.status_code == 404

    list_resp = await client.get("/runs", headers=headers)
    assert all(r["id"] != run_id for r in list_resp.json())


@pytest.mark.asyncio
async def test_other_user_cannot_access_run(client: AsyncClient) -> None:
    headers1 = await _signup(client)
    headers2 = await _signup(client)

    created = (await client.post("/runs", json=_make_run(), headers=headers1)).json()
    run_id = created["id"]

    resp = await client.get(f"/runs/{run_id}", headers=headers2)
    assert resp.status_code == 404

    resp = await client.put(f"/runs/{run_id}", json={"notes": "hack"}, headers=headers2)
    assert resp.status_code == 404

    resp = await client.delete(f"/runs/{run_id}", headers=headers2)
    assert resp.status_code == 404
