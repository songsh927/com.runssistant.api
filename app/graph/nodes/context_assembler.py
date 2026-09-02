from datetime import date, timedelta
from typing import Any

from app.core.pace import get_monday
from app.graph.state import CoachState
from app.repositories.goal_repo import GoalRepository
from app.repositories.run_repo import RunRepository
from app.services.plan_service import PlanService
from app.services.stats_service import StatsService

_goal_repo = GoalRepository()
_run_repo = RunRepository()
_stats_svc = StatsService()
_plan_svc = PlanService()

_RECENT_RUNS_WINDOW_DAYS = 14


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
    }
    return {"context": context}
