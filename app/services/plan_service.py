from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound, ValidationError
from app.core.pace import get_monday
from app.models.run import Run
from app.models.weekly_plan import WeeklyPlan
from app.repositories.goal_repo import GoalRepository
from app.repositories.plan_repo import PlanRepository
from app.repositories.run_repo import RunRepository
from app.schemas.plan import WeeklyPlanResponse

_goal_repo = GoalRepository()
_plan_repo = PlanRepository()
_run_repo = RunRepository()

_DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_TEMPLATE: tuple[tuple[str, str, float], ...] = (
    ("tue", "easy", 0.20),
    ("thu", "tempo", 0.20),
    ("sat", "long_run", 0.40),
    ("sun", "easy", 0.20),
)


def build_planned_sessions(weekly_km_target: float | None) -> list[dict[str, Any]]:
    if weekly_km_target is None or weekly_km_target <= 0:
        return []

    sessions: list[dict[str, Any]] = []
    allocated = 0.0
    for i, (day, run_type, ratio) in enumerate(_TEMPLATE):
        if i == len(_TEMPLATE) - 1:
            distance_km = round(weekly_km_target - allocated, 2)
        else:
            distance_km = round(weekly_km_target * ratio, 2)
            allocated += distance_km
        sessions.append(
            {
                "day": day,
                "type": run_type,
                "distance_km": distance_km,
                "pace_range": None,
                "status": "pending",
                "actual_distance_km": None,
                "run_id": None,
                "unplanned": False,
            }
        )
    return sessions


async def _to_response(session: AsyncSession, plan: WeeklyPlan, user_id: str) -> WeeklyPlanResponse:
    week_end = plan.week_start + timedelta(days=6)
    runs = await _run_repo.get_range(session, user_id, plan.week_start, week_end)
    completed_km = round(float(sum(r.distance_km for r in runs)), 2)
    total_planned_km = float(plan.total_planned_km) if plan.total_planned_km is not None else None

    remaining_km: float | None = None
    progress_pct: int | None = None
    if total_planned_km:
        remaining_km = round(max(0.0, total_planned_km - completed_km), 2)
        progress_pct = int(round(completed_km / total_planned_km * 100))

    return WeeklyPlanResponse(
        id=plan.id,
        user_id=plan.user_id,
        goal_id=plan.goal_id,
        week_start=plan.week_start,
        planned_sessions=plan.planned_sessions,
        total_planned_km=total_planned_km,
        completed_km=completed_km,
        remaining_km=remaining_km,
        progress_pct=progress_pct,
        adjustments_log=plan.adjustments_log,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


class PlanService:
    async def get_or_create(
        self, session: AsyncSession, user_id: str, week_start: date
    ) -> WeeklyPlan:
        plan = await _plan_repo.get_by_week(session, user_id, week_start)
        if plan is not None:
            return plan

        goal = await _goal_repo.get_active(session, user_id)
        weekly_km_target = float(goal.weekly_km_target) if goal and goal.weekly_km_target else None
        planned_sessions = build_planned_sessions(weekly_km_target)

        return await _plan_repo.create(
            session,
            user_id=user_id,
            goal_id=goal.id if goal else None,
            week_start=week_start,
            planned_sessions=planned_sessions,
            total_planned_km=(
                Decimal(str(weekly_km_target)) if weekly_km_target is not None else None
            ),
        )

    async def get_current(self, session: AsyncSession, user_id: str) -> WeeklyPlanResponse:
        plan = await self.get_or_create(session, user_id, get_monday(date.today()))
        return await _to_response(session, plan, user_id)

    async def get_by_week(
        self, session: AsyncSession, user_id: str, week_start: date
    ) -> WeeklyPlanResponse:
        if week_start != get_monday(week_start):
            raise ValidationError("week_start는 월요일이어야 합니다.")
        plan = await _plan_repo.get_by_week(session, user_id, week_start)
        if plan is None:
            raise NotFound("해당 주의 플랜을 찾을 수 없습니다.")
        return await _to_response(session, plan, user_id)

    async def get_history(
        self, session: AsyncSession, user_id: str, weeks: int = 8
    ) -> list[WeeklyPlanResponse]:
        plans = await _plan_repo.list_recent(session, user_id, weeks)
        return [await _to_response(session, plan, user_id) for plan in plans]

    async def mark_session_completed(self, session: AsyncSession, user_id: str, run: Run) -> None:
        week_start = get_monday(run.run_date)
        plan = await self.get_or_create(session, user_id, week_start)

        day = _DAY_NAMES[run.run_date.weekday()]
        sessions = [dict(s) for s in plan.planned_sessions]

        candidate_idx = next(
            (
                i
                for i, s in enumerate(sessions)
                if s["day"] == day and s["status"] == "pending" and s["type"] == run.run_type
            ),
            None,
        )
        if candidate_idx is None:
            candidate_idx = next(
                (i for i, s in enumerate(sessions) if s["day"] == day and s["status"] == "pending"),
                None,
            )

        if candidate_idx is not None:
            sessions[candidate_idx] = {
                **sessions[candidate_idx],
                "status": "completed",
                "actual_distance_km": float(run.distance_km),
                "run_id": run.id,
            }
        else:
            sessions.append(
                {
                    "day": day,
                    "type": run.run_type,
                    "distance_km": float(run.distance_km),
                    "pace_range": None,
                    "status": "completed",
                    "actual_distance_km": float(run.distance_km),
                    "run_id": run.id,
                    "unplanned": True,
                }
            )

        await _plan_repo.update(session, plan, {"planned_sessions": sessions})

    async def unmark_session(self, session: AsyncSession, user_id: str, run: Run) -> None:
        week_start = get_monday(run.run_date)
        plan = await _plan_repo.get_by_week(session, user_id, week_start)
        if plan is None:
            return

        sessions = [dict(s) for s in plan.planned_sessions]
        idx = next((i for i, s in enumerate(sessions) if s.get("run_id") == run.id), None)
        if idx is None:
            return

        if sessions[idx].get("unplanned"):
            sessions.pop(idx)
        else:
            sessions[idx] = {
                **sessions[idx],
                "status": "pending",
                "actual_distance_km": None,
                "run_id": None,
            }

        await _plan_repo.update(session, plan, {"planned_sessions": sessions})

    async def apply_recommendation(
        self,
        session: AsyncSession,
        user_id: str,
        recommendation: dict[str, Any],
        constraints: list[dict[str, str]],
    ) -> None:
        today = date.today()
        week_start = get_monday(today)
        plan = await self.get_or_create(session, user_id, week_start)

        day = _DAY_NAMES[today.weekday()]
        sessions = [dict(s) for s in plan.planned_sessions]

        candidate_idx = next(
            (i for i, s in enumerate(sessions) if s["day"] == day and s["status"] == "pending"),
            None,
        )
        recommended_session = {
            "type": recommendation["run_type"],
            "distance_km": recommendation["distance_km"],
            "pace_range": recommendation.get("pace_range"),
            "status": "recommended",
        }

        if candidate_idx is not None:
            sessions[candidate_idx] = {**sessions[candidate_idx], **recommended_session}
        else:
            sessions.append(
                {
                    "day": day,
                    "actual_distance_km": None,
                    "run_id": None,
                    "unplanned": True,
                    **recommended_session,
                }
            )

        adjustments_log = [dict(a) for a in plan.adjustments_log]
        for c in constraints:
            adjustments_log.append(
                {"date": today.isoformat(), "reason": c["code"], "change": c["message"]}
            )

        await _plan_repo.update(
            session, plan, {"planned_sessions": sessions, "adjustments_log": adjustments_log}
        )

    async def drop_untouched_current(self, session: AsyncSession, user_id: str) -> None:
        week_start = get_monday(date.today())
        plan = await _plan_repo.get_by_week(session, user_id, week_start)
        if plan is None:
            return
        has_completed = any(s.get("status") == "completed" for s in plan.planned_sessions)
        if not has_completed:
            await _plan_repo.delete(session, plan)
