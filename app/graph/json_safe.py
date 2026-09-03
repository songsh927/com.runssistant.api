import json
from typing import Any


def to_json_safe(data: Any) -> Any:
    """date/Decimal 등 JSON 비호환 타입을 문자열로 변환해 JSONB 저장·LLM 프롬프트에 쓴다."""
    return json.loads(json.dumps(data, default=str, ensure_ascii=False))
