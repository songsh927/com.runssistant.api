import json
import uuid
from datetime import date

import pytest
from httpx import AsyncClient

from app.dependencies import get_coach_graph
from app.graph.coach_graph import build_coach_graph
from app.llm.base import LLMProvider, LLMResponse
from app.main import app

_DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_GOOD_RECOMMENDATION = {
    "run_type": "easy",
    "distance_km": 5.0,
    "pace_range": {"min": "6:00/km", "max": "6:30/km"},
    "warmup": "1km 이지 조깅",
    "main_session": "4km 이지런",
    "cooldown": "500m 조깅",
    "reasoning": "이번 주 볼륨에 여유가 있어 이지런을 권장합니다.",
    "motivation": "오늘도 가볍게 다녀오세요!",
}


class FakeLLMProvider(LLMProvider):
    def __init__(
        self,
        responses: list[str] | None = None,
        always_fail: bool = False,
    ) -> None:
        self._responses = responses or [json.dumps(_GOOD_RECOMMENDATION, ensure_ascii=False)]
        self._call_count = 0
        self._always_fail = always_fail

    async def invoke(
        self,
        system: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        if self._always_fail:
            raise RuntimeError("LLM provider unavailable (simulated)")
        idx = min(self._call_count, len(self._responses) - 1)
        content = self._responses[idx]
        self._call_count += 1
        return LLMResponse(content=content, model="fake/test-model", usage=None)

    def get_model_name(self) -> str:
        return "fake/test-model"


def _override_graph(responses: list[str] | None = None, always_fail: bool = False) -> None:
    def _get() -> object:
        return build_coach_graph(FakeLLMProvider(responses=responses, always_fail=always_fail))

    app.dependency_overrides[get_coach_graph] = _get


def _make_user() -> dict[str, str]:
    uid = str(uuid.uuid4())[:8]
    return {
        "email": f"coachuser_{uid}@example.com",
        "password": "password123",
        "name": "Coach User",
        "location": "Seoul",
    }


async def _signup(client: AsyncClient) -> dict[str, str]:
    resp = await client.post("/auth/signup", json=_make_user())
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _set_weekly_goal(client: AsyncClient, headers: dict[str, str], km: float) -> None:
    resp = await client.post(
        "/goals", json={"goal_type": "weekly_volume", "weekly_km_target": km}, headers=headers
    )
    assert resp.status_code == 201


async def _create_run(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    run_date: date,
    distance_km: str,
    run_type: str = "easy",
) -> None:
    resp = await client.post(
        "/runs",
        json={
            "run_date": str(run_date),
            "distance_km": distance_km,
            "duration_sec": 1800,
            "run_type": run_type,
        },
        headers=headers,
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_recommend_returns_recommendation(client: AsyncClient) -> None:
    headers = await _signup(client)
    _override_graph()

    resp = await client.post(
        "/coach/recommend", json={"rpe": 6, "notes": "괜찮음"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendation"]["run_type"] == "easy"
    assert body["recommendation"]["distance_km"] == 5.0
    assert body["weekly_context"]["completed_km"] == 0.0
    assert body["weather"]["condition"] == "clear sky"


@pytest.mark.asyncio
async def test_recommend_persists_coaching_session(client: AsyncClient) -> None:
    headers = await _signup(client)
    _override_graph()

    resp = await client.post("/coach/recommend", json={"rpe": 5}, headers=headers)
    assert resp.status_code == 200

    history = await client.get("/coach/history", headers=headers)
    assert history.status_code == 200
    sessions = history.json()
    assert len(sessions) == 1
    assert sessions[0]["model_used"] == "fake/test-model"
    assert sessions[0]["recommendation"]["run_type"] == "easy"


@pytest.mark.asyncio
async def test_recommend_updates_weekly_plan(client: AsyncClient) -> None:
    headers = await _signup(client)
    await _set_weekly_goal(client, headers, 20)
    _override_graph()

    resp = await client.post("/coach/recommend", json={"rpe": 5}, headers=headers)
    assert resp.status_code == 200

    plan = (await client.get("/plans/current", headers=headers)).json()
    today_day = _DAY_NAMES[date.today().weekday()]
    today_sessions = [s for s in plan["planned_sessions"] if s["day"] == today_day]
    assert len(today_sessions) == 1
    assert today_sessions[0]["status"] == "recommended"
    assert today_sessions[0]["distance_km"] == 5.0
    assert today_sessions[0]["pace_range"] == {"min": "6:00/km", "max": "6:30/km"}


@pytest.mark.asyncio
async def test_recommend_applies_rule_constraints(client: AsyncClient) -> None:
    headers = await _signup(client)
    await _set_weekly_goal(client, headers, 10)
    await _create_run(client, headers, run_date=date.today(), distance_km="15.00")
    _override_graph()

    resp = await client.post("/coach/recommend", json={"rpe": 5}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["weekly_context"]["plan_adjustment"] is not None

    history = (await client.get("/coach/history", headers=headers)).json()
    codes = {c["code"] for c in history[0]["constraints"]}
    assert "VOLUME_EXCEEDED" in codes


@pytest.mark.asyncio
async def test_recommend_malformed_json_retries_then_503(client: AsyncClient) -> None:
    headers = await _signup(client)
    _override_graph(responses=["이건 JSON이 아닙니다", "여전히 JSON이 아닙니다"])

    resp = await client.post("/coach/recommend", json={"rpe": 5}, headers=headers)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "COACHING_UNAVAILABLE"

    history = (await client.get("/coach/history", headers=headers)).json()
    assert history == []


@pytest.mark.asyncio
async def test_recommend_llm_down_returns_503(client: AsyncClient) -> None:
    headers = await _signup(client)
    _override_graph(always_fail=True)

    resp = await client.post("/coach/recommend", json={"rpe": 5}, headers=headers)
    assert resp.status_code == 503

    history = (await client.get("/coach/history", headers=headers)).json()
    assert history == []


@pytest.mark.asyncio
async def test_feedback_updates_rating(client: AsyncClient) -> None:
    headers = await _signup(client)
    _override_graph()
    recommend_resp = await client.post("/coach/recommend", json={"rpe": 5}, headers=headers)
    session_id = recommend_resp.json()["session_id"]

    resp = await client.post(
        "/coach/feedback",
        json={"coaching_session_id": session_id, "rating": 4},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["user_feedback"] == 4


@pytest.mark.asyncio
async def test_feedback_invalid_rating_rejected(client: AsyncClient) -> None:
    headers = await _signup(client)
    _override_graph()
    recommend_resp = await client.post("/coach/recommend", json={"rpe": 5}, headers=headers)
    session_id = recommend_resp.json()["session_id"]

    resp = await client.post(
        "/coach/feedback",
        json={"coaching_session_id": session_id, "rating": 6},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_feedback_other_user_session_not_found(client: AsyncClient) -> None:
    headers1 = await _signup(client)
    headers2 = await _signup(client)
    _override_graph()
    recommend_resp = await client.post("/coach/recommend", json={"rpe": 5}, headers=headers1)
    session_id = recommend_resp.json()["session_id"]

    resp = await client.post(
        "/coach/feedback",
        json={"coaching_session_id": session_id, "rating": 3},
        headers=headers2,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_history_returns_recent_sessions(client: AsyncClient) -> None:
    headers = await _signup(client)
    _override_graph()
    await client.post("/coach/recommend", json={"rpe": 5}, headers=headers)
    await client.post("/coach/recommend", json={"rpe": 6}, headers=headers)

    resp = await client.get("/coach/history?limit=10", headers=headers)
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 2
