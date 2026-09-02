from typing import Any

from app.graph.nodes.rule_engine import evaluate_rules
from app.graph.state import CoachState


async def apply_rules(state: CoachState) -> dict[str, Any]:
    return {"constraints": evaluate_rules(state["context"])}
