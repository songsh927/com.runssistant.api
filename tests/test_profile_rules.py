
from app.graph.nodes.profile_rules import evaluate_profile_rules


def _ctx(profile: dict) -> dict:
    return {"runner_profile": profile, "is_available_day": True}


def _codes(context: dict) -> set[str]:
    return {r["code"] for r in evaluate_profile_rules(context)}


def test_beginner_guard_added() -> None:
    ctx = _ctx(
        {
            "experience_level": "beginner",
            "time_per_session": "30_60min",
            "cross_training": [],
            "injuries": {},
        }
    )
    assert "PROFILE_BEGINNER_GUARD" in _codes(ctx)


def test_novice_limit_added() -> None:
    ctx = _ctx(
        {
            "experience_level": "novice",
            "time_per_session": "30_60min",
            "cross_training": [],
            "injuries": {},
        }
    )
    assert "PROFILE_NOVICE_LIMIT" in _codes(ctx)


def test_intermediate_no_experience_constraint() -> None:
    ctx = _ctx(
        {
            "experience_level": "intermediate",
            "time_per_session": "unlimited",
            "cross_training": [],
            "injuries": {},
        }
    )
    codes = _codes(ctx)
    assert "PROFILE_BEGINNER_GUARD" not in codes
    assert "PROFILE_NOVICE_LIMIT" not in codes


def test_time_short_added() -> None:
    ctx = _ctx(
        {
            "experience_level": "advanced",
            "time_per_session": "under_30min",
            "cross_training": [],
            "injuries": {},
        }
    )
    assert "PROFILE_TIME_SHORT" in _codes(ctx)


def test_time_medium_added() -> None:
    ctx = _ctx(
        {
            "experience_level": "advanced",
            "time_per_session": "30_60min",
            "cross_training": [],
            "injuries": {},
        }
    )
    assert "PROFILE_TIME_MEDIUM" in _codes(ctx)


def test_non_training_day_added() -> None:
    ctx = {
        "runner_profile": {
            "experience_level": "intermediate",
            "time_per_session": "30_60min",
            "cross_training": [],
            "injuries": {},
        },
        "is_available_day": False,
    }
    assert "PROFILE_NON_TRAINING_DAY" in _codes(ctx)


def test_training_day_no_constraint() -> None:
    ctx = {
        "runner_profile": {
            "experience_level": "intermediate",
            "time_per_session": "30_60min",
            "cross_training": [],
            "injuries": {},
        },
        "is_available_day": True,
    }
    assert "PROFILE_NON_TRAINING_DAY" not in _codes(ctx)


def test_cross_high_load_weight() -> None:
    ctx = _ctx(
        {
            "experience_level": "intermediate",
            "time_per_session": "30_60min",
            "cross_training": ["weight"],
            "injuries": {},
        }
    )
    assert "PROFILE_CROSS_HIGH_LOAD" in _codes(ctx)


def test_cross_cardio_cycling() -> None:
    ctx = _ctx(
        {
            "experience_level": "intermediate",
            "time_per_session": "30_60min",
            "cross_training": ["cycling"],
            "injuries": {},
        }
    )
    assert "PROFILE_CROSS_CARDIO" in _codes(ctx)


def test_injury_knee_caution() -> None:
    ctx = _ctx(
        {
            "experience_level": "intermediate",
            "time_per_session": "30_60min",
            "cross_training": [],
            "injuries": {"knee": "caution"},
        }
    )
    assert "INJURY_KNEE_CAUTION" in _codes(ctx)


def test_injury_knee_severe() -> None:
    ctx = _ctx(
        {
            "experience_level": "intermediate",
            "time_per_session": "30_60min",
            "cross_training": [],
            "injuries": {"knee": "severe"},
        }
    )
    assert "INJURY_KNEE_SEVERE" in _codes(ctx)


def test_injury_mild_note() -> None:
    ctx = _ctx(
        {
            "experience_level": "intermediate",
            "time_per_session": "30_60min",
            "cross_training": [],
            "injuries": {"knee": "mild", "ankle": "none"},
        }
    )
    assert "PROFILE_INJURY_MILD_NOTE" in _codes(ctx)


def test_injury_none_no_constraint() -> None:
    ctx = _ctx(
        {
            "experience_level": "intermediate",
            "time_per_session": "30_60min",
            "cross_training": [],
            "injuries": {"knee": "none"},
        }
    )
    codes = _codes(ctx)
    assert "INJURY_KNEE_CAUTION" not in codes
    assert "INJURY_KNEE_SEVERE" not in codes
    assert "PROFILE_INJURY_MILD_NOTE" not in codes


def test_no_profile_returns_empty() -> None:
    assert evaluate_profile_rules({}) == []
    assert evaluate_profile_rules({"runner_profile": None}) == []


def test_beginner_with_knee_caution() -> None:
    ctx = _ctx(
        {
            "experience_level": "beginner",
            "time_per_session": "30_60min",
            "cross_training": [],
            "injuries": {"knee": "caution"},
        }
    )
    codes = _codes(ctx)
    assert "PROFILE_BEGINNER_GUARD" in codes
    assert "INJURY_KNEE_CAUTION" in codes
