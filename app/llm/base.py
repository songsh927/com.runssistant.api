from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: dict[str, Any] | None = None


class LLMProvider(ABC):
    """LLM provider 공통 인터페이스. 모든 provider는 이 인터페이스만 구현하면 된다."""

    @abstractmethod
    async def invoke(
        self,
        system: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse: ...

    @abstractmethod
    def get_model_name(self) -> str: ...
