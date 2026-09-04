from datetime import date, timedelta
from typing import Any

from app.core.pace import get_monday
from app.graph.state import CoachState
from app.repositories.goal_repo import GoalRepository
from app.repositories.run_repo import RunRepository
from app.repositories.user_repo import UserRepository
from app.services.plan_service import PlanService
from app.services.stats_service import StatsService

_goal_repo = GoalRepository()
_run_repo = RunRepository()
_user_repo = UserRepository()
_stats_svc = StatsService()
_plan_svc = PlanService()

_RECENT_RUNS_WINDOW_DAYS = 14

_DAY_MAP = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


def _is_today_available(available_days: list[str]) -> bool:
    return _DAY_MAP[date.today().weekday()] in available_days


async def assemble_context(state: CoachState) -> dict[str, Any]:
    session = state["db_session"]
    user_id = state["user_id"]
    today = date.today()
    week_start = get_monday(today)

    weekly_stats = await _stats_svc.get_weekly_stats(session, user_id, week_start)
    plan = await _plan_svc.get_current(session, user_id)
    goal = await _goal_repo.get_active(session, user_id)

    recent_runs_orm = await _run_repo.get_range(
        session, user_id, today - timedelta(days=_RECENT_RUNS_WINDOW_DAYS), today
    )
    recent_runs = [
        {
            "run_date": r.run_date,
            "run_type": r.run_type,
            "rpe": r.rpe,
            "distance_km": float(r.distance_km),
        }
        for r in recent_runs_orm
    ]

    total_run_count = await _run_repo.count(session, user_id)

    user = await _user_repo.get(session, user_id)
    raw_profile = user.runner_profile if user else None
    runner_profile_context: dict[str, Any] | None = None
    is_available_day = True
    if raw_profile:
        training = raw_profile.get("training", {})
        available_days: list[str] = training.get("available_days", [])
        runner_profile_context = {
            "experience_level": raw_profile.get("experience", {}).get("level"),
            "runs_per_week": raw_profile.get("experience", {}).get("runs_per_week"),
            "longest_distance": raw_profile.get("experience", {}).get("longest_distance"),
            "preferred_types": training.get("preferred_types", []),
            "available_days": available_days,
            "time_per_session": training.get("time_per_session"),
            "cross_training": raw_profile.get("cross_training", []),
            "injuries": raw_profile.get("injuries", {}).get("status", {}),
            "injury_history": raw_profile.get("injuries", {}).get("history"),
        }
        is_available_day = _is_today_available(available_days) if available_days else True

    weather_snapshot = None
    if state["user_location"]:
        weather_snapshot = await state["weather_service"].get_current(state["user_location"])

    goal_context: dict[str, Any] | None = None
    if goal is not None:
        days_to_race = (goal.race_date - today).days if goal.race_date else None
        goal_context = {
            "goal_type": goal.goal_type,
            "weekly_km_target": float(goal.weekly_km_target) if goal.weekly_km_target else None,
            "race_name": goal.race_name,
            "race_date": goal.race_date,
            "race_distance_km": float(goal.race_distance_km) if goal.race_distance_km else None,
            "days_to_race": days_to_race,
        }

    context: dict[str, Any] = {
        "rpe": state["rpe"],
        "notes": state["notes"],
        "weekly": {
            "completed_km": weekly_stats.total_km,
            "target_km": weekly_stats.target_km,
            "progress_pct": weekly_stats.progress_pct,
            "session_count": weekly_stats.session_count,
            "avg_pace_sec": weekly_stats.avg_pace_sec,
            "avg_rpe": weekly_stats.avg_rpe,
            "week_start": week_start,
            "today": today,
        },
        "plan": {
            "remaining_km": plan.remaining_km,
            "total_planned_km": plan.total_planned_km,
            "planned_sessions": [s.model_dump() for s in plan.planned_sessions],
        },
        "recent_runs": recent_runs,
        "goal": goal_context,
        "weather": weather_snapshot,
        "total_run_count": total_run_count,
        "runner_profile": runner_profile_context,
        "is_available_day": is_available_day,
    }
    return {"context": context}
