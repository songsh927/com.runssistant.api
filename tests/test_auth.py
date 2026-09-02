import uuid

import pytest
from httpx import AsyncClient


def make_user() -> dict[str, str]:
    uid = str(uuid.uuid4())[:8]
    return {
        "email": f"runner_{uid}@example.com",
        "password": "password123",
        "name": "테스트 러너",
        "location": "Seoul",
    }


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient) -> None:
    resp = await client.post("/auth/signup", json=make_user())
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient) -> None:
    data = make_user()
    await client.post("/auth/signup", json=data)
    resp = await client.post("/auth/signup", json=data)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    data = make_user()
    await client.post("/auth/signup", json=data)
    resp = await client.post(
        "/auth/login",
        json={"email": data["email"], "password": data["password"]},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    data = make_user()
    await client.post("/auth/signup", json=data)
    resp = await client.post(
        "/auth/login",
        json={"email": data["email"], "password": "wrongpassword"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_me_success(client: AsyncClient) -> None:
    data = make_user()
    signup_resp = await client.post("/auth/signup", json=data)
    token = signup_resp.json()["access_token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == data["email"]
    assert body["name"] == data["name"]


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient) -> None:
    resp = await client.get("/auth/me")
    assert resp.status_code in (401, 403)
