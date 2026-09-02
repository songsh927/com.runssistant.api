import json
from typing import Any

from pydantic import ValidationError

from app.core.exceptions import CoachingUnavailable
from app.graph.json_safe import to_json_safe
from app.graph.prompts import COACH_SYSTEM_PROMPT
from app.graph.state import CoachState
from app.llm.base import LLMProvider
from app.llm.parsing import extract_json
from app.schemas.coach import CoachRecommendation

_MAX_ATTEMPTS = 2

# gemma3:4b 같은 소형 모델이 종종 쓰는 표기를 runs.run_type 어휘로 정규화한다.
_RUN_TYPE_ALIASES = {"long": "long_run"}


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("run_type") in _RUN_TYPE_ALIASES:
        data = {**data, "run_type": _RUN_TYPE_ALIASES[data["run_type"]]}
    return data


async def call_coach(state: CoachState, llm: LLMProvider) -> dict[str, Any]:
    constraints = state["constraints"]
    constraints_text = (
        "\n".join(f"- {c['code']}: {c['message']}" for c in constraints) if constraints else "없음"
    )
    system = COACH_SYSTEM_PROMPT.format(constraints=constraints_text)
    user_message = json.dumps(to_json_safe(state["context"]), ensure_ascii=False)

    last_error: Exception | None = None
    for _ in range(_MAX_ATTEMPTS):
        try:
            response = await llm.invoke(system=system, user_message=user_message, temperature=0.7)
            data = _normalize(extract_json(response.content))
            recommendation = CoachRecommendation(**data)
            return {
                "recommendation": recommendation.model_dump(),
                "model_used": llm.get_model_name(),
            }
        except (ValueError, ValidationError, KeyError) as e:
            last_error = e
        except Exception as e:
            # provider/network failures (httpx, boto3, ...) must degrade to 503, not crash
            last_error = e

    raise CoachingUnavailable() from last_error
