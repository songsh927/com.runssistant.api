import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pace import get_monday
from app.models.weekly_plan import WeeklyPlan
from app.services.plan_service import build_planned_sessions

_DAY_OFFSET = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _make_user() -> dict[str, str]:
    uid = str(uuid.uuid4())[:8]
    return {
        "email": f"planuser_{uid}@example.com",
        "password": "password123",
        "name": "Plan User",
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
    assert resp.status_code == 201
    return resp.json()  # type: ignore[return-value]


@pytest.mark.parametrize("target", [30.0, 20.0, 40.5, 10.0])
def test_build_planned_sessions_sums_to_target(target: float) -> None:
    sessions = build_planned_sessions(target)
    total = sum(s["distance_km"] for s in sessions)
    assert total == pytest.approx(target)


def test_build_planned_sessions_none_target_returns_empty() -> None:
    assert build_planned_sessions(None) == []


def test_build_planned_sessions_zero_or_negative_returns_empty() -> None:
    assert build_planned_sessions(0) == []
    assert build_planned_sessions(-5) == []


def test_build_planned_sessions_shape() -> None:
    sessions = build_planned_sessions(30.0)
    assert len(sessions) == 4
    days = {s["day"] for s in sessions}
    assert days == {"tue", "thu", "sat", "sun"}
    for s in sessions:
        assert s["status"] == "pending"
        assert s["pace_range"] is None
        assert s["actual_distance_km"] is None
        assert s["run_id"] is None
        assert s["unplanned"] is False
        assert s["type"] in {"easy", "tempo", "long_run"}


@pytest.mark.asyncio
async def test_current_plan_auto_created_from_goal(client: AsyncClient) -> None:
    headers = await _signup(client)
    await _set_weekly_goal(client, headers, 30)

    resp = await client.get("/plans/current", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["planned_sessions"]) == 4
    assert body["total_planned_km"] == 30.0
    assert body["completed_km"] == 0.0
    assert body["remaining_km"] == 30.0
    assert body["progress_pct"] == 0


@pytest.mark.asyncio
async def test_current_plan_without_goal_is_empty(client: AsyncClient) -> None:
    headers = await _signup(client)
    resp = await client.get("/plans/current", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["planned_sessions"] == []
    assert body["total_planned_km"] is None
    assert body["remaining_km"] is None
    assert body["progress_pct"] is None


@pytest.mark.asyncio
async def test_current_plan_is_idempotent(client: AsyncClient) -> None:
    headers = await _signup(client)
    await _set_weekly_goal(client, headers, 30)
    first = (await client.get("/plans/current", headers=headers)).json()
    second = (await client.get("/plans/current", headers=headers)).json()
    assert first["id"] == second["id"]


@pytest.mark.asyncio
async def test_run_marks_planned_session_completed(client: AsyncClient) -> None:
    headers = await _signup(client)
    await _set_weekly_goal(client, headers, 30)
    monday = get_monday(date.today())
    tuesday = monday + timedelta(days=_DAY_OFFSET["tue"])

    await _create_run(client, headers, run_date=tuesday, distance_km="6.00")

    plan = (await client.get("/plans/current", headers=headers)).json()
    tue_session = next(s for s in plan["planned_sessions"] if s["day"] == "tue")
    assert tue_session["status"] == "completed"
    assert tue_session["actual_distance_km"] == 6.0
    assert tue_session["unplanned"] is False


@pytest.mark.asyncio
async def test_unplanned_run_appended_to_plan(client: AsyncClient) -> None:
    headers = await _signup(client)
    await _set_weekly_goal(client, headers, 30)
    monday = get_monday(date.today())
    wednesday = monday + timedelta(days=_DAY_OFFSET["wed"])

    await _create_run(client, headers, run_date=wednesday, distance_km="4.00")

    plan = (await client.get("/plans/current", headers=headers)).json()
    wed_sessions = [s for s in plan["planned_sessions"] if s["day"] == "wed"]
    assert len(wed_sessions) == 1
    assert wed_sessions[0]["status"] == "completed"
    assert wed_sessions[0]["unplanned"] is True
    assert wed_sessions[0]["actual_distance_km"] == 4.0


@pytest.mark.asyncio
async def test_goal_30km_then_5km_run_leaves_25km_remaining(client: AsyncClient) -> None:
    headers = await _signup(client)
    await _set_weekly_goal(client, headers, 30)
    monday = get_monday(date.today())

    await _create_run(client, headers, run_date=monday, distance_km="5.00")

    plan = (await client.get("/plans/current", headers=headers)).json()
    assert plan["completed_km"] == 5.0
    assert plan["remaining_km"] == 25.0

    stats = (await client.get(f"/stats/weekly?week_start={monday}", headers=headers)).json()
    assert stats["target_km"] == 30.0
    assert stats["progress_pct"] == 17


@pytest.mark.asyncio
async def test_delete_run_reverts_session_status(client: AsyncClient) -> None:
    headers = await _signup(client)
    await _set_weekly_goal(client, headers, 30)
    monday = get_monday(date.today())
    tuesday = monday + timedelta(days=_DAY_OFFSET["tue"])

    run = await _create_run(client, headers, run_date=tuesday, distance_km="6.00")
    await client.delete(f"/runs/{run['id']}", headers=headers)

    plan = (await client.get("/plans/current", headers=headers)).json()
    tue_session = next(s for s in plan["planned_sessions"] if s["day"] == "tue")
    assert tue_session["status"] == "pending"
    assert plan["completed_km"] == 0.0


@pytest.mark.asyncio
async def test_new_goal_regenerates_untouched_plan(client: AsyncClient) -> None:
    headers = await _signup(client)
    await _set_weekly_goal(client, headers, 20)
    first_plan = (await client.get("/plans/current", headers=headers)).json()
    assert first_plan["total_planned_km"] == 20.0

    await _set_weekly_goal(client, headers, 30)
    second_plan = (await client.get("/plans/current", headers=headers)).json()
    assert second_plan["total_planned_km"] == 30.0


@pytest.mark.asyncio
async def test_get_plan_by_week_not_found(client: AsyncClient) -> None:
    headers = await _signup(client)
    monday = get_monday(date.today()) - timedelta(weeks=10)
    resp = await client.get(f"/plans/{monday}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_plan_by_non_monday_rejected(client: AsyncClient) -> None:
    headers = await _signup(client)
    not_monday = get_monday(date.today()) + timedelta(days=1)
    resp = await client.get(f"/plans/{not_monday}", headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_plans_history(client: AsyncClient) -> None:
    headers = await _signup(client)
    await _set_weekly_goal(client, headers, 30)
    await client.get("/plans/current", headers=headers)

    resp = await client.get("/plans/history?weeks=4", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["total_planned_km"] == 30.0


@pytest.mark.asyncio
async def test_other_user_cannot_access_plan(client: AsyncClient) -> None:
    headers1 = await _signup(client)
    headers2 = await _signup(client)
    await _set_weekly_goal(client, headers1, 30)
    plan1 = (await client.get("/plans/current", headers=headers1)).json()
    monday = plan1["week_start"]

    resp = await client.get(f"/plans/{monday}", headers=headers2)
    assert resp.status_code == 404


def test_planned_session_accepts_design_pace_range_shape() -> None:
    """설계 §5.5 / §7.3이 LLM 출력으로 강제하는 {min, max} 형태를 받아들여야 한다."""
    from app.schemas.plan import PlannedSession

    s = PlannedSession(
        day="thu",
        type="tempo",
        distance_km=6.0,
        status="recommended",
        pace_range={"min": "5:20/km", "max": "5:40/km"},
    )
    assert s.pace_range is not None
    assert s.pace_range.min == "5:20/km"
    assert s.pace_range.max == "5:40/km"


def test_planned_session_rejects_malformed_pace_range() -> None:
    """min/max가 없는 pace_range는 거부해야 Sprint 3의 잘못된 LLM 출력을 경계에서 잡는다."""
    from pydantic import ValidationError

    from app.schemas.plan import PlannedSession

    with pytest.raises(ValidationError):
        PlannedSession(
            day="thu",
            type="tempo",
            distance_km=6.0,
            status="recommended",
            pace_range={"foo": "bar"},
        )


@pytest.mark.asyncio
async def test_plan_round_trips_pace_range_through_jsonb(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Sprint 3 Plan Updater가 기록할 dict 형태가 JSONB 왕복 후에도 유지되는지 확인."""
    headers = await _signup(client)
    await _set_weekly_goal(client, headers, 30)
    plan = (await client.get("/plans/current", headers=headers)).json()

    sessions = [dict(s) for s in plan["planned_sessions"]]
    sessions[0] = {**sessions[0], "pace_range": {"min": "6:00/km", "max": "6:30/km"}}

    await db_session.execute(
        update(WeeklyPlan).where(WeeklyPlan.id == plan["id"]).values(planned_sessions=sessions)
    )
    await db_session.commit()

    refetched = (await client.get("/plans/current", headers=headers)).json()
    assert refetched["planned_sessions"][0]["pace_range"] == {
        "min": "6:00/km",
        "max": "6:30/km",
    }
