from datetime import date
from typing import Any

from app.core.pace import get_monday
from app.graph.state import CoachState


async def format_response(state: CoachState) -> dict[str, Any]:
    context = state["context"]
    weekly = context["weekly"]
    constraints = state["constraints"]

    today = date.today()
    week_end_weekday = 6  # sunday, mon=0..sun=6
    remaining_days = week_end_weekday - (today - get_monday(today)).days

    weather = context.get("weather")
    weather_response = (
        {
            "temp_c": weather.get("temp_c"),
            "humidity": weather.get("humidity"),
            "condition": weather.get("condition"),
        }
        if weather
        else None
    )

    plan_adjustment = "; ".join(c["message"] for c in constraints) if constraints else None

    response = {
        "session_id": state["coaching_session_id"],
        "recommendation": state["recommendation"],
        "weekly_context": {
            "completed_km": weekly["completed_km"],
            "target_km": weekly["target_km"],
            "progress_pct": weekly["progress_pct"],
            "remaining_days": remaining_days,
            "sessions_done": weekly["session_count"],
            "plan_adjustment": plan_adjustment,
        },
        "weather": weather_response,
    }
    return {"response": response}
