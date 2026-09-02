from datetime import date, timedelta

from app.graph.nodes.rule_engine import evaluate_rules

TODAY = date(2026, 9, 3)  # 목요일
MONDAY = TODAY - timedelta(days=TODAY.weekday())


def _base_context(**overrides: object) -> dict:
    context: dict = {
        "weekly": {
            "completed_km": 10.0,
            "target_km": 30.0,
            "session_count": 2,
            "week_start": MONDAY,
            "today": TODAY,
        },
        "recent_runs": [],
        "goal": None,
        "weather": None,
        "total_run_count": 20,
    }
    context.update(overrides)
    return context


def _codes(constraints: list[dict]) -> set:
    return {c["code"] for c in constraints}


def test_no_rules_triggered_by_default() -> None:
    assert evaluate_rules(_base_context()) == []


def test_volume_exceeded_triggers_at_120_percent() -> None:
    ctx = _base_context(
        weekly={**_base_context()["weekly"], "completed_km": 36.0, "target_km": 30.0}
    )
    assert "VOLUME_EXCEEDED" in _codes(evaluate_rules(ctx))


def test_volume_exceeded_does_not_trigger_just_under_threshold() -> None:
    ctx = _base_context(
        weekly={**_base_context()["weekly"], "completed_km": 35.9, "target_km": 30.0}
    )
    assert "VOLUME_EXCEEDED" not in _codes(evaluate_rules(ctx))


def test_volume_exceeded_skipped_without_target() -> None:
    ctx = _base_context(
        weekly={**_base_context()["weekly"], "completed_km": 100.0, "target_km": None}
    )
    assert "VOLUME_EXCEEDED" not in _codes(evaluate_rules(ctx))


def test_hard_days_limit_triggers_on_two_consecutive_hard_days() -> None:
    ctx = _base_context(
        recent_runs=[
            {"run_date": TODAY - timedelta(days=1), "run_type": "interval", "rpe": 7},
            {"run_date": TODAY - timedelta(days=2), "run_type": "tempo", "rpe": 6},
        ]
    )
    assert "HARD_DAYS_LIMIT" in _codes(evaluate_rules(ctx))


def test_hard_days_limit_not_triggered_if_easy_between() -> None:
    ctx = _base_context(
        recent_runs=[
            {"run_date": TODAY - timedelta(days=1), "run_type": "easy", "rpe": 5},
            {"run_date": TODAY - timedelta(days=2), "run_type": "tempo", "rpe": 6},
        ]
    )
    assert "HARD_DAYS_LIMIT" not in _codes(evaluate_rules(ctx))


def test_hard_days_limit_not_triggered_if_not_consecutive() -> None:
    ctx = _base_context(
        recent_runs=[
            {"run_date": TODAY - timedelta(days=1), "run_type": "interval", "rpe": 7},
            {"run_date": TODAY - timedelta(days=3), "run_type": "tempo", "rpe": 6},
        ]
    )
    assert "HARD_DAYS_LIMIT" not in _codes(evaluate_rules(ctx))


def test_rest_day_minimum_triggers_when_no_rest_and_enough_sessions() -> None:
    ctx = _base_context(
        weekly={**_base_context()["weekly"], "session_count": 4},
        recent_runs=[
            {"run_date": MONDAY, "run_type": "easy", "rpe": 5},
            {"run_date": MONDAY + timedelta(days=1), "run_type": "easy", "rpe": 5},
            {"run_date": MONDAY + timedelta(days=2), "run_type": "easy", "rpe": 5},
            {"run_date": TODAY, "run_type": "easy", "rpe": 5},
        ],
    )
    assert "REST_DAY_MINIMUM" in _codes(evaluate_rules(ctx))


def test_rest_day_minimum_not_triggered_with_rest_day_taken() -> None:
    ctx = _base_context(
        weekly={**_base_context()["weekly"], "session_count": 4},
        recent_runs=[
            {"run_date": MONDAY, "run_type": "easy", "rpe": 5},
            {"run_date": MONDAY + timedelta(days=1), "run_type": "easy", "rpe": 5},
            {"run_date": TODAY, "run_type": "easy", "rpe": 5},
        ],
    )
    assert "REST_DAY_MINIMUM" not in _codes(evaluate_rules(ctx))


def test_rest_day_minimum_not_triggered_under_session_threshold() -> None:
    ctx = _base_context(
        weekly={**_base_context()["weekly"], "session_count": 3},
        recent_runs=[
            {"run_date": MONDAY, "run_type": "easy", "rpe": 5},
            {"run_date": MONDAY + timedelta(days=1), "run_type": "easy", "rpe": 5},
            {"run_date": TODAY, "run_type": "easy", "rpe": 5},
        ],
    )
    assert "REST_DAY_MINIMUM" not in _codes(evaluate_rules(ctx))


def test_taper_3d_triggers_within_3_days() -> None:
    ctx = _base_context(goal={"days_to_race": 2})
    assert "TAPER_3D" in _codes(evaluate_rules(ctx))
    assert "TAPER_7D" not in _codes(evaluate_rules(ctx))


def test_taper_7d_triggers_between_4_and_7_days() -> None:
    ctx = _base_context(goal={"days_to_race": 6})
    assert "TAPER_7D" in _codes(evaluate_rules(ctx))
    assert "TAPER_3D" not in _codes(evaluate_rules(ctx))


def test_taper_not_triggered_beyond_7_days() -> None:
    ctx = _base_context(goal={"days_to_race": 10})
    codes = _codes(evaluate_rules(ctx))
    assert "TAPER_3D" not in codes
    assert "TAPER_7D" not in codes


def test_taper_skipped_without_goal() -> None:
    ctx = _base_context(goal=None)
    codes = _codes(evaluate_rules(ctx))
    assert "TAPER_3D" not in codes
    assert "TAPER_7D" not in codes


def test_heat_alert_triggers_at_33_degrees() -> None:
    ctx = _base_context(weather={"temp_c": 33.0})
    assert "HEAT_ALERT" in _codes(evaluate_rules(ctx))


def test_heat_alert_not_triggered_just_under() -> None:
    ctx = _base_context(weather={"temp_c": 32.9})
    assert "HEAT_ALERT" not in _codes(evaluate_rules(ctx))


def test_cold_alert_triggers_at_minus_5() -> None:
    ctx = _base_context(weather={"temp_c": -5.0})
    assert "COLD_ALERT" in _codes(evaluate_rules(ctx))


def test_weather_none_triggers_nothing() -> None:
    ctx = _base_context(weather=None)
    codes = _codes(evaluate_rules(ctx))
    assert "HEAT_ALERT" not in codes
    assert "COLD_ALERT" not in codes


def test_injury_risk_triggers_on_two_consecutive_high_rpe_days() -> None:
    ctx = _base_context(
        recent_runs=[
            {"run_date": TODAY - timedelta(days=1), "run_type": "easy", "rpe": 9},
            {"run_date": TODAY - timedelta(days=2), "run_type": "easy", "rpe": 9},
        ]
    )
    assert "INJURY_RISK" in _codes(evaluate_rules(ctx))


def test_injury_risk_not_triggered_single_high_rpe_day() -> None:
    ctx = _base_context(
        recent_runs=[
            {"run_date": TODAY - timedelta(days=1), "run_type": "easy", "rpe": 9},
            {"run_date": TODAY - timedelta(days=2), "run_type": "easy", "rpe": 4},
        ]
    )
    assert "INJURY_RISK" not in _codes(evaluate_rules(ctx))


def test_beginner_guard_triggers_under_10_runs() -> None:
    ctx = _base_context(total_run_count=9)
    assert "BEGINNER_GUARD" in _codes(evaluate_rules(ctx))


def test_beginner_guard_not_triggered_at_10_runs() -> None:
    ctx = _base_context(total_run_count=10)
    assert "BEGINNER_GUARD" not in _codes(evaluate_rules(ctx))


def test_multiple_rules_can_trigger_together() -> None:
    ctx = _base_context(
        weekly={**_base_context()["weekly"], "completed_km": 36.0, "target_km": 30.0},
        weather={"temp_c": 35.0},
    )
    codes = _codes(evaluate_rules(ctx))
    assert "VOLUME_EXCEEDED" in codes
    assert "HEAT_ALERT" in codes


def test_every_constraint_has_code_and_message() -> None:
    ctx = _base_context(
        weekly={**_base_context()["weekly"], "completed_km": 36.0, "target_km": 30.0},
    )
    for c in evaluate_rules(ctx):
        assert isinstance(c["code"], str) and c["code"]
        assert isinstance(c["message"], str) and c["message"]
