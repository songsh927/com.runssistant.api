import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import _DEFAULT_PROFILE

_ONBOARDING_PAYLOAD = _DEFAULT_PROFILE


async def _signup_and_get_headers(client: AsyncClient) -> dict[str, str]:
    uid = str(uuid.uuid4())[:8]
    resp = await client.post(
        "/auth/signup",
        json={
            "email": f"profile_{uid}@example.com",
            "password": "password123",
            "name": "Profile Tester",
            "location": "Seoul",
        },
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_profile_success(client: AsyncClient) -> None:
    headers = await _signup_and_get_headers(client)
    resp = await client.post("/users/profile", json=_ONBOARDING_PAYLOAD, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["onboarding_completed"] is True
    assert body["experience"]["level"] == "intermediate"
    assert body["experience"]["runs_per_week"] == 3


@pytest.mark.asyncio
async def test_create_profile_conflict_on_second_submit(client: AsyncClient) -> None:
    headers = await _signup_and_get_headers(client)
    await client.post("/users/profile", json=_ONBOARDING_PAYLOAD, headers=headers)
    resp = await client.post("/users/profile", json=_ONBOARDING_PAYLOAD, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PROFILE_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_get_profile_success(client: AsyncClient) -> None:
    headers = await _signup_and_get_headers(client)
    await client.post("/users/profile", json=_ONBOARDING_PAYLOAD, headers=headers)

    resp = await client.get("/users/profile", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["onboarding_completed"] is True
    assert body["training"]["time_per_session"] == "30_60min"


@pytest.mark.asyncio
async def test_get_profile_not_found_before_onboarding(client: AsyncClient) -> None:
    headers = await _signup_and_get_headers(client)
    resp = await client.get("/users/profile", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROFILE_NOT_FOUND"


@pytest.mark.asyncio
async def test_patch_profile_partial_update(client: AsyncClient) -> None:
    headers = await _signup_and_get_headers(client)
    await client.post("/users/profile", json=_ONBOARDING_PAYLOAD, headers=headers)

    patch = {
        "injuries": {
            "status": {
                "knee": "mild",
                "ankle": "none",
                "achilles": "none",
                "shin": "none",
                "hip_back": "none",
                "plantar_fascia": "none",
            },
            "history": "2024년 무릎 부상 이력",
        }
    }
    resp = await client.patch("/users/profile", json=patch, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["injuries"]["status"]["knee"] == "mild"
    assert body["injuries"]["history"] == "2024년 무릎 부상 이력"
    assert body["experience"]["level"] == "intermediate"


@pytest.mark.asyncio
async def test_patch_profile_not_found_before_onboarding(client: AsyncClient) -> None:
    headers = await _signup_and_get_headers(client)
    resp = await client.patch("/users/profile", json={"cross_training": ["yoga"]}, headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROFILE_NOT_FOUND"


@pytest.mark.asyncio
async def test_coach_recommend_blocked_without_onboarding(client: AsyncClient) -> None:
    headers = await _signup_and_get_headers(client)
    resp = await client.post("/coach/recommend", json={"rpe": 5}, headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ONBOARDING_REQUIRED"


@pytest.mark.asyncio
async def test_auth_me_returns_onboarding_completed(client: AsyncClient) -> None:
    headers = await _signup_and_get_headers(client)

    me_before = await client.get("/auth/me", headers=headers)
    assert me_before.status_code == 200
    assert me_before.json()["onboarding_completed"] is False

    await client.post("/users/profile", json=_ONBOARDING_PAYLOAD, headers=headers)

    me_after = await client.get("/auth/me", headers=headers)
    assert me_after.status_code == 200
    assert me_after.json()["onboarding_completed"] is True
