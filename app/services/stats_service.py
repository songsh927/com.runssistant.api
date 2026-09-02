from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pace import format_pace, get_monday
from app.models.run import Run
from app.repositories.goal_repo import GoalRepository
from app.repositories.run_repo import RunRepository
from app.schemas.stats import PersonalBest, TrendPoint, WeeklyStats

_repo = RunRepository()
_goal_repo = GoalRepository()

_DISTANCE_BUCKETS: dict[str, tuple[float, float]] = {
    "5k": (4.0, 6.0),
    "10k": (8.0, 12.0),
    "half": (18.0, 22.0),
    "full": (40.0, 44.0),
}


def _compute_weekly(
    week_start: date, runs: list[Run], target_km: float | None = None
) -> WeeklyStats:
    total_km = float(sum(r.distance_km for r in runs))
    total_sec = sum(r.duration_sec for r in runs)
    avg_pace_sec = int(total_sec / total_km) if total_km > 0 else None
    run_type_breakdown: dict[str, int] = {}
    for r in runs:
        run_type_breakdown[r.run_type] = run_type_breakdown.get(r.run_type, 0) + 1

    rpes = [r.rpe for r in runs if r.rpe is not None]
    avg_rpe = round(sum(rpes) / len(rpes), 1) if rpes else None
    progress_pct = int(round(total_km / target_km * 100)) if target_km else None

    return WeeklyStats(
        week_start=week_start,
        total_km=round(total_km, 2),
        target_km=target_km,
        progress_pct=progress_pct,
        session_count=len(runs),
        avg_pace_sec=avg_pace_sec,
        avg_pace_display=format_pace(avg_pace_sec) if avg_pace_sec is not None else None,
        avg_rpe=avg_rpe,
        run_type_breakdown=run_type_breakdown,
    )


class StatsService:
    async def get_weekly_stats(
        self, session: AsyncSession, user_id: str, week_start: date
    ) -> WeeklyStats:
        week_end = week_start + timedelta(days=6)
        runs = await _repo.get_range(session, user_id, week_start, week_end)
        goal = await _goal_repo.get_active(session, user_id)
        target_km = float(goal.weekly_km_target) if goal and goal.weekly_km_target else None
        return _compute_weekly(week_start, runs, target_km)

    async def get_trend(
        self, session: AsyncSession, user_id: str, weeks: int = 12
    ) -> list[TrendPoint]:
        current_monday = get_monday(date.today())
        points: list[TrendPoint] = []
        for i in range(weeks - 1, -1, -1):
            week_start = current_monday - timedelta(weeks=i)
            week_end = week_start + timedelta(days=6)
            runs = await _repo.get_range(session, user_id, week_start, week_end)
            stats = _compute_weekly(week_start, runs)
            points.append(
                TrendPoint(
                    week_start=stats.week_start,
                    total_km=stats.total_km,
                    session_count=stats.session_count,
                    avg_pace_sec=stats.avg_pace_sec,
                    avg_pace_display=stats.avg_pace_display,
                )
            )
        return points

    async def get_personal_bests(self, session: AsyncSession, user_id: str) -> list[PersonalBest]:
        runs = await _repo.get_range(session, user_id, date(2000, 1, 1), date.today())
        bests: list[PersonalBest] = []
        for bucket_name, (min_km, max_km) in _DISTANCE_BUCKETS.items():
            candidates = [
                r
                for r in runs
                if min_km <= float(r.distance_km) <= max_km and r.avg_pace_sec is not None
            ]
            if not candidates:
                continue
            best = min(candidates, key=lambda r: r.avg_pace_sec or 0)
            if best.avg_pace_sec is None:
                continue
            bests.append(
                PersonalBest(
                    distance_bucket=bucket_name,
                    best_pace_sec=best.avg_pace_sec,
                    best_pace_display=format_pace(best.avg_pace_sec),
                    achieved_on=best.run_date,
                )
            )
        return bests
