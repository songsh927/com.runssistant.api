from functools import partial
from typing import Any

from langgraph.graph import END, StateGraph

from app.graph.nodes.context_assembler import assemble_context
from app.graph.nodes.llm_coach import call_coach
from app.graph.nodes.plan_updater import update_plan
from app.graph.nodes.response_formatter import format_response
from app.graph.nodes.rule_engine_node import apply_rules
from app.graph.state import CoachState
from app.llm.base import LLMProvider


def build_coach_graph(llm: LLMProvider) -> Any:
    workflow = StateGraph(CoachState)

    workflow.add_node("assemble_context", assemble_context)
    workflow.add_node("apply_rules", apply_rules)
    workflow.add_node("call_coach", partial(call_coach, llm=llm))
    workflow.add_node("update_plan", update_plan)
    workflow.add_node("format_response", format_response)

    workflow.set_entry_point("assemble_context")
    workflow.add_edge("assemble_context", "apply_rules")
    workflow.add_edge("apply_rules", "call_coach")
    workflow.add_edge("call_coach", "update_plan")
    workflow.add_edge("update_plan", "format_response")
    workflow.add_edge("format_response", END)

    return workflow.compile()
