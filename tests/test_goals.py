import uuid

import pytest
from httpx import AsyncClient


def _make_user() -> dict[str, str]:
    uid = str(uuid.uuid4())[:8]
    return {
        "email": f"goaluser_{uid}@example.com",
        "password": "password123",
        "name": "Goal User",
        "location": "Seoul",
    }


async def _signup(client: AsyncClient) -> dict[str, str]:
    resp = await client.post("/auth/signup", json=_make_user())
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_weekly_volume_goal_success(client: AsyncClient) -> None:
    headers = await _signup(client)
    resp = await client.post(
        "/goals",
        json={"goal_type": "weekly_volume", "weekly_km_target": 30},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["goal_type"] == "weekly_volume"
    assert body["weekly_km_target"] == 30.0
    assert body["status"] == "active"


@pytest.mark.asyncio
async def test_create_race_goal_success(client: AsyncClient) -> None:
    headers = await _signup(client)
    resp = await client.post(
        "/goals",
        json={
            "goal_type": "race",
            "race_name": "서울마라톤 2027",
            "race_date": "2027-03-16",
            "race_distance_km": 42.195,
            "race_target_time": 14400,
            "weekly_km_target": 40,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["goal_type"] == "race"
    assert body["race_name"] == "서울마라톤 2027"


@pytest.mark.asyncio
async def test_create_goal_abandons_previous_active(client: AsyncClient) -> None:
    headers = await _signup(client)
    first = (
        await client.post(
            "/goals", json={"goal_type": "weekly_volume", "weekly_km_target": 20}, headers=headers
        )
    ).json()
    second = (
        await client.post(
            "/goals", json={"goal_type": "weekly_volume", "weekly_km_target": 30}, headers=headers
        )
    ).json()
    assert second["status"] == "active"

    list_resp = await client.get("/goals", headers=headers)
    goals = {g["id"]: g for g in list_resp.json()}
    assert goals[first["id"]]["status"] == "abandoned"
    assert goals[second["id"]]["status"] == "active"


@pytest.mark.asyncio
async def test_create_weekly_volume_goal_without_target_rejected(client: AsyncClient) -> None:
    headers = await _signup(client)
    resp = await client.post("/goals", json={"goal_type": "weekly_volume"}, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_goals_filter_by_status(client: AsyncClient) -> None:
    headers = await _signup(client)
    await client.post(
        "/goals", json={"goal_type": "weekly_volume", "weekly_km_target": 20}, headers=headers
    )
    await client.post(
        "/goals", json={"goal_type": "weekly_volume", "weekly_km_target": 30}, headers=headers
    )
    resp = await client.get("/goals?status=active", headers=headers)
    assert resp.status_code == 200
    goals = resp.json()
    assert len(goals) == 1
    assert goals[0]["status"] == "active"


@pytest.mark.asyncio
async def test_get_active_goal(client: AsyncClient) -> None:
    headers = await _signup(client)
    await client.post(
        "/goals", json={"goal_type": "weekly_volume", "weekly_km_target": 30}, headers=headers
    )
    resp = await client.get("/goals/active", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["weekly_km_target"] == 30.0


@pytest.mark.asyncio
async def test_get_active_goal_none(client: AsyncClient) -> None:
    headers = await _signup(client)
    resp = await client.get("/goals/active", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_goal(client: AsyncClient) -> None:
    headers = await _signup(client)
    created = (
        await client.post(
            "/goals", json={"goal_type": "weekly_volume", "weekly_km_target": 30}, headers=headers
        )
    ).json()
    resp = await client.put(
        f"/goals/{created['id']}", json={"weekly_km_target": 35}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["weekly_km_target"] == 35.0


@pytest.mark.asyncio
async def test_update_goal_status(client: AsyncClient) -> None:
    headers = await _signup(client)
    created = (
        await client.post(
            "/goals", json={"goal_type": "weekly_volume", "weekly_km_target": 30}, headers=headers
        )
    ).json()
    resp = await client.patch(
        f"/goals/{created['id']}/status", json={"status": "completed"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_other_user_cannot_access_goal(client: AsyncClient) -> None:
    headers1 = await _signup(client)
    headers2 = await _signup(client)
    created = (
        await client.post(
            "/goals", json={"goal_type": "weekly_volume", "weekly_km_target": 30}, headers=headers1
        )
    ).json()

    resp = await client.put(
        f"/goals/{created['id']}", json={"weekly_km_target": 99}, headers=headers2
    )
    assert resp.status_code == 404

    resp = await client.patch(
        f"/goals/{created['id']}/status", json={"status": "abandoned"}, headers=headers2
    )
    assert resp.status_code == 404
