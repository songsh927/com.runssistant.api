from typing import Any

from app.graph.json_safe import to_json_safe
from app.graph.state import CoachState
from app.repositories.coaching_repo import CoachingRepository
from app.services.plan_service import PlanService

_plan_svc = PlanService()
_coaching_repo = CoachingRepository()


async def update_plan(state: CoachState) -> dict[str, Any]:
    session = state["db_session"]
    user_id = state["user_id"]

    await _plan_svc.apply_recommendation(
        session, user_id, state["recommendation"], state["constraints"]
    )

    coaching_session = await _coaching_repo.create(
        session,
        user_id=user_id,
        context_snapshot=to_json_safe(state["context"]),
        constraints=state["constraints"],
        recommendation=state["recommendation"],
        model_used=state["model_used"],
    )

    return {"coaching_session_id": coaching_session.id}
