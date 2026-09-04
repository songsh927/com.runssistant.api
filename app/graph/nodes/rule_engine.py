from datetime import date
from typing import Any

_HARD_TYPES = {"tempo", "interval"}


def _group_by_date(runs: list[dict[str, Any]]) -> dict[date, list[dict[str, Any]]]:
    grouped: dict[date, list[dict[str, Any]]] = {}
    for r in runs:
        grouped.setdefault(r["run_date"], []).append(r)
    return grouped


def _last_two_consecutive_days(
    runs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    grouped = _group_by_date(runs)
    dates_sorted = sorted(grouped.keys(), reverse=True)
    if len(dates_sorted) < 2:
        return None
    d0, d1 = dates_sorted[0], dates_sorted[1]
    if (d0 - d1).days != 1:
        return None
    return grouped[d0], grouped[d1]


def _check_volume_exceeded(weekly: dict[str, Any]) -> dict[str, str] | None:
    target = weekly.get("target_km")
    if not target:
        return None
    if weekly["completed_km"] >= target * 1.2:
        return {
            "code": "VOLUME_EXCEEDED",
            "message": (
                f"이번 주 {weekly['completed_km']}km는 목표 {target}km의 120% 이상입니다. "
                "이지런 또는 휴식만 권장하세요."
            ),
        }
    return None


def _check_hard_days_limit(recent_runs: list[dict[str, Any]]) -> dict[str, str] | None:
    pair = _last_two_consecutive_days(recent_runs)
    if pair is None:
        return None
    day0, day1 = pair
    day0_hard = any(r["run_type"] in _HARD_TYPES for r in day0)
    day1_hard = any(r["run_type"] in _HARD_TYPES for r in day1)
    if day0_hard and day1_hard:
        return {
            "code": "HARD_DAYS_LIMIT",
            "message": "최근 2일 연속 고강도(템포/인터벌) 세션이 있었습니다. 이지런을 강제하세요.",
        }
    return None


def _check_rest_day_minimum(
    weekly: dict[str, Any], recent_runs: list[dict[str, Any]]
) -> dict[str, str] | None:
    if weekly["session_count"] < 4:
        return None
    week_start: date = weekly["week_start"]
    today: date = weekly["today"]
    days_elapsed = (today - week_start).days + 1
    run_dates_this_week = {
        r["run_date"] for r in recent_runs if week_start <= r["run_date"] <= today
    }
    rest_days = days_elapsed - len(run_dates_this_week)
    if rest_days <= 0:
        return {
            "code": "REST_DAY_MINIMUM",
            "message": "이번 주 휴식일이 없었습니다. 휴식을 강력히 권장하세요.",
        }
    return None


def _check_taper(goal: dict[str, Any] | None) -> dict[str, str] | None:
    if not goal or goal.get("days_to_race") is None:
        return None
    days_to_race: int = goal["days_to_race"]
    if 0 <= days_to_race <= 3:
        return {
            "code": "TAPER_3D",
            "message": f"대회 D-{days_to_race}. 이지런 3km 이하 또는 휴식만 권장하세요.",
        }
    if 4 <= days_to_race <= 7:
        return {
            "code": "TAPER_7D",
            "message": f"대회 D-{days_to_race}. 주간 볼륨을 60% 이하로 낮추세요.",
        }
    return None


def _check_heat_alert(weather: dict[str, Any] | None) -> dict[str, str] | None:
    if not weather:
        return None
    if weather["temp_c"] >= 33:
        return {
            "code": "HEAT_ALERT",
            "message": f"기온 {weather['temp_c']}°C. 페이스를 10-15% 하향 조정하세요.",
        }
    return None


def _check_cold_alert(weather: dict[str, Any] | None) -> dict[str, str] | None:
    if not weather:
        return None
    if weather["temp_c"] <= -5:
        return {
            "code": "COLD_ALERT",
            "message": f"기온 {weather['temp_c']}°C. 실내 대안을 제시하거나 방한을 강조하세요.",
        }
    return None


def _check_injury_risk(recent_runs: list[dict[str, Any]]) -> dict[str, str] | None:
    pair = _last_two_consecutive_days(recent_runs)
    if pair is None:
        return None
    day0, day1 = pair
    day0_high = any((r.get("rpe") or 0) >= 9 for r in day0)
    day1_high = any((r.get("rpe") or 0) >= 9 for r in day1)
    if day0_high and day1_high:
        return {
            "code": "INJURY_RISK",
            "message": "최근 2일 연속 RPE 9 이상입니다. 휴식을 강제하고 통증 여부를 확인하세요.",
        }
    return None


def _check_beginner_guard(total_run_count: int, has_profile: bool) -> dict[str, str] | None:
    # 프로필이 있으면 experience_level 기반 PROFILE_BEGINNER_GUARD가 처리한다 (6-3 통합)
    if has_profile:
        return None
    if total_run_count < 10:
        return {
            "code": "BEGINNER_GUARD",
            "message": "총 러닝 기록이 10회 미만입니다. 최대 5km, 이지런 위주로 권장하세요.",
        }
    return None


def evaluate_rules(context: dict[str, Any]) -> list[dict[str, str]]:
    has_profile = bool(context.get("runner_profile"))
    checks = [
        _check_volume_exceeded(context["weekly"]),
        _check_hard_days_limit(context["recent_runs"]),
        _check_rest_day_minimum(context["weekly"], context["recent_runs"]),
        _check_taper(context.get("goal")),
        _check_heat_alert(context.get("weather")),
        _check_cold_alert(context.get("weather")),
        _check_injury_risk(context["recent_runs"]),
        _check_beginner_guard(context["total_run_count"], has_profile),
    ]
    return [c for c in checks if c is not None]
