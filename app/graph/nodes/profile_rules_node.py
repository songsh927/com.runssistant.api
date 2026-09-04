from typing import Any

from app.graph.nodes.profile_rules import evaluate_profile_rules
from app.graph.state import CoachState


async def apply_profile_rules(state: CoachState) -> dict[str, Any]:
    profile_constraints = evaluate_profile_rules(state["context"])
    return {"constraints": state["constraints"] + profile_constraints}
